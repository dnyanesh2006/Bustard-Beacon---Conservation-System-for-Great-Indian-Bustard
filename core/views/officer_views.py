from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from ..models import (
    Incident, PatrolAssignment, MedicalCase, ConservationZone, TourismRestriction, TourismRecord,
    Notification, User, ROLE_RANGER, ROLE_MEDICAL_TEAM, ROLE_FOREST_OFFICER, ROLE_ADMIN, UserProfile, MedicalEquipment
)
from ..services.gis_service import calculate_high_risk_zones
from ..services.audit_service import log_activity
from ..decorators import role_required
from .report_views import parse_date_range_safely, filter_datetime_range

@role_required(ROLE_FOREST_OFFICER)
def officer_dashboard(request):
    """
    Forest Officer Command Center Dashboard
    """
    pending_incidents = Incident.objects.filter(status='PENDING')
    critical_incidents = Incident.objects.filter(priority='CRITICAL', status__in=['PENDING', 'VERIFIED'])
    active_assignments = PatrolAssignment.objects.filter(status__in=['PENDING', 'ACCEPTED', 'IN_PROGRESS'])
    active_medical = MedicalCase.objects.filter(status__in=['ACTIVE', 'UNDER_TREATMENT'])
    recent_medical_updates = MedicalCase.objects.all().order_by('-updated_at')[:3]

    risk_zones = calculate_high_risk_zones()

    active_tourism_count = TourismRecord.objects.filter(status='APPROVED').count()
    visitor_sum = TourismRecord.objects.filter(status='APPROVED').aggregate(total=Sum('visitor_count'))['total'] or 0
    recent_tourism = TourismRecord.objects.all().select_related('zone').order_by('-created_at')[:4]

    context = {
        'pending_count': pending_incidents.count(),
        'critical_count': critical_incidents.count(),
        'active_assignments_count': active_assignments.count(),
        'active_medical_count': active_medical.count(),
        'active_tourism_count': active_tourism_count,
        'total_visitors_scheduled': visitor_sum,
        'recent_tourism': recent_tourism,
        'pending_incidents': pending_incidents[:5],
        'critical_incidents': critical_incidents[:5],
        
        'all_pending_incidents': pending_incidents,
        'all_critical_incidents': critical_incidents,
        'active_assignments': active_assignments,
        'active_medical': active_medical,
        'recent_medical_updates': recent_medical_updates,

        'risk_zones': risk_zones,
    }
    return render(request, 'officer/dashboard.html', context)

@role_required(ROLE_FOREST_OFFICER)
def officer_incidents(request):
    status_filter = request.GET.get('status', 'ALL')
    priority_filter = request.GET.get('priority', 'ALL')

    incidents = Incident.objects.all().select_related('reporter', 'location', 'location__zone')

    if status_filter != 'ALL':
        incidents = incidents.filter(status=status_filter)
    if priority_filter != 'ALL':
        incidents = incidents.filter(priority=priority_filter)

    context = {
        'incidents': incidents,
        'selected_status': status_filter,
        'selected_priority': priority_filter,
    }
    return render(request, 'officer/incidents.html', context)

