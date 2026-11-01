from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from PIL import Image, UnidentifiedImageError
from ..models import (
    Incident, IncidentLocation, IncidentImage, PatrolAssignment,
    Notification, User, ROLE_RANGER, ROLE_FOREST_OFFICER, ROLE_MEDICAL_TEAM,
    UserProfile, MedicalCase, Bustard
)
from ..services.gis_service import detect_zone_for_point
from ..services.weather_service import get_weather_at_coordinates
from ..services.audit_service import log_activity
from django.conf import settings
from django.contrib.auth.decorators import login_required
from ..decorators import role_required
from ..validators import validate_uploaded_document

MAX_INCIDENT_IMAGE_SIZE = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}


def _validate_incident_image(uploaded_file):
    if uploaded_file.size > MAX_INCIDENT_IMAGE_SIZE:
        raise ValidationError('The incident image must be 10 MB or smaller.')
    if uploaded_file.content_type not in ALLOWED_IMAGE_TYPES:
        raise ValidationError('Use a JPEG, PNG, or WEBP image for the incident photo.')

    try:
        image = Image.open(uploaded_file)
        image.verify()
    except (UnidentifiedImageError, OSError):
        raise ValidationError('The uploaded file is not a valid image.')
    finally:
        uploaded_file.seek(0)

@role_required(ROLE_RANGER)
def ranger_field_mode(request):
    """
    Mobile-first field operation interface for Rangers.
    """
    user = request.user
    my_pending_tasks = PatrolAssignment.objects.filter(
        assigned_ranger=user,
        status__in=['PENDING', 'ACCEPTED', 'IN_PROGRESS']
    )

    context = {
        'pending_tasks_count': my_pending_tasks.count(),
        'my_pending_tasks': my_pending_tasks[:3],
    }
    return render(request, 'ranger/field_mode.html', context)

