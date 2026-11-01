from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid

# Role Constants
ROLE_ADMIN = 'ADMIN'
ROLE_FOREST_OFFICER = 'FOREST_OFFICER'
ROLE_RANGER = 'RANGER'
ROLE_MEDICAL_TEAM = 'MEDICAL_TEAM'
ROLE_RESEARCHER = 'RESEARCHER'

ROLE_CHOICES = (
    (ROLE_ADMIN, 'System Administrator'),
    (ROLE_FOREST_OFFICER, 'Forest Officer'),
    (ROLE_RANGER, 'Ranger / Field Officer'),
    (ROLE_MEDICAL_TEAM, 'Veterinary Medical Team'),
    (ROLE_RESEARCHER, 'Wildlife Researcher'),
)

DATA_ENV_PRODUCTION = 'PRODUCTION'
DATA_ENV_DEMO = 'DEMO'

DATA_ENV_CHOICES = (
    (DATA_ENV_PRODUCTION, 'Production Data'),
    (DATA_ENV_DEMO, 'Demo / Test Data'),
)

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=30, choices=ROLE_CHOICES, default=ROLE_RANGER)
    badge_number = models.CharField(max_length=50, blank=True, null=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    assigned_zone = models.ForeignKey('ConservationZone', on_delete=models.SET_NULL, null=True, blank=True, related_name='rangers')
    current_latitude = models.FloatField(null=True, blank=True)
    current_longitude = models.FloatField(null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)
    is_active_field_mode = models.BooleanField(default=False)
    AVAILABILITY_CHOICES = (
        ('AVAILABLE', 'Available'),
        ('BUSY', 'Busy'),
        ('OFFLINE', 'Offline'),
    )
    availability_status = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default='OFFLINE')
    force_password_change = models.BooleanField(default=False)
    profile_image = models.ImageField(upload_to='profile_images/', null=True, blank=True)

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.get_role_display()})"


class ConservationZone(models.Model):
    ZONE_TYPES = (
        ('BREEDING', 'Core Breeding Sanctuary'),
        ('CORE_CONSERVATION', 'Core Conservation Zone'),
        ('BUFFER_RESTRICTED', 'Buffer / Restricted Zone'),
        ('TOURISM_NORMAL', 'Tourism & Buffer Zone'),
    )
    name = models.CharField(max_length=100)
    zone_type = models.CharField(max_length=30, choices=ZONE_TYPES, default='CORE_CONSERVATION')
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)
    responsible_officer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='managed_zones')
    # Polygon array formatted as JSON string: [[lat, lng], [lat, lng], ...]
    boundary_geojson = models.TextField(help_text="JSON array of lat/lng coordinates bounding the zone", blank=True)
    color_hex = models.CharField(max_length=10, default="#2e7d32")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.code})"


class TourismRestriction(models.Model):
    STATUS_CHOICES = (
        ('ALLOWED', 'Tourism Allowed'),
        ('RESTRICTED', 'Restricted Entry (Permit Required)'),
        ('PROHIBITED', 'Strictly Prohibited'),
    )
    zone = models.ForeignKey(ConservationZone, on_delete=models.CASCADE, related_name='tourism_restrictions')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='ALLOWED')
    restriction_reason = models.TextField()
    valid_from = models.DateField()
    valid_until = models.DateField(null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.zone.name} - {self.get_status_display()}"


class TourismRecord(models.Model):
    STATUS_CHOICES = (
        ('APPROVED', 'Approved / Active Permit'),
        ('PENDING', 'Pending Verification'),
        ('COMPLETED', 'Visit Completed'),
        ('CANCELLED', 'Cancelled / Revoked'),
    )

    permit_id = models.CharField(max_length=30, unique=True, editable=False)
    visitor_name = models.CharField(max_length=150, help_text="Lead visitor or tour group name")
    contact_phone = models.CharField(max_length=30, blank=True)
    contact_email = models.EmailField(blank=True)
    visit_date = models.DateField(default=timezone.now)
    visitor_count = models.PositiveIntegerField(default=1, help_text="Number of persons in party")
    zone = models.ForeignKey(ConservationZone, on_delete=models.SET_NULL, null=True, blank=True, related_name='tourism_records')
    location_area = models.CharField(max_length=150, blank=True, help_text="Designated trail, watchtower, or visitor point")
    purpose_of_visit = models.CharField(max_length=200, help_text="Eco-tourism, birdwatching, educational tour, photography, etc.")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='APPROVED')
    remarks = models.TextField(blank=True, help_text="Special vehicle permits, guide assigned, restrictions, or notes")
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='recorded_tourism')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-visit_date', '-created_at']

    def __str__(self):
        return f"{self.permit_id} - {self.visitor_name} ({self.visit_date})"

    def save(self, *args, **kwargs):
        if not self.permit_id:
            import uuid
            date_str = (self.visit_date or timezone.now().date()).strftime('%Y%m%d')
            short_id = uuid.uuid4().hex[:6].upper()
            self.permit_id = f"TRM-{date_str}-{short_id}"
        super().save(*args, **kwargs)


