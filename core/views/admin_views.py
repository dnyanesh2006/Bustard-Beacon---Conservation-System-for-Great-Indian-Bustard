from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from ..models import (
    UserProfile, Bustard, BirthRecord, DeathRecord, MissingBirdRecord,
    ActivityLog, ROLE_ADMIN, ROLE_CHOICES, Incident, MedicalCase, ConservationZone,
    ROLE_RANGER, ROLE_FOREST_OFFICER, ROLE_MEDICAL_TEAM, ROLE_RESEARCHER
)
from ..services.audit_service import log_activity
from django.core.exceptions import ValidationError
from ..validators import (
    validate_indian_mobile, validate_email_address, validate_username,
    validate_uploaded_image, validate_date_string
)
from .report_views import parse_date_range_safely, filter_datetime_range
from django.conf import settings
from django.core.mail import send_mail
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
import secrets
import logging

logger = logging.getLogger(__name__)

def is_admin_check(user):
    return user.is_superuser or (hasattr(user, 'profile') and user.profile.role == ROLE_ADMIN)

def generate_batch_number(role):
    prefix_map = {
        ROLE_RANGER: 'RNG',
        ROLE_FOREST_OFFICER: 'FO',
        ROLE_ADMIN: 'ADM',
        ROLE_MEDICAL_TEAM: 'VET-MT',
        ROLE_RESEARCHER: 'WL-RSH',
    }
    prefix = prefix_map.get(role, 'EMP')
    
    import re
    profiles = UserProfile.objects.filter(role=role, badge_number__isnull=False)
    max_num = 0
    for p in profiles:
        match = re.search(r'-(\d+)$', str(p.badge_number))
        if match:
            num = int(match.group(1))
            if num > max_num:
                max_num = num
    new_num = max_num + 1
    return f"{prefix}-{new_num:03d}"


@login_required
@user_passes_test(is_admin_check)
def admin_dashboard(request):
    total_users = User.objects.count()
    total_birds = Bustard.objects.count()
    total_incidents = Incident.objects.count()
    total_medical = MedicalCase.objects.count()
    total_audit_logs = ActivityLog.objects.count()

    recent_logs = ActivityLog.objects.all()[:10]

    context = {
        'total_users': total_users,
        'total_birds': total_birds,
        'total_incidents': total_incidents,
        'total_fo_records': total_incidents,
        'total_medical': total_medical,
        'total_audit_logs': total_audit_logs,
        'recent_logs': recent_logs,
    }
    return render(request, 'admin_panel/dashboard.html', context)