@role_required(ROLE_RANGER)
def report_incident(request):
    """
    Ranger Incident Reporting View:
    Processes live GPS, camera photo, zone detection, and transaction consistency.
    """
    category_preset = request.GET.get('category', 'BIRD_SIGHTING')
    incident_id = request.GET.get('incident_id')
    edit_incident = None
    if incident_id:
        edit_incident = get_object_or_404(Incident, id=incident_id, reporter=request.user)
        category_preset = edit_incident.category

    if request.method == 'POST':
        incident_id = request.POST.get('incident_id')
        category = request.POST.get('category', 'BIRD_SIGHTING')
        description = request.POST.get('description', '').strip()
        latitude_raw = request.POST.get('latitude')
        longitude_raw = request.POST.get('longitude')
        accuracy_raw = request.POST.get('accuracy')
        custom_category_name = request.POST.get('custom_category', '').strip()
        priority = request.POST.get('priority')
        bird_id = request.POST.get('bird_id', '').strip()
        send_medical = (request.POST.get('send_medical_alert') or '').strip().lower()
        medical_team_id = request.POST.get('medical_team_id')
        photo_files = request.FILES.getlist('photo_upload')
        captured_image_data = request.POST.get('captured_image_data')

        if captured_image_data and not photo_files:
            import base64
            from django.core.files.uploadedfile import SimpleUploadedFile
            try:
                format_header, imgstr = captured_image_data.split(';base64,')
                content_type = format_header.split(':')[1]
                ext = content_type.split('/')[-1]
                photo_files.append(SimpleUploadedFile(
                    name=f'captured_photo.{ext}',
                    content=base64.b64decode(imgstr),
                    content_type=content_type
                ))
            except Exception:
                pass

        def _get_err_context():
            return {
                'category_preset': category,
                'edit_incident': edit_incident,
                'medical_teams': UserProfile.objects.filter(role=ROLE_MEDICAL_TEAM, user__is_active=True),
                'registered_birds': Bustard.objects.exclude(health_status='DECEASED').order_by('tag_id'),
                'entered_description': description,
                'entered_custom_category': custom_category_name,
                'entered_latitude': latitude_raw or '',
                'entered_longitude': longitude_raw or '',
                'entered_accuracy': accuracy_raw or '',
                'selected_bird_id': bird_id or '',
                'send_medical_preset': send_medical == 'true',
                'selected_medical_team_id': medical_team_id or '',
                'google_maps_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', ''),
            }

        if not description:
            messages.error(request, "Please provide a description of the observation/incident.")
            return render(request, 'ranger/report_incident.html', _get_err_context())

        if not latitude_raw or not longitude_raw:
            messages.error(request, "GPS coordinates are required. Please enable location services.")
            return render(request, 'ranger/report_incident.html', _get_err_context())

        try:
            latitude = float(latitude_raw)
            longitude = float(longitude_raw)
            accuracy = float(accuracy_raw) if accuracy_raw else None
        except (TypeError, ValueError):
            messages.error(request, "Invalid GPS coordinate format received.")
            return render(request, 'ranger/report_incident.html', _get_err_context())

        valid_categories = {value for value, _label in Incident.CATEGORY_CHOICES}
        if category not in valid_categories:
            messages.error(request, "Please select a valid incident category.")
            category = 'BIRD_SIGHTING'
            return render(request, 'ranger/report_incident.html', _get_err_context())

        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            messages.error(request, "GPS coordinates are outside the valid latitude/longitude range.")
            return render(request, 'ranger/report_incident.html', _get_err_context())

        if accuracy is not None and (accuracy < 0 or accuracy > 100000):
            messages.error(request, "GPS accuracy is invalid. Please refresh the device location.")
            return render(request, 'ranger/report_incident.html', _get_err_context())

        if photo_files:
            for photo_file in photo_files:
                try:
                    _validate_incident_image(photo_file)
                except ValidationError as error:
                    messages.error(request, error.message)
                    return render(request, 'ranger/report_incident.html', _get_err_context())
        
        # Automatically assign CRITICAL priority for medical incidents.
        # Rangers no longer manually select priority.
        if category in ['INJURED_BIRD', 'SICK_BIRD'] or send_medical == 'true':
            priority = 'CRITICAL'
        else:
            priority = 'MEDIUM'

        bustard = None
        bird_id_text = request.POST.get('bird_id', '').strip()
        if bird_id_text and bird_id_text.upper() != 'UNKNOWN':
            # Authoritative backend validation against database
            found_bird = Bustard.objects.filter(tag_id__iexact=bird_id_text).first()
            if not found_bird:
                messages.error(request, f"The selected Bird ID '{bird_id_text}' does not exist in the database. Please select a registered living bird or 'Unknown Bird'.")
                return render(request, 'ranger/report_incident.html', _get_err_context())
            elif found_bird.health_status == 'DECEASED':
                messages.error(request, f"The selected bird ({found_bird.tag_id}) is confirmed deceased and cannot be assigned to new field reports.")
                return render(request, 'ranger/report_incident.html', _get_err_context())
            else:
                bustard = found_bird
        else:
            # Explicit Unknown Bird selected or left blank
            bustard = None

        # Atomic Transaction for Data Consistency
        try:
            with transaction.atomic():
                if incident_id:
                    incident = get_object_or_404(Incident, id=incident_id, reporter=request.user)
                    incident.category = category
                    incident.custom_category_name = custom_category_name if category == 'OTHER' else ''
                    incident.description = description
                    incident.priority = priority
                    incident.status = 'PENDING'
                    incident.bustard = bustard
                    incident.save()

                    assignments = PatrolAssignment.objects.filter(incident=incident, assigned_ranger=request.user, status='PENDING', instructions__startswith="Information Request")
                    for a in assignments:
                        a.status = 'COMPLETED'
                        a.completed_at = timezone.now()
                        a.save()

                    target_officer = incident.verified_by if incident.verified_by else User.objects.filter(profile__role=ROLE_FOREST_OFFICER).first()
                    if target_officer:
                        Notification.objects.create(
                            recipient=target_officer,
                            title=f"Incident Updated: {incident.incident_id}",
                            message=f"Ranger {request.user.username} has updated the requested information.",
                            category="INCIDENT_ALERT",
                            link_url=f"/officer/incidents/{incident.id}/"
                        )
                else:
                    # 1. Create Incident
                    incident = Incident.objects.create(
                        category=category,
                        custom_category_name=custom_category_name if category == 'OTHER' else '',
                        description=description,
                        priority=priority,
                        status='PENDING',
                        reporter=request.user,
                        reported_at=timezone.now(),
                        data_source='FIELD_REPORT',
                        bustard=bustard
                    )

                # 2. GIS Zone Detection & Weather Retrieval
                zone = detect_zone_for_point(latitude, longitude)
                weather = get_weather_at_coordinates(latitude, longitude)

                # 3. Create Incident Location
                location = IncidentLocation.objects.create(
                    incident=incident,
                    latitude=latitude,
                    longitude=longitude,
                    accuracy_meters=accuracy,
                    zone=zone,
                    weather_temperature_c=weather.get('temperature_c'),
                    weather_condition=weather.get('condition'),
                    weather_wind_speed_kmh=weather.get('wind_speed_kmh')
                )

                # 4. Save Image if Provided
                if photo_files:
                    for photo_file in photo_files:
                        IncidentImage.objects.create(
                            incident=incident,
                            image=photo_file,
                            caption=f"Field photo captured by {request.user.username}"
                        )

                # 5. Dispatch Notifications to Forest Officers
                # Prefer responsible officer for the zone
                target_officer = None
                if zone and zone.responsible_officer:
                    target_officer = zone.responsible_officer
                
                officers_to_notify = [target_officer] if target_officer else User.objects.filter(profile__role=ROLE_FOREST_OFFICER)
                
                for officer in officers_to_notify:
                    Notification.objects.create(
                        recipient=officer,
                        title=f"New Field Incident: {incident.get_category_display()}",
                        message=f"Ranger {request.user.username} reported a {priority} incident in {zone.name if zone else 'Nannaj Region'}.",
                        category="INCIDENT_ALERT",
                        link_url=f"/officer/incidents/{incident.id}/"
                    )

                # 5.5 Check for Medical Alert
                if send_medical == 'true' and medical_team_id and category in ['INJURED_BIRD', 'SICK_BIRD']:
                    try:
                        assigned_team = User.objects.get(id=medical_team_id, profile__role=ROLE_MEDICAL_TEAM, is_active=True)
                        med_case = MedicalCase.objects.create(
                            incident=incident,
                            bustard=bustard,
                            condition_summary=f"Emergency Alert: {incident.get_category_display()}",
                            symptoms=incident.description,
                            status='ACTIVE',
                            priority='CRITICAL',
                            created_by=request.user,
                            assigned_team=assigned_team
                        )
                        Notification.objects.create(
                            recipient=assigned_team,
                            title=f"URGENT: Medical Alert from Field",
                            message=f"Ranger {request.user.username} requested immediate medical treatment.",
                            category="MEDICAL_ALERT",
                            link_url=f"/medical/cases/{med_case.id}/"
                        )
                    except User.DoesNotExist:
                        pass # Team might be invalid or deactivated

                if incident_id:
                    log_activity(
                        request.user,
                        "UPDATE",
                        f"Updated incident {incident.incident_id} in response to request",
                        model_name="Incident",
                        object_id=incident.id,
                        request=request
                    )
                    messages.success(request, f"Incident {incident.incident_id} updated successfully!")
                    return redirect('ranger_assignments')
                else:
                    log_activity(
                        request.user,
                        "CREATE",
                        f"Reported incident {incident.incident_id} ({category}) in zone '{zone.name if zone else 'N/A'}'",
                        model_name="Incident",
                        object_id=incident.id,
                        request=request
                    )
                    messages.success(request, f"Incident {incident.incident_id} submitted successfully! Assigned Priority: {priority}.")
                    return redirect('ranger_incidents')

        except Exception:
            messages.error(request, "The incident could not be saved. Please retry, or contact an administrator if the problem continues.")

    medical_teams = UserProfile.objects.filter(role=ROLE_MEDICAL_TEAM, user__is_active=True)
    registered_birds = Bustard.objects.exclude(health_status='DECEASED').order_by('tag_id')
    
    context = {
        'category_preset': category_preset,
        'medical_teams': medical_teams,
        'registered_birds': registered_birds,
        'edit_incident': edit_incident,
        'google_maps_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', ''),
    }
    return render(request, 'ranger/report_incident.html', context)