class Bustard(models.Model):
    SEX_CHOICES = (
        ('MALE', 'Male'),
        ('FEMALE', 'Female'),
        ('UNKNOWN', 'Unknown'),
    )
    AGE_CHOICES = (
        ('JUVENILE', 'Chick / Juvenile'),
        ('SUB_ADULT', 'Sub-Adult'),
        ('ADULT', 'Adult'),
        ('OLD', 'Old'),
    )
    HEALTH_CHOICES = (
        ('HEALTHY', 'Healthy / Active'),
        ('UNDER_MONITORING', 'Under Monitoring'),
        ('INJURED', 'Injured'),
        ('REHABILITATION', 'In Medical Rehabilitation'),
        ('DECEASED', 'Deceased'),
        ('MISSING', 'Missing / Unconfirmed'),
    )
    tag_id = models.CharField(max_length=50, unique=True, help_text="e.g. GIB-NNJ-001")
    name = models.CharField(max_length=100, blank=True, help_text="Optional local identifier name")
    species = models.CharField(max_length=100, default='Great Indian Bustard')
    sex = models.CharField(max_length=10, choices=SEX_CHOICES, default='UNKNOWN')
    age_class = models.CharField(max_length=20, choices=AGE_CHOICES, default='ADULT')
    health_status = models.CharField(max_length=30, choices=HEALTH_CHOICES, default='HEALTHY')
    estimated_birth_year = models.IntegerField(null=True, blank=True)
    nesting_notes = models.TextField(blank=True)
    last_seen_date = models.DateTimeField(null=True, blank=True)
    last_seen_zone = models.ForeignKey(ConservationZone, on_delete=models.SET_NULL, null=True, blank=True)
    data_environment = models.CharField(max_length=20, choices=DATA_ENV_CHOICES, default=DATA_ENV_PRODUCTION)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.tag_id} ({self.name or 'Unnamed'}) - {self.get_health_status_display()}"


class BustardMovement(models.Model):
    bustard = models.ForeignKey(Bustard, on_delete=models.CASCADE, related_name='movements')
    recorded_at = models.DateTimeField(default=timezone.now)
    latitude = models.FloatField()
    longitude = models.FloatField()
    data_source = models.CharField(max_length=50, default="FIELD_OBSERVATION")
    confidence = models.CharField(max_length=20, default="VERIFIED")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-recorded_at']


class BreedingRecord(models.Model):
    bustard = models.ForeignKey(Bustard, on_delete=models.CASCADE, related_name='breeding_records')
    season_year = models.IntegerField()
    nest_latitude = models.FloatField()
    nest_longitude = models.FloatField()
    clutch_size = models.IntegerField(default=1)
    chick_hatch_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=50, default="NESTING_ACTIVE")
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class BirthRecord(models.Model):
    bustard = models.OneToOneField(Bustard, on_delete=models.CASCADE, related_name='birth_record')
    hatch_date = models.DateField()
    nest_zone = models.ForeignKey(ConservationZone, on_delete=models.SET_NULL, null=True)
    clutch_reference = models.CharField(max_length=100, blank=True)
    parent_male_tag = models.CharField(max_length=50, blank=True)
    parent_female_tag = models.CharField(max_length=50, blank=True)
    notes = models.TextField(blank=True)
    birth_image = models.ImageField(upload_to='birth_records/%Y/%m/', null=True, blank=True)


class DeathRecord(models.Model):
    bustard = models.OneToOneField(Bustard, on_delete=models.CASCADE, related_name='death_record')
    date_of_death = models.DateField()
    cause_of_death = models.CharField(max_length=100, help_text="e.g. Power Line Collision, Predation, Natural Causes")
    autopsy_summary = models.TextField(blank=True)
    location_latitude = models.FloatField(null=True, blank=True)
    location_longitude = models.FloatField(null=True, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)