@role_required(ROLE_FOREST_OFFICER)
def officer_incident_detail(request, incident_id):
    incident = get_object_or_404(Incident.objects.select_related('reporter', 'location', 'location__zone'), id=incident_id)
    available_rangers = User.objects.filter(profile__role=ROLE_RANGER)
    existing_assignments = PatrolAssignment.objects.filter(incident=incident)

    if request.method == 'POST':
        action_type = request.POST.get('action_type')

        if action_type == 'verify_incident':
            new_status = request.POST.get('status')
            new_priority = request.POST.get('priority')
            notes = request.POST.get('verification_notes', '').strip()
            ranger_id = request.POST.get('ranger_id')

            incident.status = new_status
            incident.priority = new_priority
            incident.verified_by = request.user
            incident.verified_at = timezone.now()
            incident.verification_notes = notes
            incident.save()

            log_activity(request.user, "VERIFY", f"Officer updated incident {incident.incident_id} status to {new_status} and priority to {new_priority}", model_name="Incident", object_id=incident.id, request=request)

            if new_status == 'MORE_INFO' or ranger_id:
                target_ranger = None
                instruction_prefix = ""
                notif_title = ""
                notif_message = ""
                
                if new_status == 'MORE_INFO':
                    # If they explicitly chose a different ranger while requesting info, that's weird but possible.
                    # Usually it goes back to the reporter.
                    target_ranger = get_object_or_404(User, id=ranger_id) if ranger_id else incident.reporter
                    instruction_prefix = "Information Request: "
                    notif_title = f"Information Requested: Incident {incident.incident_id}"
                    notif_message = f"Officer {request.user.username} requested more info: {notes}"
                else:
                    target_ranger = get_object_or_404(User, id=ranger_id)
                    instruction_prefix = ""
                    notif_title = f"Patrol Task Assigned: {incident.incident_id}"
                    notif_message = f"Officer {request.user.username} assigned you a patrol task."
                
                PatrolAssignment.objects.create(
                    incident=incident,
                    assigned_ranger=target_ranger,
                    assigned_by=request.user,
                    instructions=f"{instruction_prefix}{notes}" if notes else "General Patrol Assignment",
                    status='PENDING'
                )
                Notification.objects.create(
                    recipient=target_ranger,
                    title=notif_title,
                    message=notif_message,
                    category="PATROL_ASSIGNMENT",
                    link_url="/ranger/assignments/"
                )
                messages.success(request, f"Task successfully assigned to Ranger {target_ranger.username}.")
                log_activity(request.user, "ASSIGN", f"Assigned incident {incident.incident_id} to Ranger {target_ranger.username}", model_name="PatrolAssignment", object_id=incident.id, request=request)

            messages.success(request, f"Incident {incident.incident_id} verification updated.")
            return redirect('officer_incident_detail', incident_id=incident.id)

        elif action_type == 'assign_medical':
            medical_team_id = request.POST.get('medical_team_id')
            priority = request.POST.get('priority', 'MEDIUM')
            
            med_case = MedicalCase.objects.filter(incident=incident).first()
            
            assigned_team = None
            if medical_team_id:
                try:
                    assigned_team = User.objects.get(id=medical_team_id, profile__role=ROLE_MEDICAL_TEAM, profile__availability_status='AVAILABLE', is_active=True)
                except User.DoesNotExist:
                    messages.error(request, "Selected Medical Team is invalid or currently unavailable.")
                    return redirect('officer_incident_detail', incident_id=incident.id)

            if med_case:
                med_case.assigned_team = assigned_team
                med_case.priority = priority
                med_case.save()
                if assigned_team:
                    action_msg = f"Reassigned medical case {med_case.case_id} to {assigned_team.username}"
                else:
                    action_msg = f"Updated medical case {med_case.case_id} priority to {priority} (Unassigned)"
            else:
                med_case = MedicalCase.objects.create(
                    incident=incident,
                    bustard=incident.bustard,
                    condition_summary=f"Emergency rescue: {incident.get_category_display()}",
                    symptoms=incident.description,
                    rehabilitation_stage='ICU',
                    status='ACTIVE',
                    priority=priority,
                    created_by=request.user,
                    assigned_team=assigned_team
                )
                if assigned_team:
                    action_msg = f"Created medical case {med_case.case_id} and assigned to {assigned_team.username}"
                else:
                    action_msg = f"Created unassigned medical case {med_case.case_id} (Priority: {priority})"

            if assigned_team:
                Notification.objects.create(
                    recipient=assigned_team,
                    title=f"Medical Assignment: {med_case.case_id}",
                    message=f"Officer {request.user.username} assigned you to a medical case for incident {incident.incident_id}.",
                    category="MEDICAL_ALERT",
                    link_url=f"/medical/cases/{med_case.id}/"
                )
                messages.success(request, f"Medical Team {assigned_team.get_full_name() or assigned_team.username} assigned successfully.")
            else:
                messages.success(request, f"Medical case priority updated to {priority}. Pending team assignment.")
                
            log_activity(request.user, "ASSIGN", action_msg, model_name="MedicalCase", object_id=med_case.id, request=request)
            return redirect('officer_incident_detail', incident_id=incident.id)

    medical_teams = list(UserProfile.objects.filter(role=ROLE_MEDICAL_TEAM, user__is_active=True))
    if hasattr(incident, 'location') and incident.location.latitude is not None:
        import math
        def sort_key(team):
            if team.availability_status == 'AVAILABLE' and team.current_latitude is not None:
                return math.sqrt((team.current_latitude - incident.location.latitude)**2 + (team.current_longitude - incident.location.longitude)**2)
            return float('inf')
        medical_teams.sort(key=sort_key)
        
    medical_case = MedicalCase.objects.filter(incident=incident).first()
    medical_equipment = MedicalEquipment.objects.all()

    context = {
        'incident': incident,
        'available_rangers': available_rangers,
        'existing_assignments': existing_assignments,
        'medical_teams': medical_teams,
        'medical_case': medical_case,
        'medical_equipment': medical_equipment,
    }
    return render(request, 'officer/incident_detail.html', context)