import json
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

@login_required
@csrf_exempt
def api_update_location(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            lat = data.get('latitude')
            lng = data.get('longitude')
            
            profile = request.user.profile if hasattr(request.user, 'profile') else None
            if profile and profile.role == ROLE_RANGER:
                profile.current_latitude = lat
                profile.current_longitude = lng
                profile.location_updated_at = timezone.now()
                profile.save()
                return JsonResponse({'status': 'success'})
            return JsonResponse({'status': 'error', 'message': 'Unauthorized role'}, status=403)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

@role_required(ROLE_RANGER)
def ranger_incidents(request):
    incidents = Incident.objects.filter(reporter=request.user)
    
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    
    from datetime import datetime, time
    dt_from = None
    dt_to = None

    if date_from:
        try:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d").date()
        except ValueError:
            pass

    if date_to:
        try:
            dt_to = datetime.strptime(date_to, "%Y-%m-%d").date()
        except ValueError:
            pass

    if dt_from and dt_to and dt_from > dt_to:
        messages.error(request, "Start date cannot be later than end date.")
    else:
        if dt_from:
            incidents = incidents.filter(reported_at__gte=timezone.make_aware(datetime.combine(dt_from, time.min)))
        if dt_to:
            incidents = incidents.filter(reported_at__lte=timezone.make_aware(datetime.combine(dt_to, time.max)))
        
    from django.conf import settings
    context = {
        'incidents': incidents,
        'date_from': date_from,
        'date_to': date_to,
        'google_maps_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', ''),
    }
    return render(request, 'ranger/incidents.html', context)