class MissingBirdRecord(models.Model):
    bustard = models.ForeignKey(Bustard, on_delete=models.CASCADE, related_name='missing_records')
    reported_missing_date = models.DateField()
    last_known_latitude = models.FloatField()
    last_known_longitude = models.FloatField()
    search_status = models.CharField(max_length=50, default="ACTIVE_SEARCH")
    notes = models.TextField(blank=True)
    reported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # Found Information
    found_date = models.DateField(null=True, blank=True)
    found_latitude = models.FloatField(null=True, blank=True)
    found_longitude = models.FloatField(null=True, blank=True)
    found_by = models.CharField(max_length=100, blank=True)
    found_notes = models.TextField(blank=True)


class Incident(models.Model):
    CATEGORY_CHOICES = (
        ('BIRD_SIGHTING', 'Great Indian Bustard Sighting'),
        ('INJURED_BIRD', 'Injured Bustard / Wildlife'),
        ('SICK_BIRD', 'Sick / Weak Bustard'),
        ('POACHING_THREAT', 'Poaching / Illegal Hunting Activity'),
        ('POWERLINE_COLLISION', 'High-Tension Line Collision Threat'),
        ('SUSPICIOUS_ACTIVITY', 'Suspicious Human Intrusion'),
        ('OTHER', 'Other Conservation Alert'),
    )
    PRIORITY_CHOICES = (
        ('CRITICAL', 'CRITICAL — Immediate Emergency'),
        ('HIGH', 'HIGH — Rapid Response Required'),
        ('MEDIUM', 'MEDIUM — Standard Monitoring'),
        ('LOW', 'LOW — Information / Routine'),
    )
    STATUS_CHOICES = (
        ('PENDING', 'Pending Verification'),
        ('VERIFIED', 'Verified Operational Incident'),
        ('REJECTED', 'Rejected / Invalid Report'),
        ('MORE_INFO', 'Request More Information'),
        ('RESOLVED', 'Resolved / Action Completed'),
    )
    DATA_SOURCE_CHOICES = (
        ('FIELD_REPORT', 'Field Ranger Report'),
        ('PUBLIC_OBSERVATION', 'Public Observation'),
        ('RESEARCH_IMPORT', 'External Research Data'),
    )

    incident_id = models.CharField(max_length=50, unique=True, editable=False)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    custom_category_name = models.CharField(max_length=100, blank=True)
    bustard = models.ForeignKey(Bustard, on_delete=models.SET_NULL, null=True, blank=True, related_name='incidents')
    description = models.TextField()
    priority = models.CharField(max_length=15, choices=PRIORITY_CHOICES, default='MEDIUM')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='PENDING')
    reporter = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reported_incidents')
    reported_at = models.DateTimeField(default=timezone.now)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_incidents')
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)
    data_source = models.CharField(max_length=30, choices=DATA_SOURCE_CHOICES, default='FIELD_REPORT')
    data_environment = models.CharField(max_length=20, choices=DATA_ENV_CHOICES, default=DATA_ENV_PRODUCTION)

    class Meta:
        ordering = ['-reported_at']

    def save(self, *args, **kwargs):
        if not self.incident_id:
            year = timezone.now().strftime('%Y')
            random_code = str(uuid.uuid4().hex[:6]).upper()
            self.incident_id = f"INC-{year}-{random_code}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.incident_id} - {self.get_category_display()} ({self.get_priority_display()})"


class IncidentLocation(models.Model):
    incident = models.OneToOneField(Incident, on_delete=models.CASCADE, related_name='location')
    latitude = models.FloatField()
    longitude = models.FloatField()
    accuracy_meters = models.FloatField(null=True, blank=True)
    zone = models.ForeignKey(ConservationZone, on_delete=models.SET_NULL, null=True, blank=True)
    weather_temperature_c = models.FloatField(null=True, blank=True)
    weather_condition = models.CharField(max_length=100, blank=True)
    weather_wind_speed_kmh = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.incident.incident_id} at ({self.latitude:.4f}, {self.longitude:.4f})"