@role_required(ROLE_FOREST_OFFICER)
def officer_zones(request):
    zones = ConservationZone.objects.all()

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip().upper()
        zone_type = request.POST.get('zone_type', 'CORE_CONSERVATION')
        color_hex = request.POST.get('color_hex', '#2e7d32')
        description = request.POST.get('description', '').strip()

        if name and code:
            zone = ConservationZone.objects.create(
                name=name,
                code=code,
                zone_type=zone_type,
                color_hex=color_hex,
                description=description,
                responsible_officer=request.user
            )
            log_activity(request.user, "CREATE", f"Created conservation zone {zone.name} ({zone.code})", model_name="ConservationZone", object_id=zone.id, request=request)
            messages.success(request, f"Zone '{zone.name}' created.")
            return redirect('officer_zones')

    return render(request, 'officer/zones.html', {'zones': zones})

from django.http import JsonResponse

@role_required(ROLE_FOREST_OFFICER, ROLE_ADMIN)
def officer_tourism(request):
    """
    Forest Officer Tourism Handling:
    1. Manages visitor and tour group permits (TourismRecord)
    2. Controls sanctuary eco-tourism zone restrictions (TourismRestriction)
    Accessible to authorized Forest Officers and Administrators.
    """
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_permit' or (request.POST.get('visitor_name') and action != 'update_restriction'):
            visitor_name = request.POST.get('visitor_name', '').strip()
            contact_phone = request.POST.get('contact_phone', '').strip()
            contact_email = request.POST.get('contact_email', '').strip()
            visit_date_str = request.POST.get('visit_date', '').strip()
            visitor_count_str = request.POST.get('visitor_count', '1').strip()
            zone_id = request.POST.get('zone_id')
            location_area = request.POST.get('location_area', '').strip()
            purpose_of_visit = request.POST.get('purpose_of_visit', '').strip()
            status = request.POST.get('status', 'APPROVED')
            remarks = request.POST.get('remarks', '').strip()

            errors = []
            if not visitor_name:
                errors.append("Visitor / Group name is required.")
            if not purpose_of_visit:
                errors.append("Purpose of visit is required.")

            try:
                visitor_count = int(visitor_count_str)
                if visitor_count < 1:
                    errors.append("Visitor count must be at least 1.")
            except (ValueError, TypeError):
                errors.append("Visitor count must be a valid number.")

            try:
                visit_date = timezone.datetime.strptime(visit_date_str, '%Y-%m-%d').date() if visit_date_str else timezone.now().date()
            except ValueError:
                errors.append("Invalid visit date format. Use YYYY-MM-DD.")

            zone = None
            if zone_id:
                try:
                    zone = ConservationZone.objects.get(id=zone_id)
                except ConservationZone.DoesNotExist:
                    errors.append("Selected conservation zone does not exist.")

            if errors:
                for err in errors:
                    messages.error(request, err)
                return redirect('officer_tourism')

            record = TourismRecord.objects.create(
                visitor_name=visitor_name,
                contact_phone=contact_phone,
                contact_email=contact_email,
                visit_date=visit_date,
                visitor_count=visitor_count,
                zone=zone,
                location_area=location_area,
                purpose_of_visit=purpose_of_visit,
                status=status,
                remarks=remarks,
                recorded_by=request.user
            )

            log_activity(
                request.user, "CREATE",
                f"Issued tourism permit {record.permit_id} for {record.visitor_name} ({record.visitor_count} persons)",
                model_name="TourismRecord", object_id=record.id, request=request
            )
            messages.success(request, f"Visitor permit {record.permit_id} successfully issued for {record.visitor_name}.")
            return redirect('officer_tourism')

        elif action == 'update_restriction' or request.POST.get('restriction_reason'):
            zone_id = request.POST.get('zone_id')
            status = request.POST.get('status')
            reason = request.POST.get('restriction_reason', '').strip()
            valid_from = request.POST.get('valid_from', timezone.now().strftime('%Y-%m-%d'))
            valid_until = request.POST.get('valid_until') or None

            zone = get_object_or_404(ConservationZone, id=zone_id)
            tr = TourismRestriction.objects.create(
                zone=zone,
                status=status,
                restriction_reason=reason,
                valid_from=valid_from,
                valid_until=valid_until,
                updated_by=request.user
            )
            log_activity(request.user, "UPDATE", f"Updated tourism restriction for zone {zone.name} to {status}", model_name="TourismRestriction", object_id=tr.id, request=request)
            messages.success(request, f"Tourism restriction updated for {zone.name}.")
            return redirect('officer_tourism')

    # Querying & Filters
    q = request.GET.get('q', '').strip()
    status_filter = request.GET.get('status', 'ALL')
    zone_filter = request.GET.get('zone_id', 'ALL')
    from_date = request.GET.get('from_date', '').strip()
    to_date = request.GET.get('to_date', '').strip()

    records_qs = TourismRecord.objects.all().select_related('zone', 'recorded_by')

    if q:
        records_qs = records_qs.filter(
            Q(permit_id__icontains=q) |
            Q(visitor_name__icontains=q) |
            Q(purpose_of_visit__icontains=q) |
            Q(location_area__icontains=q) |
            Q(contact_phone__icontains=q) |
            Q(remarks__icontains=q)
        )

    if status_filter != 'ALL':
        records_qs = records_qs.filter(status=status_filter)

    if zone_filter != 'ALL':
        records_qs = records_qs.filter(zone_id=zone_filter)

    dt_from, dt_to, date_err = parse_date_range_safely(from_date, to_date)
    if date_err:
        messages.error(request, date_err)
    elif dt_from or dt_to:
        if dt_from:
            records_qs = records_qs.filter(visit_date__gte=dt_from.date())
        if dt_to:
            records_qs = records_qs.filter(visit_date__lte=dt_to.date())

    total_permits = TourismRecord.objects.count()
    active_permits = TourismRecord.objects.filter(status='APPROVED').count()
    total_visitors = TourismRecord.objects.filter(status='APPROVED').aggregate(total=Sum('visitor_count'))['total'] or 0
    restrictions = TourismRestriction.objects.all().select_related('zone')
    zones = ConservationZone.objects.filter(is_active=True)

    context = {
        'records': records_qs,
        'restrictions': restrictions,
        'zones': zones,
        'total_permits': total_permits,
        'active_permits': active_permits,
        'total_visitors': total_visitors,
        'restrictions_count': restrictions.count(),
        'q': q,
        'status_filter': status_filter,
        'zone_filter': zone_filter,
        'from_date': from_date,
        'to_date': to_date,
        'status_choices': TourismRecord.STATUS_CHOICES,
    }
    return render(request, 'officer/tourism.html', context)