@login_required
@user_passes_test(is_admin_check)
def admin_users_overview(request):
    """
    Read-only overview of registered personnel segmented by functional roles:
    Rangers, Forest Officers, Medical Team members, Researchers, and Administrators.
    """
    q = request.GET.get('q', '').strip()
    active_role = request.GET.get('role', 'RANGER').upper()

    base_users = User.objects.all().select_related('profile', 'profile__assigned_zone')
    if q:
        base_users = base_users.filter(
            Q(username__icontains=q) |
            Q(first_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(email__icontains=q) |
            Q(profile__badge_number__icontains=q)
        )

    rangers_qs = base_users.filter(profile__role=ROLE_RANGER).order_by('date_joined')
    officers_qs = base_users.filter(profile__role=ROLE_FOREST_OFFICER).order_by('date_joined')
    medical_qs = base_users.filter(profile__role=ROLE_MEDICAL_TEAM).order_by('date_joined')
    researchers_qs = base_users.filter(profile__role=ROLE_RESEARCHER).order_by('date_joined')
    admins_qs = base_users.filter(profile__role=ROLE_ADMIN).order_by('date_joined')

    role_counts = {
        'RANGER': User.objects.filter(profile__role=ROLE_RANGER).count(),
        'FOREST_OFFICER': User.objects.filter(profile__role=ROLE_FOREST_OFFICER).count(),
        'MEDICAL_TEAM': User.objects.filter(profile__role=ROLE_MEDICAL_TEAM).count(),
        'RESEARCHER': User.objects.filter(profile__role=ROLE_RESEARCHER).count(),
        'ADMIN': User.objects.filter(profile__role=ROLE_ADMIN).count(),
        'TOTAL': User.objects.count(),
    }

    context = {
        'role_counts': role_counts,
        'rangers': rangers_qs,
        'officers': officers_qs,
        'medical_users': medical_qs,
        'researchers': researchers_qs,
        'admins': admins_qs,
        'active_role': active_role,
        'q': q,
        'total_users': role_counts['TOTAL'],
    }
    return render(request, 'admin_panel/users_overview.html', context)


@login_required
@user_passes_test(is_admin_check)
def admin_medical_records(request):
    """
    Read-only view of all veterinary medical cases in the system.
    Supports filtering by status, rehabilitation stage, priority, date range, and keyword search.
    """
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'ALL')
    stage_filter = request.GET.get('stage', 'ALL')
    priority_filter = request.GET.get('priority', 'ALL')
    from_date = request.GET.get('from_date', '').strip()
    to_date = request.GET.get('to_date', '').strip()
    sort_by = request.GET.get('sort', 'newest')

    cases = MedicalCase.objects.all().select_related(
        'incident', 'bustard', 'assigned_team', 'assigned_team__profile', 'created_by'
    )

    if q:
        cases = cases.filter(
            Q(case_id__icontains=q) |
            Q(incident__incident_id__icontains=q) |
            Q(bustard__tag_id__icontains=q) |
            Q(condition_summary__icontains=q) |
            Q(diagnosis__icontains=q) |
            Q(assigned_team__username__icontains=q) |
            Q(assigned_team__first_name__icontains=q) |
            Q(assigned_team__last_name__icontains=q)
        )

    if status_filter != 'ALL':
        cases = cases.filter(status=status_filter)

    if stage_filter != 'ALL':
        cases = cases.filter(rehabilitation_stage=stage_filter)

    if priority_filter != 'ALL':
        cases = cases.filter(priority=priority_filter)

    dt_from, dt_to, date_err = parse_date_range_safely(from_date, to_date)
    if date_err:
        messages.error(request, date_err)
    elif dt_from or dt_to:
        cases = filter_datetime_range(cases, 'created_at', dt_from, dt_to)

    if sort_by == 'oldest':
        cases = cases.order_by('created_at')
    elif sort_by == 'priority':
        cases = cases.order_by('priority', '-created_at')
    elif sort_by == 'status':
        cases = cases.order_by('status', '-created_at')
    else:
        cases = cases.order_by('-created_at')

    total_count = MedicalCase.objects.count()
    filtered_count = cases.count()

    paginator = Paginator(cases, 20)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        'page_obj': page_obj,
        'cases': page_obj.object_list,
        'total_count': total_count,
        'filtered_count': filtered_count,
        'q': q,
        'status_filter': status_filter,
        'stage_filter': stage_filter,
        'priority_filter': priority_filter,
        'from_date': from_date,
        'to_date': to_date,
        'sort_by': sort_by,
        'status_choices': MedicalCase.STATUS_CHOICES,
        'stage_choices': MedicalCase.STAGE_CHOICES,
        'priority_choices': MedicalCase.PRIORITY_CHOICES,
    }
    return render(request, 'admin_panel/medical_records.html', context)


