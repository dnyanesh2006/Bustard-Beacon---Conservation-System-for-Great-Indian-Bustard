from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from ..models import MedicalCase, MedicalTreatment, MedicalEquipment, Bustard, Notification, ROLE_MEDICAL_TEAM, ROLE_FOREST_OFFICER
from ..services.audit_service import log_activity
from ..decorators import role_required

def get_forest_officers_for_case(med_case):
    officers = set()
    if med_case.incident:
        if med_case.incident.verified_by and med_case.incident.verified_by.profile.role == ROLE_FOREST_OFFICER:
            officers.add(med_case.incident.verified_by)
        if med_case.incident.location and med_case.incident.location.zone and med_case.incident.location.zone.responsible_officer:
            officers.add(med_case.incident.location.zone.responsible_officer)
    if med_case.created_by and getattr(med_case.created_by, 'profile', None) and med_case.created_by.profile.role == ROLE_FOREST_OFFICER:
        officers.add(med_case.created_by)
    return list(officers)

def get_admin_users():
    from ..models import UserProfile
    admin_profiles = UserProfile.objects.filter(role='ADMIN', user__is_active=True)
    return [p.user for p in admin_profiles]


@role_required(ROLE_MEDICAL_TEAM)
def medical_dashboard(request):
    team_cases = MedicalCase.objects.filter(assigned_team=request.user).order_by('-created_at', '-id')
    active_cases_qs = team_cases.filter(status__in=['ACTIVE', 'UNDER_TREATMENT', 'REHABILITATION'])
    icu_cases_qs = team_cases.filter(rehabilitation_stage='ICU', status__in=['ACTIVE', 'UNDER_TREATMENT'])
    recovered_qs = team_cases.filter(status__in=['RECOVERED', 'CLOSED'], rehabilitation_stage__in=['PRE_RELEASE', 'RELEASED'])
    death_qs = team_cases.filter(status='CLOSED', rehabilitation_stage='DECEASED')

    equipment = MedicalEquipment.objects.all()

    if request.method == 'POST' and request.POST.get('form_type') == 'update_availability':
        new_status = request.POST.get('availability_status')
        if new_status in dict(request.user.profile.AVAILABILITY_CHOICES).keys():
            request.user.profile.availability_status = new_status
            request.user.profile.save()
            log_activity(request.user, "UPDATE", f"Updated availability status to {new_status}", model_name="UserProfile", object_id=request.user.id, request=request)
            messages.success(request, f"Your availability has been updated to {new_status}.")
            return redirect('medical_dashboard')

    context = {
        'active_cases_count': active_cases_qs.count(),
        'icu_cases_count': icu_cases_qs.count(),
        'recovered_count': recovered_qs.count(),
        'death_count': death_qs.count(),
        'active_cases': active_cases_qs[:5],
        'all_active_cases': active_cases_qs,
        'icu_cases': icu_cases_qs,
        'recovered_cases': recovered_qs,
        'death_cases': death_qs,
        'equipment': equipment,
    }
    return render(request, 'medical/dashboard.html', context)

@role_required(ROLE_MEDICAL_TEAM)
def medical_cases(request):
    status_filter = request.GET.get('status', 'ALL')
    cases = MedicalCase.objects.filter(assigned_team=request.user).select_related('incident', 'bustard', 'created_by')

    if status_filter != 'ALL':
        cases = cases.filter(status=status_filter)

    return render(request, 'medical/cases.html', {'cases': cases, 'selected_status': status_filter})