@role_required(ROLE_RANGER)
def ranger_assignments(request):
    assignments = PatrolAssignment.objects.filter(assigned_ranger=request.user)
    
    pending_assignments = assignments.exclude(status='COMPLETED').order_by('-assigned_at')
    completed_assignments = assignments.filter(status='COMPLETED').order_by('-completed_at')

    if request.method == 'POST':
        assignment_id = request.POST.get('assignment_id')
        new_status = request.POST.get('status')
        notes = request.POST.get('ranger_notes', '').strip()

        assignment = get_object_or_404(PatrolAssignment, id=assignment_id, assigned_ranger=request.user)
        
        # Valid statuses restricted to the required three options mapped to model values
        # Pending -> PENDING
        # Patrol in Progress -> IN_PROGRESS
        # Complete -> COMPLETED
        valid_frontend_statuses = {'PENDING', 'IN_PROGRESS', 'COMPLETED'}
        if new_status not in valid_frontend_statuses:
            messages.error(request, "Invalid assignment status.")
            return redirect('ranger_assignments')

        assignment.status = new_status
        if notes:
            assignment.ranger_notes = notes
        if new_status == 'COMPLETED':
            assignment.completed_at = timezone.now()

        assignment.save()
        
        evidence_files = request.FILES.getlist('evidence_files')
        if evidence_files:
            from ..models import AssignmentAttachment
            for f in evidence_files:
                try:
                    validate_uploaded_document(f)
                except ValidationError as err:
                    messages.error(request, err.message)
                    return redirect('ranger_assignments')
                AssignmentAttachment.objects.create(assignment=assignment, file=f)
                
        log_activity(request.user, "UPDATE", f"Ranger updated assignment #{assignment.id} status to {new_status}", model_name="PatrolAssignment", object_id=assignment.id, request=request)
        messages.success(request, f"Assignment status updated to {new_status}.")
        return redirect('ranger_assignments')

    return render(request, 'ranger/assignments.html', {
        'pending_assignments': pending_assignments,
        'completed_assignments': completed_assignments
    })