@login_required
@user_passes_test(is_admin_check)
def admin_officer_records(request):
    """
    Read-only view of Forest Officer operational records and managed incidents.
    Displays verified incidents, operational actions, dispatched patrols, and verification notes.
    """
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'ALL')
    priority_filter = request.GET.get('priority', 'ALL')
    category_filter = request.GET.get('category', 'ALL')
    officer_id = request.GET.get('officer_id', 'ALL')
    from_date = request.GET.get('from_date', '').strip()
    to_date = request.GET.get('to_date', '').strip()
    sort_by = request.GET.get('sort', 'newest')

    incidents = Incident.objects.all().select_related(
        'reporter', 'reporter__profile', 'verified_by', 'verified_by__profile',
        'location', 'location__zone', 'bustard'
    ).prefetch_related('assignments', 'assignments__assigned_ranger')

    if q:
        incidents = incidents.filter(
            Q(incident_id__icontains=q) |
            Q(description__icontains=q) |
            Q(verification_notes__icontains=q) |
            Q(reporter__username__icontains=q) |
            Q(verified_by__username__icontains=q) |
            Q(verified_by__first_name__icontains=q) |
            Q(verified_by__last_name__icontains=q) |
            Q(bustard__tag_id__icontains=q)
        )

    if status_filter != 'ALL':
        incidents = incidents.filter(status=status_filter)

    if priority_filter != 'ALL':
        incidents = incidents.filter(priority=priority_filter)

    if category_filter != 'ALL':
        incidents = incidents.filter(category=category_filter)

    if officer_id != 'ALL':
        if officer_id == 'UNVERIFIED':
            incidents = incidents.filter(verified_by__isnull=True)
        else:
            incidents = incidents.filter(verified_by_id=officer_id)

    dt_from, dt_to, date_err = parse_date_range_safely(from_date, to_date)
    if date_err:
        messages.error(request, date_err)
    elif dt_from or dt_to:
        incidents = filter_datetime_range(incidents, 'reported_at', dt_from, dt_to)

    if sort_by == 'oldest':
        incidents = incidents.order_by('reported_at')
    elif sort_by == 'priority':
        incidents = incidents.order_by('priority', '-reported_at')
    elif sort_by == 'status':
        incidents = incidents.order_by('status', '-reported_at')
    else:
        incidents = incidents.order_by('-reported_at')

    total_count = Incident.objects.count()
    filtered_count = incidents.count()

    officers = User.objects.filter(profile__role=ROLE_FOREST_OFFICER).order_by('first_name', 'username')

    paginator = Paginator(incidents, 20)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    context = {
        'page_obj': page_obj,
        'incidents': page_obj.object_list,
        'total_count': total_count,
        'filtered_count': filtered_count,
        'officers': officers,
        'q': q,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'category_filter': category_filter,
        'officer_id': officer_id,
        'from_date': from_date,
        'to_date': to_date,
        'sort_by': sort_by,
        'status_choices': Incident.STATUS_CHOICES,
        'priority_choices': Incident.PRIORITY_CHOICES,
        'category_choices': Incident.CATEGORY_CHOICES,
    }
    return render(request, 'admin_panel/officer_records.html', context)