@role_required('MEDICAL_TEAM', 'FOREST_OFFICER', 'ADMIN')
def medical_case_detail(request, case_id):
    try:
        med_case = MedicalCase.objects.select_related('incident', 'bustard', 'created_by').get(id=case_id)
    except MedicalCase.DoesNotExist:
        messages.error(request, "The medical case record has been deleted or is unavailable.")
        return render(request, 'medical/case_detail_error.html', {'message': "Record not found or deleted."})
    
    profile = request.user.profile
    if profile.role == 'MEDICAL_TEAM':
        if med_case.assigned_team != request.user:
            messages.error(request, "You can only view cases assigned to you.")
            return render(request, 'medical/case_detail_error.html', {'message': "Access Denied."})
    elif profile.role == 'FOREST_OFFICER':
        is_responsible = (
            med_case.created_by == request.user or
            (med_case.incident and med_case.incident.verified_by == request.user) or
            (med_case.incident and hasattr(med_case.incident, 'location') and med_case.incident.location and med_case.incident.location.zone and med_case.incident.location.zone.responsible_officer == request.user)
        )
        if not is_responsible:
            messages.error(request, "You can only view medical cases related to your assigned incidents or zones.")
            return render(request, 'medical/case_detail_error.html', {'message': "Access Denied."})

    treatments = MedicalTreatment.objects.filter(medical_case=med_case).select_related('administered_by')

    if request.method == 'POST':
        if profile.role != ROLE_MEDICAL_TEAM:
            raise PermissionDenied("Only the Medical Team can manage clinical details.")
        
        form_type = request.POST.get('form_type')

        if form_type == 'add_treatment':
            description = request.POST.get('treatment_description', '').strip()
            medications = request.POST.get('medications_given', '').strip()
            dosage = request.POST.get('dosage_notes', '').strip()

            if description:
                treatment = MedicalTreatment.objects.create(
                    medical_case=med_case,
                    administered_by=request.user,
                    treatment_description=description,
                    medications_given=medications,
                    dosage_notes=dosage,
                    treatment_time=timezone.now()
                )
                log_activity(request.user, "CREATE", f"Added treatment log to Medical Case {med_case.case_id}", model_name="MedicalTreatment", object_id=treatment.id, request=request)
                
                try:
                    for officer in get_forest_officers_for_case(med_case):
                        bird_info = f" for {med_case.bustard.tag_id}" if med_case.bustard else ""
                        Notification.objects.create(
                            recipient=officer,
                            title=f"New Treatment Log: Case {med_case.case_id}",
                            message=f"A new medical treatment log was added{bird_info}. Summary: {description}",
                            category="MEDICAL_UPDATE",
                            link_url=reverse('medical_case_detail', args=[med_case.id])
                        )
                except Exception:
                    pass

                messages.success(request, "Treatment log recorded successfully.")

        elif form_type == 'update_status':
            new_stage = request.POST.get('rehabilitation_stage')
            new_status = request.POST.get('status')
            if new_stage == 'DECEASED':
                new_status = 'CLOSED'
            diagnosis = request.POST.get('diagnosis', '').strip()

            valid_mapping = {
                'RECOVERY_ENCLOSURE': ['UNDER_TREATMENT', 'REHABILITATION'],
                'ICU': ['ACTIVE', 'UNDER_TREATMENT'],
                'PRE_RELEASE': ['RECOVERED'],
                'RELEASED': ['CLOSED'],
                'DECEASED': ['CLOSED']
            }

            if new_stage not in valid_mapping or new_status not in valid_mapping[new_stage]:
                messages.error(request, "Invalid combination of Rehabilitation Stage and Case Status.")
                return redirect('medical_case_detail', case_id=case_id)

            old_stage = med_case.rehabilitation_stage
            old_stage_display = med_case.get_rehabilitation_stage_display()
            old_status_display = med_case.get_status_display()

            med_case.rehabilitation_stage = new_stage
            med_case.status = new_status
            if diagnosis:
                med_case.diagnosis = diagnosis
            med_case.save()

            # Update associated Bustard health status if linked
            if med_case.bustard:
                if new_status == 'CLOSED' and new_stage == 'RELEASED':
                    med_case.bustard.health_status = 'HEALTHY'
                elif new_status == 'CLOSED' and new_stage == 'DECEASED':
                    med_case.bustard.health_status = 'DECEASED'
                elif new_status in ['ACTIVE', 'UNDER_TREATMENT']:
                    med_case.bustard.health_status = 'REHABILITATION'
                med_case.bustard.save()

            log_activity(request.user, "UPDATE", f"Updated Medical Case {med_case.case_id} stage to {new_stage} ({new_status})", model_name="MedicalCase", object_id=med_case.id, request=request)
            
            try:
                recipients = get_forest_officers_for_case(med_case)
                is_new_death = (new_status == 'CLOSED' and new_stage == 'DECEASED' and old_stage != 'DECEASED')
                if is_new_death:
                    recipients.extend(get_admin_users())
                
                # Make recipient list unique
                recipients = list(set(recipients))
                
                for officer in recipients:
                    bird_info = f"{med_case.bustard.tag_id}" if med_case.bustard else "Unknown / Unregistered Bird"
                    title = None
                    msg = None
                    
                    if new_stage == 'DECEASED' and old_stage != 'DECEASED':
                        title = f"DECEASED BIRD ALERT: Case {med_case.case_id}"
                        cause = diagnosis if diagnosis else "Unknown / Not Recorded"
                        msg = f"Bird {bird_info} confirmed dead.\nIncident ID: {med_case.incident.incident_id if med_case.incident else 'N/A'}\nCase ID: {med_case.case_id}\nClosure Time: {timezone.now().strftime('%Y-%m-%d %H:%M')}\nCause / Circumstances: {cause}"
                    elif old_stage != new_stage or old_status_display != med_case.get_status_display():
                        title = f"Rehab Update: Case {med_case.case_id}"
                        msg = f"Medical status updated for {bird_info}.\nStage: {old_stage_display} -> {med_case.get_rehabilitation_stage_display()}\nStatus: {old_status_display} -> {med_case.get_status_display()}\nDiagnosis: {diagnosis}"
                        
                    if title and msg:
                        Notification.objects.create(
                            recipient=officer,
                            title=title,
                            message=msg,
                            category="MEDICAL_UPDATE",
                            link_url=reverse('medical_case_detail', args=[med_case.id])
                        )
            except Exception:
                pass

            messages.success(request, "Medical case status and stage updated.")

        return redirect('medical_case_detail', case_id=med_case.id)

    context = {
        'case': med_case,
        'treatments': treatments,
    }
    return render(request, 'medical/case_detail.html', context)