@role_required(ROLE_FOREST_OFFICER, ROLE_ADMIN)
def officer_tourism_edit(request, pk):
    record = get_object_or_404(TourismRecord, pk=pk)

    if request.method == 'GET' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'id': record.id,
            'permit_id': record.permit_id,
            'visitor_name': record.visitor_name,
            'contact_phone': record.contact_phone,
            'contact_email': record.contact_email,
            'visit_date': record.visit_date.strftime('%Y-%m-%d'),
            'visitor_count': record.visitor_count,
            'zone_id': record.zone_id,
            'location_area': record.location_area,
            'purpose_of_visit': record.purpose_of_visit,
            'status': record.status,
            'remarks': record.remarks,
        })

    if request.method == 'POST':
        visitor_name = request.POST.get('visitor_name', '').strip()
        contact_phone = request.POST.get('contact_phone', '').strip()
        contact_email = request.POST.get('contact_email', '').strip()
        visit_date_str = request.POST.get('visit_date', '').strip()
        visitor_count_str = request.POST.get('visitor_count', '1').strip()
        zone_id = request.POST.get('zone_id')
        location_area = request.POST.get('location_area', '').strip()
        purpose_of_visit = request.POST.get('purpose_of_visit', '').strip()
        status = request.POST.get('status', record.status)
        remarks = request.POST.get('remarks', '').strip()

        errors = []
        if not visitor_name:
            errors.append("Visitor / Group name is required.")
        if not purpose_of_visit:
            errors.append("Purpose of visit is required.")

        try:
            visitor_count = int(visitor_count_str)
            if visitor_count < 1:
                errors.append("Visitor count must be at least 1.")
        except (ValueError, TypeError):
            errors.append("Visitor count must be a valid number.")

        try:
            visit_date = timezone.datetime.strptime(visit_date_str, '%Y-%m-%d').date() if visit_date_str else record.visit_date
        except ValueError:
            errors.append("Invalid visit date format. Use YYYY-MM-DD.")

        zone = None
        if zone_id:
            try:
                zone = ConservationZone.objects.get(id=zone_id)
            except ConservationZone.DoesNotExist:
                errors.append("Selected zone does not exist.")

        if errors:
            for err in errors:
                messages.error(request, err)
            return redirect('officer_tourism')

        record.visitor_name = visitor_name
        record.contact_phone = contact_phone
        record.contact_email = contact_email
        record.visit_date = visit_date
        record.visitor_count = visitor_count
        record.zone = zone
        record.location_area = location_area
        record.purpose_of_visit = purpose_of_visit
        record.status = status
        record.remarks = remarks
        record.save()

        log_activity(
            request.user, "UPDATE",
            f"Updated tourism record {record.permit_id} ({record.visitor_name})",
            model_name="TourismRecord", object_id=record.id, request=request
        )
        messages.success(request, f"Permit {record.permit_id} updated successfully.")
        return redirect('officer_tourism')

    return redirect('officer_tourism')


@role_required(ROLE_FOREST_OFFICER, ROLE_ADMIN)
def officer_tourism_delete(request, pk):
    record = get_object_or_404(TourismRecord, pk=pk)

    if request.method == 'POST':
        permit_id = record.permit_id
        visitor_name = record.visitor_name
        record.delete()

        log_activity(
            request.user, "DELETE",
            f"Deleted tourism record {permit_id} ({visitor_name})",
            model_name="TourismRecord", object_id=str(pk), request=request
        )
        messages.success(request, f"Tourism record {permit_id} deleted successfully.")
    else:
        messages.error(request, "Invalid request method for deletion.")

    return redirect('officer_tourism')