@login_required
@user_passes_test(is_admin_check)
def admin_users(request):
    users = User.objects.all().select_related('profile')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_user':
            username = request.POST.get('username', '').strip()
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '')
            role = request.POST.get('role', 'RANGER')
            first_name = request.POST.get('first_name', '').strip()
            last_name = request.POST.get('last_name', '').strip()
            phone_number = request.POST.get('phone_number', '').strip()
            zone_id = request.POST.get('assigned_zone')

            if not username:
                messages.error(request, "Username is required.")
                return redirect('admin_users')

            u_err = validate_username(username)
            if u_err:
                messages.error(request, u_err)
                return redirect('admin_users')

            if User.objects.filter(username__iexact=username).exists():
                messages.error(request, f"Username '{username}' is already taken.")
                return redirect('admin_users')

            if password and len(password) < 6:
                messages.error(request, "Temporary password must be at least 6 characters long.")
                return redirect('admin_users')

            if role == ROLE_ADMIN or role not in dict(ROLE_CHOICES).keys():
                messages.error(request, "Cannot assign System Administrator or invalid role.")
                return redirect('admin_users')

            if email:
                e_err = validate_email_address(email)
                if e_err:
                    messages.error(request, f"Email: {e_err}")
                    return redirect('admin_users')
                if User.objects.filter(email__iexact=email).exists():
                    messages.error(request, f"Email '{email}' is already registered to another account.")
                    return redirect('admin_users')

            if phone_number:
                p_err = validate_indian_mobile(phone_number)
                if p_err:
                    messages.error(request, f"Phone Number: {p_err}")
                    return redirect('admin_users')

            assigned_zone = None
            if zone_id:
                try:
                    assigned_zone = ConservationZone.objects.get(id=zone_id)
                except (ConservationZone.DoesNotExist, ValueError):
                    messages.error(request, "Selected Conservation Zone does not exist.")
                    return redirect('admin_users')

            # Use password if provided or auto-generate secure random initial password
            initial_password = password if password else secrets.token_urlsafe(24)

            new_user = User.objects.create_user(
                username=username,
                email=email,
                password=initial_password,
                first_name=first_name,
                last_name=last_name
            )
            profile, created = UserProfile.objects.get_or_create(user=new_user)
            profile.role = role
            profile.badge_number = generate_batch_number(role)
            profile.phone_number = phone_number
            profile.assigned_zone = assigned_zone
            profile.force_password_change = True
            profile.save()

            log_activity(request.user, "CREATE", f"Admin created user {new_user.username} with role {role}", model_name="User", object_id=new_user.id, request=request)

            # Generate secure, expiring password setup link for the user
            uid = urlsafe_base64_encode(force_bytes(new_user.pk))
            token = default_token_generator.make_token(new_user)
            setup_url = f"{request.scheme}://{request.get_host()}/reset/{uid}/{token}/"

            email_sent = False
            if email:
                subject = "Welcome to Bustard Beacon — Account Setup Instructions"
                message = (
                    f"Hello {new_user.get_full_name() or new_user.username},\n\n"
                    f"An official staff account has been created for you on the Bustard Beacon Conservation Platform.\n\n"
                    f"Username: {new_user.username}\n"
                    f"Assigned Role: {profile.get_role_display()}\n\n"
                    f"To activate your account and configure your secure personal password, please click the secure link below:\n"
                    f"{setup_url}\n\n"
                    f"This link is cryptographically protected and valid for 24 hours.\n\n"
                    f"Regards,\n"
                    f"Bustard Beacon Administration"
                )
                mailers_config = getattr(settings, 'MAILERS', {}).get('default', {})
                backend_name = mailers_config.get('BACKEND', '') or getattr(settings, 'EMAIL_BACKEND', '')
                is_console = 'console' in backend_name.lower()
                try:
                    send_mail(
                        subject=subject,
                        message=message,
                        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', None),
                        recipient_list=[email],
                        fail_silently=False,
                    )
                    if not is_console:
                        email_sent = True
                except Exception as mail_err:
                    logger.warning(f"Failed to deliver account setup email to {email}: {mail_err}")

            if email and email_sent:
                messages.success(request, f"User '{new_user.username}' created successfully. A secure password setup link has been sent to {email}.")
            elif email:
                messages.success(request, f"User '{new_user.username}' created successfully with role {profile.get_role_display()}.")
                messages.info(request, f"Email service is in local/console mode or SMTP is unconfigured. Secure account setup link (valid 24h): {setup_url}")
            else:
                messages.success(request, f"User '{new_user.username}' created successfully with role {profile.get_role_display()}.")
                messages.info(request, f"Secure password setup link (valid 24h): {setup_url}")

        elif action == 'update_role':
            user_id = request.POST.get('user_id')
            new_role = request.POST.get('role')
            if new_role == ROLE_ADMIN or new_role not in dict(ROLE_CHOICES).keys():
                messages.error(request, "Cannot assign System Administrator or invalid role.")
                return redirect('admin_users')
            
            try:
                target_user = User.objects.get(id=user_id)
            except (User.DoesNotExist, ValueError, TypeError):
                messages.error(request, "Invalid or non-existent user identifier.")
                return redirect('admin_users')

            profile, created = UserProfile.objects.get_or_create(user=target_user)
            if profile.role != new_role:
                profile.role = new_role
                profile.badge_number = generate_batch_number(new_role)
                profile.save()

                log_activity(request.user, "UPDATE", f"Admin updated user {target_user.username} role to {new_role}", model_name="UserProfile", object_id=profile.id, request=request)
                messages.success(request, f"Role for {target_user.username} updated to {profile.get_role_display()}. New Badge Number: {profile.badge_number}")
            else:
                messages.info(request, f"User {target_user.username} is already assigned to the {profile.get_role_display()} role.")

        elif action == 'toggle_status':
            user_id = request.POST.get('user_id')
            try:
                target_user = User.objects.get(id=user_id)
            except (User.DoesNotExist, ValueError, TypeError):
                messages.error(request, "Invalid or non-existent user identifier.")
                return redirect('admin_users')

            if hasattr(target_user, 'profile') and target_user.profile.role == ROLE_ADMIN:
                messages.error(request, "You cannot deactivate or reactivate a System Administrator account.")
            elif target_user.id == request.user.id:
                messages.error(request, "You cannot deactivate your own account.")
            else:
                target_user.is_active = not target_user.is_active
                target_user.save()
                status_word = "reactivated" if target_user.is_active else "deactivated"
                log_activity(request.user, "UPDATE", f"Admin {status_word} user {target_user.username}", model_name="User", object_id=target_user.id, request=request)
                messages.success(request, f"User {target_user.username} has been {status_word}.")
                
        elif action == 'delete_user':
            user_id = request.POST.get('user_id')
            try:
                target_user = User.objects.get(id=user_id)
            except (User.DoesNotExist, ValueError, TypeError):
                messages.error(request, "Invalid or non-existent user identifier.")
                return redirect('admin_users')

            if hasattr(target_user, 'profile') and target_user.profile.role == ROLE_ADMIN:
                messages.error(request, "You cannot delete a System Administrator account.")
            elif target_user.id == request.user.id:
                messages.error(request, "You cannot delete your own account.")
            else:
                username = target_user.username
                target_user.delete()
                log_activity(request.user, "DELETE", f"Admin deleted user {username}", model_name="User", object_id=str(user_id), request=request)
                messages.success(request, f"User {username} has been permanently deleted.")

        return redirect('admin_users')

    assignable_roles = [r for r in ROLE_CHOICES if r[0] != ROLE_ADMIN]
    
    context = {
        'users': users,
        'role_choices': ROLE_CHOICES,
        'assignable_roles': assignable_roles,
        'zones': ConservationZone.objects.filter(is_active=True)
    }
    return render(request, 'admin_panel/users.html', context)

