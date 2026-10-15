import json
import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import (
    UserProfile, ConservationZone, TourismRestriction, Bustard,
    Incident, IncidentLocation, MedicalCase, MedicalTreatment,
    MedicalEquipment, ActivityLog,
    ROLE_ADMIN, ROLE_FOREST_OFFICER, ROLE_RANGER, ROLE_MEDICAL_TEAM, ROLE_RESEARCHER,
    DATA_ENV_DEMO, DATA_ENV_PRODUCTION
)

class Command(BaseCommand):
    help = "Seed initial demonstration data and default role accounts for Bustard Beacon platform."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Initializing Bustard Beacon Demo Seeding Engine..."))

        # 1. Create System Users
        users_data = [
            ('admin', 'admin123', 'admin@bustardbeacon.gov.in', 'System', 'Administrator', ROLE_ADMIN, 'ADM-001'),
            ('officer_solapur', 'officer123', 'officer.nannaj@forest.gov.in', 'Rajesh', 'Deshmukh', ROLE_FOREST_OFFICER, 'FO-SLP-101'),
            ('ranger_nannaj', 'ranger123', 'ranger.nannaj@forest.gov.in', 'Vikram', 'Patil', ROLE_RANGER, 'RNG-NNJ-204'),
            ('dr_vet_solapur', 'vet123', 'dr.vet@bustardbeacon.org', 'Dr. Sunita', 'Kulkarni', ROLE_MEDICAL_TEAM, 'VET-SLP-302'),
            ('dr_researcher', 'research123', 'researcher@wii.gov.in', 'Dr. Amit', 'Joshi', ROLE_RESEARCHER, 'RES-WII-501'),
        ]

        created_users = {}
        for username, password, email, fname, lname, role, badge in users_data:
            user, u_created = User.objects.get_or_create(username=username, defaults={
                'email': email,
                'first_name': fname,
                'last_name': lname,
                'is_staff': (role in [ROLE_ADMIN, ROLE_FOREST_OFFICER]),
                'is_superuser': (role == ROLE_ADMIN)
            })
            if u_created:
                user.save()

            # ALWAYS enforce default demo passwords when seeding
            user.set_password(password)
            user.save()

            profile, p_created = UserProfile.objects.get_or_create(user=user)
            profile.role = role
            profile.badge_number = badge
            if role == ROLE_RANGER:
                profile.current_latitude = 17.8228
                profile.current_longitude = 75.8458
                profile.location_updated_at = timezone.now()
                profile.is_active_field_mode = True
            profile.save()
            created_users[role] = user

        self.stdout.write(self.style.SUCCESS("[OK] Default user accounts verified and passwords reset."))

        # 2. Seed Nannaj Sanctuary Reference Conservation Zones
        zones_data = [
            {
                'name': 'Nannaj Core Breeding Sanctuary',
                'code': 'ZONE-NNJ-CORE',
                'zone_type': 'BREEDING',
                'color_hex': '#d32f2f',
                'description': 'Reference / Approximate Conservation Boundary: Primary nesting and courtship display arena for Great Indian Bustard at Nannaj.',
                # Coordinates array polygon around Nannaj (~17.8228, 75.8458)
                'geojson': json.dumps([
                    [17.8350, 75.8350],
                    [17.8350, 75.8550],
                    [17.8100, 75.8550],
                    [17.8100, 75.8350]
                ])
            },
            {
                'name': 'Solapur Grassland Buffer Zone',
                'code': 'ZONE-NNJ-BUFF',
                'zone_type': 'BUFFER_RESTRICTED',
                'color_hex': '#f57c00',
                'description': 'Reference / Approximate Conservation Boundary: Buffer corridor protecting foraging routes against power lines and encroachment.',
                'geojson': json.dumps([
                    [17.8500, 75.8200],
                    [17.8500, 75.8700],
                    [17.7900, 75.8700],
                    [17.7900, 75.8200]
                ])
            },
            {
                'name': 'Maldhok Tourism & Visitor Area',
                'code': 'ZONE-NNJ-TOUR',
                'zone_type': 'TOURISM_NORMAL',
                'color_hex': '#388e3c',
                'description': 'Reference / Approximate Conservation Boundary: Designated eco-tourism viewing area with strict guided trail rules.',
                'geojson': json.dumps([
                    [17.8050, 75.8400],
                    [17.8050, 75.8600],
                    [17.7850, 75.8600],
                    [17.7850, 75.8400]
                ])
            }
        ]

        created_zones = []
        for zd in zones_data:
            z, z_created = ConservationZone.objects.get_or_create(code=zd['code'], defaults={
                'name': zd['name'],
                'zone_type': zd['zone_type'],
                'color_hex': zd['color_hex'],
                'description': zd['description'],
                'boundary_geojson': zd['geojson'],
                'responsible_officer': created_users[ROLE_FOREST_OFFICER]
            })
            created_zones.append(z)

            # Assign tourism restriction
            TourismRestriction.objects.get_or_create(zone=z, defaults={
                'status': 'RESTRICTED' if z.zone_type == 'BREEDING' else 'ALLOWED',
                'restriction_reason': 'Breeding season enclosure restriction to prevent nest disturbance.' if z.zone_type == 'BREEDING' else 'Eco-tourism permit required.',
                'valid_from': timezone.now().date(),
                'updated_by': created_users[ROLE_FOREST_OFFICER]
            })

        self.stdout.write(self.style.SUCCESS("[OK] Nannaj reference conservation zones created."))

        # 3. Seed Great Indian Bustard Master Register (Demo Records)
        birds_data = [
            ('GIB-NNJ-001', 'Maldhok King', 'MALE', 'ADULT', 'HEALTHY', 2018),
            ('GIB-NNJ-002', 'Solapur Queen', 'FEMALE', 'ADULT', 'UNDER_MONITORING', 2019),
            ('GIB-NNJ-003', 'Sahyadri Jewel', 'FEMALE', 'JUVENILE', 'REHABILITATION', 2024),
        ]

        created_birds = []
        for tag, name, sex, age, health, birth_yr in birds_data:
            b, b_created = Bustard.objects.get_or_create(tag_id=tag, defaults={
                'name': name,
                'sex': sex,
                'age_class': age,
                'health_status': health,
                'estimated_birth_year': birth_yr,
                'last_seen_zone': created_zones[0],
                'data_environment': DATA_ENV_DEMO
            })
            created_birds.append(b)

        self.stdout.write(self.style.SUCCESS("[OK] Great Indian Bustard register seeded."))

        # 4. Seed Demo Incidents
        inc_data = [
            {
                'category': 'BIRD_SIGHTING',
                'description': 'DEMO RECORD: Adult male Great Indian Bustard observed displaying courtship plumage in Nannaj grassland sector.',
                'priority': 'LOW',
                'status': 'VERIFIED',
                'reporter': created_users[ROLE_RANGER],
                'lat': 17.8245,
                'lng': 75.8472,
                'zone': created_zones[0]
            },
            {
                'category': 'POWERLINE_COLLISION',
                'description': 'DEMO RECORD: High-tension electrical lines near buffer corridor lack bird diverters. Urgent diverter installation recommended.',
                'priority': 'HIGH',
                'status': 'VERIFIED',
                'reporter': created_users[ROLE_RANGER],
                'lat': 17.8390,
                'lng': 75.8310,
                'zone': created_zones[1]
            },
            {
                'category': 'INJURED_BIRD',
                'description': 'DEMO RECORD: Sub-adult female found with minor wing abrasion near fencing boundary. Required veterinary response.',
                'priority': 'CRITICAL',
                'status': 'VERIFIED',
                'reporter': created_users[ROLE_RANGER],
                'lat': 17.8210,
                'lng': 75.8490,
                'zone': created_zones[0]
            }
        ]

        for idata in inc_data:
            inc, i_created = Incident.objects.get_or_create(
                description=idata['description'],
                defaults={
                    'category': idata['category'],
                    'priority': idata['priority'],
                    'status': idata['status'],
                    'reporter': idata['reporter'],
                    'verified_by': created_users[ROLE_FOREST_OFFICER],
                    'verified_at': timezone.now(),
                    'data_source': 'FIELD_REPORT',
                    'data_environment': DATA_ENV_DEMO
                }
            )
            if i_created:
                IncidentLocation.objects.create(
                    incident=inc,
                    latitude=idata['lat'],
                    longitude=idata['lng'],
                    accuracy_meters=5.0,
                    zone=idata['zone'],
                    weather_temperature_c=32.5,
                    weather_condition='Sunny / Clear',
                    weather_wind_speed_kmh=11.2
                )

                # Create Medical Case for Critical Injured Bird
                if idata['category'] == 'INJURED_BIRD':
                    med, m_created = MedicalCase.objects.get_or_create(incident=inc, defaults={
                        'bustard': created_birds[2],
                        'condition_summary': 'Minor wing feather damage from fencing boundary',
                        'symptoms': 'Wing droop, slight limping, normal alertness',
                        'diagnosis': 'Superficial muscle strain and primary feather bending',
                        'rehabilitation_stage': 'RECOVERY_ENCLOSURE',
                        'status': 'UNDER_TREATMENT',
                        'created_by': created_users[ROLE_FOREST_OFFICER]
                    })
                    if m_created:
                        MedicalTreatment.objects.create(
                            medical_case=med,
                            administered_by=created_users[ROLE_MEDICAL_TEAM],
                            treatment_description='Antiseptic cleansing and anti-inflammatory bandage dressing.',
                            medications_given='Meloxicam 0.2mg/kg, Topical Betadine',
                            dosage_notes='Daily oral dose once per morning for 5 days.'
                        )

        self.stdout.write(self.style.SUCCESS("[OK] Demo field incidents & medical rescue cases seeded."))

        # 5. Seed Medical Equipment Catalog
        eq_data = [
            ('Avian Transport Crate (Padded)', 'Transport / Rescue', 4, 'OPERATIONAL'),
            ('Avian Wing Splint & Wrap Kit', 'Veterinary First Aid', 6, 'OPERATIONAL'),
            ('Portable Oxygen Incubator Unit', 'Intensive Care', 2, 'OPERATIONAL'),
            ('GPS Solar Telemetry Harness Kit', 'Tracking / Monitoring', 3, 'OPERATIONAL'),
        ]
        for ename, ecat, eqty, estatus in eq_data:
            MedicalEquipment.objects.get_or_create(name=ename, defaults={
                'category': ecat,
                'quantity_available': eqty,
                'status': estatus
            })

        self.stdout.write(self.style.SUCCESS("[OK] Medical equipment catalog seeded."))


        # Log Activity
        ActivityLog.objects.create(
            user=created_users[ROLE_ADMIN],
            user_display="Admin Seeding Script",
            action="SEED_DEMO_DATA",
            description="Seeded initial demonstration dataset, users, reference zones, and sample records tagged with DEMO.",
            timestamp=timezone.now()
        )

        self.stdout.write(self.style.SUCCESS("\n========================================================"))
        self.stdout.write(self.style.SUCCESS("  BUSTARD BEACON DEMO SEEDING COMPLETED SUCCESSFULLY!"))
        self.stdout.write(self.style.SUCCESS("========================================================"))
        self.stdout.write(self.style.NOTICE("Demonstration Accounts Created:"))
        self.stdout.write(" 1. Admin:           username: admin            password: admin123")
        self.stdout.write(" 2. Forest Officer:  username: officer_solapur  password: officer123")
        self.stdout.write(" 3. Field Ranger:    username: ranger_nannaj    password: ranger123")
        self.stdout.write(" 4. Medical Team:    username: dr_vet_solapur   password: vet123")
        self.stdout.write(" 5. Researcher:      username: dr_researcher    password: research123")
        self.stdout.write(self.style.SUCCESS("========================================================\n"))