@role_required(ROLE_MEDICAL_TEAM, ROLE_FOREST_OFFICER)
def medical_equipment(request):
    equipment_list = MedicalEquipment.objects.all()

    if request.method == 'POST':
        if request.user.profile.role != ROLE_MEDICAL_TEAM:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Only the Medical Team can manage equipment inventory.")
        
        action = request.POST.get('action')

        if action == 'add':
            name = request.POST.get('name', '').strip()
            category = request.POST.get('category', '').strip()
            status = request.POST.get('status', 'OPERATIONAL')

            if not name:
                messages.error(request, "Equipment name is required.")
                return redirect('medical_equipment')

            try:
                quantity_available = int(request.POST.get('quantity_available', 1))
                if quantity_available < 0:
                    messages.error(request, "Available quantity cannot be negative.")
                    return redirect('medical_equipment')
            except (ValueError, TypeError):
                messages.error(request, "Available quantity must be a valid non-negative integer.")
                return redirect('medical_equipment')

            try:
                quantity_in_use = int(request.POST.get('quantity_in_use', 0))
                if quantity_in_use < 0:
                    messages.error(request, "In-use quantity cannot be negative.")
                    return redirect('medical_equipment')
            except (ValueError, TypeError):
                messages.error(request, "In-use quantity must be a valid non-negative integer.")
                return redirect('medical_equipment')

            eq = MedicalEquipment.objects.create(
                name=name,
                category=category,
                quantity_available=quantity_available,
                quantity_in_use=quantity_in_use,
                status=status,
                last_inspected=timezone.now().date()
            )
            log_activity(request.user, "CREATE", f"Added medical equipment '{eq.name}'", model_name="MedicalEquipment", object_id=eq.id, request=request)
            messages.success(request, f"Equipment '{eq.name}' added to inventory.")
            return redirect('medical_equipment')

        elif action == 'edit':
            eq_id = request.POST.get('eq_id')
            try:
                eq = MedicalEquipment.objects.get(id=eq_id)
            except (MedicalEquipment.DoesNotExist, ValueError, TypeError):
                messages.error(request, "Invalid or non-existent equipment record.")
                return redirect('medical_equipment')

            new_name = request.POST.get('name', '').strip()
            if not new_name:
                messages.error(request, "Equipment name cannot be empty.")
                return redirect('medical_equipment')

            try:
                qty_avail = int(request.POST.get('quantity_available', eq.quantity_available))
                if qty_avail < 0:
                    messages.error(request, "Available quantity cannot be negative.")
                    return redirect('medical_equipment')
            except (ValueError, TypeError):
                messages.error(request, "Available quantity must be a valid non-negative integer.")
                return redirect('medical_equipment')

            try:
                qty_use = int(request.POST.get('quantity_in_use', eq.quantity_in_use))
                if qty_use < 0:
                    messages.error(request, "In-use quantity cannot be negative.")
                    return redirect('medical_equipment')
            except (ValueError, TypeError):
                messages.error(request, "In-use quantity must be a valid non-negative integer.")
                return redirect('medical_equipment')

            eq.name = new_name
            eq.category = request.POST.get('category', eq.category).strip()
            eq.quantity_available = qty_avail
            eq.quantity_in_use = qty_use
            eq.status = request.POST.get('status', eq.status)
            eq.save()
            log_activity(request.user, "UPDATE", f"Updated equipment '{eq.name}'", model_name="MedicalEquipment", object_id=eq.id, request=request)
            messages.success(request, f"Updated '{eq.name}'.")
            return redirect('medical_equipment')

        elif action == 'delete':
            eq_id = request.POST.get('eq_id')
            try:
                eq = MedicalEquipment.objects.get(id=eq_id)
            except (MedicalEquipment.DoesNotExist, ValueError, TypeError):
                messages.error(request, "Invalid or non-existent equipment record.")
                return redirect('medical_equipment')

            name = eq.name
            eq.delete()
            log_activity(request.user, "DELETE", f"Deleted equipment '{name}'", model_name="MedicalEquipment", object_id=eq_id, request=request)
            messages.success(request, f"Deleted '{name}'.")
            return redirect('medical_equipment')

    return render(request, 'medical/equipment.html', {'equipment_list': equipment_list})