@login_required
@user_passes_test(is_admin_check)
def admin_birds(request):
    birds = Bustard.objects.all().select_related('death_record', 'birth_record')

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_bird':
            tag_id = request.POST.get('tag_id', '').strip().upper()
            name = request.POST.get('name', '').strip()
            sex = request.POST.get('sex', 'UNKNOWN')
            age_class = request.POST.get('age_class', 'ADULT')
            health_status = request.POST.get('health_status', 'HEALTHY')
            notes = request.POST.get('nesting_notes', '').strip()
            
            species_select = request.POST.get('species_select', 'Great Indian Bustard')
            if species_select == 'Other':
                species = request.POST.get('species_custom', '').strip()
            else:
                species = species_select

            if not tag_id:
                messages.error(request, "Bird Tag ID is required.")
                return redirect('admin_birds')

            if Bustard.objects.filter(tag_id__iexact=tag_id).exists():
                messages.error(request, f"Tag ID '{tag_id}' already exists.")
                return redirect('admin_birds')

            # Validate uploaded images
            uploaded_images = request.FILES.getlist('bird_images')
            for f in uploaded_images:
                img_err = validate_uploaded_image(f)
                if img_err:
                    messages.error(request, f"Image upload error: {img_err}")
                    return redirect('admin_birds')

            bird = Bustard.objects.create(
                tag_id=tag_id,
                name=name,
                species=species,
                sex=sex,
                age_class=age_class,
                health_status=health_status,
                nesting_notes=notes
            )
            
            for f in uploaded_images:
                from ..models import IncidentImage
                IncidentImage.objects.create(bustard=bird, image=f)
                
            log_activity(request.user, "CREATE", f"Registered new Bustard record {bird.tag_id}", model_name="Bustard", object_id=bird.id, request=request)
            messages.success(request, f"Bustard {bird.tag_id} registered successfully.")

        elif action == 'record_death':
            bird_id = request.POST.get('bird_id')
            cause = request.POST.get('cause_of_death', '').strip()
            death_date = request.POST.get('date_of_death', timezone.now().strftime('%Y-%m-%d'))

            try:
                bird = Bustard.objects.get(id=bird_id)
            except (Bustard.DoesNotExist, ValueError, TypeError):
                messages.error(request, "Invalid or non-existent bird identifier.")
                return redirect('admin_birds')

            if not cause:
                messages.error(request, "Cause of death is required.")
                return redirect('admin_birds')

            d_err = validate_date_string(death_date, "Date of death", allow_future=False)
            if d_err:
                messages.error(request, d_err)
                return redirect('admin_birds')

            bird.health_status = 'DECEASED'
            bird.save()

            DeathRecord.objects.create(
                bustard=bird,
                date_of_death=death_date,
                cause_of_death=cause,
                recorded_by=request.user
            )
            log_activity(request.user, "UPDATE", f"Recorded death of Bustard {bird.tag_id} (Cause: {cause})", model_name="DeathRecord", object_id=bird.id, request=request)
            messages.success(request, f"Death record logged for {bird.tag_id}.")
            
        elif action == 'record_missing':
            bird_id = request.POST.get('bird_id')
            missing_date = request.POST.get('reported_missing_date', timezone.now().strftime('%Y-%m-%d'))
            lat_str = request.POST.get('last_known_latitude', '0.0')
            lng_str = request.POST.get('last_known_longitude', '0.0')
            notes = request.POST.get('notes', '').strip()
            
            try:
                bird = Bustard.objects.get(id=bird_id)
            except (Bustard.DoesNotExist, ValueError, TypeError):
                messages.error(request, "Invalid or non-existent bird identifier.")
                return redirect('admin_birds')

            d_err = validate_date_string(missing_date, "Reported missing date", allow_future=False)
            if d_err:
                messages.error(request, d_err)
                return redirect('admin_birds')

            try:
                lat = float(lat_str) if lat_str else 0.0
                lng = float(lng_str) if lng_str else 0.0
                if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
                    messages.error(request, "Coordinates out of bounds (Latitude: -90..90, Longitude: -180..180).")
                    return redirect('admin_birds')
            except ValueError:
                messages.error(request, "Coordinates must be valid numbers.")
                return redirect('admin_birds')

            bird.health_status = 'MISSING'
            bird.save()
            
            MissingBirdRecord.objects.create(
                bustard=bird,
                reported_missing_date=missing_date,
                last_known_latitude=lat,
                last_known_longitude=lng,
                notes=notes,
                reported_by=request.user
            )
            log_activity(request.user, "UPDATE", f"Recorded missing status for Bustard {bird.tag_id}", model_name="MissingBirdRecord", object_id=bird.id, request=request)
            messages.success(request, f"Missing record logged for {bird.tag_id}.")
            
        elif action == 'record_found':
            bird_id = request.POST.get('bird_id')
            found_date = request.POST.get('found_date', timezone.now().strftime('%Y-%m-%d'))
            lat_str = request.POST.get('found_latitude', '0.0')
            lng_str = request.POST.get('found_longitude', '0.0')
            found_by = request.POST.get('found_by', '').strip()
            notes = request.POST.get('found_notes', '').strip()
            
            try:
                bird = Bustard.objects.get(id=bird_id)
            except (Bustard.DoesNotExist, ValueError, TypeError):
                messages.error(request, "Invalid or non-existent bird identifier.")
                return redirect('admin_birds')

            d_err = validate_date_string(found_date, "Found date", allow_future=False)
            if d_err:
                messages.error(request, d_err)
                return redirect('admin_birds')

            try:
                lat = float(lat_str) if lat_str else 0.0
                lng = float(lng_str) if lng_str else 0.0
                if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lng <= 180.0):
                    messages.error(request, "Coordinates out of bounds (Latitude: -90..90, Longitude: -180..180).")
                    return redirect('admin_birds')
            except ValueError:
                messages.error(request, "Coordinates must be valid numbers.")
                return redirect('admin_birds')

            bird.health_status = 'HEALTHY'
            bird.save()
            
            # Find the active missing record
            missing_record = MissingBirdRecord.objects.filter(bustard=bird, search_status='ACTIVE_SEARCH').last()
            if missing_record:
                missing_record.search_status = 'FOUND'
                missing_record.found_date = found_date
                missing_record.found_latitude = lat
                missing_record.found_longitude = lng
                missing_record.found_by = found_by
                missing_record.found_notes = notes
                missing_record.save()
            
            log_activity(request.user, "UPDATE", f"Recorded found status for Bustard {bird.tag_id}", model_name="MissingBirdRecord", object_id=bird.id, request=request)
            messages.success(request, f"Found record logged for {bird.tag_id}.")
            
        elif action == 'record_birth':
            mother_tag = request.POST.get('mother_tag', '').strip()
            sex = request.POST.get('sex', 'UNKNOWN')
            
            species_select = request.POST.get('species_select', 'Great Indian Bustard')
            if species_select == 'Other':
                species = request.POST.get('species_custom', '').strip()
            else:
                species = species_select
                
            hatch_date = request.POST.get('hatch_date', timezone.now().strftime('%Y-%m-%d'))
            nest_zone_id = request.POST.get('nest_zone')
            notes = request.POST.get('notes', '').strip()
            images = request.FILES.getlist('birth_image')
            
            if not images:
                messages.error(request, "At least one bird image is required for a birth record.")
                return redirect('admin_birds')

            for img in images:
                img_err = validate_uploaded_image(img)
                if img_err:
                    messages.error(request, f"Birth image error: {img_err}")
                    return redirect('admin_birds')

            d_err = validate_date_string(hatch_date, "Hatch date", allow_future=False)
            if d_err:
                messages.error(request, d_err)
                return redirect('admin_birds')
                
            primary_image = images[0]
                
            import uuid
            year = timezone.now().strftime('%Y')
            random_code = str(uuid.uuid4().hex[:5]).upper()
            tag_id = f"GIB-{year}-{random_code}"
            
            bird = Bustard.objects.create(
                tag_id=tag_id,
                name=f"Hatchling of {mother_tag}" if mother_tag else "Unnamed Hatchling",
                sex=sex,
                age_class='JUVENILE',
                health_status='HEALTHY',
                species=species
            )
            
            record = BirthRecord.objects.create(
                bustard=bird,
                hatch_date=hatch_date,
                parent_female_tag=mother_tag,
                notes=notes,
                birth_image=primary_image
            )
            
            from ..models import IncidentImage
            for additional_img in images[1:]:
                IncidentImage.objects.create(bustard=bird, image=additional_img)
            
            if nest_zone_id:
                try:
                    record.nest_zone = ConservationZone.objects.get(id=nest_zone_id)
                    record.save()
                    bird.last_seen_zone = record.nest_zone
                    bird.save()
                except (ConservationZone.DoesNotExist, ValueError):
                    pass
                    
            log_activity(request.user, "CREATE", f"Recorded birth for Bustard {bird.tag_id}", model_name="BirthRecord", object_id=record.id, request=request)
            messages.success(request, f"Birth record logged. Auto-generated ID: {bird.tag_id}.")

        elif action == 'delete_bird':
            bird_id = request.POST.get('bird_id')
            try:
                bird = Bustard.objects.get(id=bird_id)
            except (Bustard.DoesNotExist, ValueError, TypeError):
                messages.error(request, "Invalid or non-existent bird identifier.")
                return redirect('admin_birds')

            tag_id = bird.tag_id
            bird_name = bird.name or "Unnamed"

            # Safe deletion:
            # 1. Preserve incident photos linked to both this bird and an incident
            from ..models import IncidentImage
            IncidentImage.objects.filter(bustard=bird, incident__isnull=False).update(bustard=None)

            # 2. Delete bird record.
            # - Incident (on_delete=SET_NULL): safely preserved
            # - MedicalCase (on_delete=SET_NULL): safely preserved
            # - BustardMovement, BreedingRecord, DeathRecord, MissingBirdRecord: removed
            # - BirthRecord: removed for this specific bird
            bird.delete()

            log_activity(
                request.user,
                "DELETE",
                f"Permanently deleted registered bird {tag_id} ({bird_name}).",
                model_name="Bustard",
                object_id=str(bird_id),
                request=request
            )
            messages.success(request, f"Bird record {tag_id} ({bird_name}) has been permanently deleted.")
            return redirect('admin_birds')

        return redirect('admin_birds')

    birds = Bustard.objects.all().select_related(
        'death_record', 'birth_record', 'last_seen_zone'
    ).prefetch_related('images', 'incidents', 'medical_cases')

    q = request.GET.get('q', '').strip()
    species_filter = request.GET.get('species', 'ALL')
    status_filter = request.GET.get('status', 'ALL')
    zone_filter = request.GET.get('zone', 'ALL')
    sex_filter = request.GET.get('sex', 'ALL')
    sort_by = request.GET.get('sort', 'newest')

    if q:
        birds = birds.filter(
            Q(tag_id__icontains=q) |
            Q(name__icontains=q) |
            Q(species__icontains=q) |
            Q(nesting_notes__icontains=q)
        )

    if species_filter != 'ALL':
        birds = birds.filter(species=species_filter)

    if status_filter != 'ALL':
        birds = birds.filter(health_status=status_filter)

    if zone_filter != 'ALL':
        birds = birds.filter(last_seen_zone_id=zone_filter)

    if sex_filter != 'ALL':
        birds = birds.filter(sex=sex_filter)

    if sort_by == 'oldest':
        birds = birds.order_by('created_at')
    elif sort_by == 'tag_asc':
        birds = birds.order_by('tag_id')
    elif sort_by == 'tag_desc':
        birds = birds.order_by('-tag_id')
    elif sort_by == 'species':
        birds = birds.order_by('species', 'tag_id')
    elif sort_by == 'status':
        birds = birds.order_by('health_status', '-created_at')
    else:
        birds = birds.order_by('-created_at')

    total_count = Bustard.objects.count()
    filtered_count = birds.count()

    species_list = Bustard.objects.values_list('species', flat=True).distinct().order_by('species')

    context = {
        'birds': birds,
        'zones': ConservationZone.objects.filter(is_active=True),
        'species_list': species_list,
        'total_count': total_count,
        'filtered_count': filtered_count,
        'q': q,
        'species_filter': species_filter,
        'status_filter': status_filter,
        'zone_filter': zone_filter,
        'sex_filter': sex_filter,
        'sort_by': sort_by,
        'health_choices': Bustard.HEALTH_CHOICES,
        'sex_choices': Bustard.SEX_CHOICES,
    }
    return render(request, 'admin_panel/birds.html', context)