class IncidentImage(models.Model):
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='images', null=True, blank=True)
    bustard = models.ForeignKey(Bustard, on_delete=models.CASCADE, related_name='images', null=True, blank=True)
    image = models.ImageField(upload_to='incident_photos/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    caption = models.CharField(max_length=200, blank=True)

    def __str__(self):
        return f"Image for {self.incident.incident_id}"


class PatrolAssignment(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending Ranger Acceptance'),
        ('ACCEPTED', 'Accepted by Ranger'),
        ('IN_PROGRESS', 'Patrol / Investigation In Progress'),
        ('COMPLETED', 'Task Completed'),
    )
    incident = models.ForeignKey(Incident, on_delete=models.CASCADE, related_name='assignments')
    assigned_ranger = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_tasks')
    assigned_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_assignments')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    assigned_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    instructions = models.TextField()
    ranger_notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-assigned_at']

    def __str__(self):
        return f"Task for {self.assigned_ranger.username}: {self.incident.incident_id}"


class AssignmentAttachment(models.Model):
    assignment = models.ForeignKey(PatrolAssignment, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='assignment_evidence/%Y/%m/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Attachment for {self.assignment.id}"
    
    @property
    def is_image(self):
        ext = self.file.name.lower().split('.')[-1]
        return ext in ['jpg', 'jpeg', 'png', 'webp', 'gif']


class MedicalCase(models.Model):
    STATUS_CHOICES = (
        ('ACTIVE', 'Active Emergency'),
        ('UNDER_TREATMENT', 'Under Active Treatment'),
        ('REHABILITATION', 'In Rehabilitation Enclosure'),
        ('RECOVERED', 'Fit for Release / Recovered'),
        ('CLOSED', 'Case Closed (Released / Deceased)'),
    )
    STAGE_CHOICES = (
        ('RECOVERY_ENCLOSURE', 'Recovery Enclosure'),
        ('ICU', 'ICU Intensive Care Unit'),
        ('PRE_RELEASE', 'Pre-Release Outdoor Flight Cage'),
        ('RELEASED', 'Successfully Released to Wild'),
        ('DECEASED', 'Confirmed Dead / Deceased'),
    )
    PRIORITY_CHOICES = (
        ('HIGH', 'High'),
        ('MEDIUM', 'Medium'),
        ('LOW', 'Low'),
    )
    case_id = models.CharField(max_length=50, unique=True, editable=False)
    incident = models.ForeignKey(Incident, on_delete=models.SET_NULL, null=True, blank=True, related_name='medical_cases')
    bustard = models.ForeignKey(Bustard, on_delete=models.SET_NULL, null=True, blank=True, related_name='medical_cases')
    condition_summary = models.CharField(max_length=200)
    symptoms = models.TextField()
    diagnosis = models.TextField(blank=True)
    rehabilitation_stage = models.CharField(max_length=30, choices=STAGE_CHOICES, default='ICU')
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='ACTIVE')
    priority = models.CharField(max_length=15, choices=PRIORITY_CHOICES, default='MEDIUM')
    assigned_team = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_medical_cases')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_medical_cases')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.case_id:
            year = timezone.now().strftime('%Y')
            random_code = str(uuid.uuid4().hex[:5]).upper()
            self.case_id = f"MED-{year}-{random_code}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.case_id} - {self.condition_summary} ({self.get_status_display()})"


class MedicalTreatment(models.Model):
    medical_case = models.ForeignKey(MedicalCase, on_delete=models.CASCADE, related_name='treatments')
    administered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    treatment_description = models.TextField()
    medications_given = models.CharField(max_length=255, blank=True)
    dosage_notes = models.TextField(blank=True)
    treatment_time = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-treatment_time']


class MedicalEquipment(models.Model):
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, help_text="e.g. Veterinary Rescue Kit, Avian Splint, Incubator")
    quantity_available = models.IntegerField(default=1)
    quantity_in_use = models.IntegerField(default=0)
    status = models.CharField(max_length=50, default="OPERATIONAL")
    last_inspected = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.quantity_available} units)"



class Complaint(models.Model):
    subject = models.CharField(max_length=200)
    description = models.TextField()
    complainant_name = models.CharField(max_length=100)
    contact_info = models.CharField(max_length=100)
    status = models.CharField(max_length=20, default="NEW")
    created_at = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=150)
    message = models.TextField()
    category = models.CharField(max_length=50, default="GENERAL")
    link_url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.title}"


class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    user_display = models.CharField(max_length=100, blank=True)
    action = models.CharField(max_length=50) # LOGIN, LOGOUT, CREATE, UPDATE, DELETE, VERIFY, REJECT, ASSIGN, IMPORT, REPORT_GEN
    model_name = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=100, blank=True)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M')}] {self.user_display or 'System'} - {self.action}: {self.description[:50]}"

class ConservationReport(models.Model):
    STATUS_CHOICES = (
        ('DRAFT', 'Draft Analysis'),
        ('FINALIZED', 'Finalized & Sent'),
    )
    period_start = models.DateField()
    period_end = models.DateField()
    generated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='generated_reports')
    created_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='DRAFT')
    submitted_to_fo = models.BooleanField(default=False)
    submitted_to_admin = models.BooleanField(default=False)
    submitted_at_fo = models.DateTimeField(null=True, blank=True)
    submitted_at_admin = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Report for {self.period_start} to {self.period_end} ({self.status})"