@login_required
@user_passes_test(is_admin_check)
def admin_audit_logs(request):
    action_filter = request.GET.get('action', 'ALL')
    q = request.GET.get('q', '').strip()
    from_date = request.GET.get('from_date', '').strip()
    to_date = request.GET.get('to_date', '').strip()

    logs = ActivityLog.objects.all().select_related('user', 'user__profile').order_by('-timestamp')

    if action_filter != 'ALL':
        logs = logs.filter(action=action_filter)

    if q:
        logs = logs.filter(
            Q(user_display__icontains=q) |
            Q(model_name__icontains=q) |
            Q(object_id__icontains=q) |
            Q(description__icontains=q) |
            Q(ip_address__icontains=q) |
            Q(user__username__icontains=q)
        )

    dt_from, dt_to, date_err = parse_date_range_safely(from_date, to_date)
    if date_err:
        messages.error(request, date_err)
    elif dt_from or dt_to:
        logs = filter_datetime_range(logs, 'timestamp', dt_from, dt_to)

    total_count = ActivityLog.objects.count()
    filtered_count = logs.count()

    paginator = Paginator(logs, 30)
    page_num = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_num)

    actions = [
        ('LOGIN', 'Login Events'),
        ('LOGOUT', 'Logout Events'),
        ('CREATE', 'Create Records'),
        ('UPDATE', 'Update Records'),
        ('DELETE', 'Delete Records'),
        ('VERIFY', 'Incident Verification'),
        ('ASSIGN', 'Ranger Assignments'),
        ('IMPORT', 'Data Imports'),
        ('REPORT_GEN', 'Report Generation'),
    ]

    context = {
        'page_obj': page_obj,
        'logs': page_obj.object_list,
        'selected_action': action_filter,
        'actions': actions,
        'total_count': total_count,
        'filtered_count': filtered_count,
        'q': q,
        'from_date': from_date,
        'to_date': to_date,
    }
    return render(request, 'admin_panel/audit_logs.html', context)
