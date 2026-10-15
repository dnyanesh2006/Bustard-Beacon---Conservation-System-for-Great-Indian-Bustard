from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Count, Q
from django.utils import timezone
from datetime import datetime
from ..models import (
    Incident, BustardMovement, ConservationZone, IncidentLocation, MedicalCase,
    ROLE_RESEARCHER, ROLE_FOREST_OFFICER, ROLE_ADMIN, ConservationReport, UserProfile, Notification
)
from ..services.gis_service import calculate_high_risk_zones
from ..services.audit_service import log_activity
from ..decorators import role_required
from django.views.decorators.clickjacking import xframe_options_sameorigin

def parse_date_range(request):
    now = timezone.now()
    from_date_str = request.GET.get('from_date') or request.POST.get('from_date')
    to_date_str = request.GET.get('to_date') or request.POST.get('to_date')

    if from_date_str:
        from_date = datetime.strptime(from_date_str, '%Y-%m-%d').date()
    else:
        from_date = now.replace(day=1).date()

    if to_date_str:
        to_date = datetime.strptime(to_date_str, '%Y-%m-%d').date()
    else:
        to_date = now.date()
        
    return from_date, to_date

def get_base_incidents(from_date, to_date):
    return Incident.objects.filter(
        status='VERIFIED',
        reported_at__date__gte=from_date,
        reported_at__date__lte=to_date
    )

from ..services.analytics_service import get_analytics_data

@role_required(ROLE_RESEARCHER)
def research_dashboard(request):
    from_date, to_date = parse_date_range(request)
    incidents = get_base_incidents(from_date, to_date)
    
    analytics = get_analytics_data(from_date, to_date)
    high_risk_data = calculate_high_risk_zones()
    
    context = {
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d'),
        'analytics': analytics,
        'high_risk_data': high_risk_data[:5],
        # Kept for backward compatibility if template still expects them directly initially
        'total_incidents': analytics['total_incidents'],
        'injured_count': analytics['medical_incident_count'],
        'critical_count': incidents.filter(priority='CRITICAL').count(),
        'total_movements': BustardMovement.objects.filter(recorded_at__date__gte=from_date, recorded_at__date__lte=to_date).count(),
    }
    return render(request, 'research/dashboard.html', context)

@role_required(ROLE_RESEARCHER)
def research_add_reference_zone(request):
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        code = request.POST.get('code', '').strip().upper()
        lat_str = request.POST.get('latitude', '')
        lng_str = request.POST.get('longitude', '')
        description = request.POST.get('description', '').strip()

        if name and code and lat_str and lng_str:
            try:
                lat = float(lat_str)
                lng = float(lng_str)
                # Save this new reference zone as CORE_CONSERVATION
                zone = ConservationZone.objects.create(
                    name=name,
                    code=code,
                    zone_type='CORE_CONSERVATION',
                    description=description,
                    boundary_geojson=f'[[{lat},{lng}]]' # Just save point as center coordinate
                )
                log_activity(request.user, "CREATE", f"Created spectral reference zone {zone.name} ({zone.code})", model_name="ConservationZone", object_id=zone.id, request=request)
                messages.success(request, f"Reference Zone '{zone.name}' successfully added.")
            except ValueError:
                messages.error(request, "Invalid coordinates provided.")
        else:
            messages.error(request, "Missing required fields.")
            
    return redirect('research_dashboard')

@role_required(ROLE_RESEARCHER)
def research_incidents(request):
    from_date, to_date = parse_date_range(request)
    incidents = get_base_incidents(from_date, to_date).select_related('reporter', 'location', 'location__zone')
    
    context = {
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d'),
        'incidents': incidents,
    }
    return render(request, 'research/incidents.html', context)

@role_required(ROLE_RESEARCHER)
def research_movements(request):
    from_date, to_date = parse_date_range(request)
    movements = BustardMovement.objects.filter(recorded_at__date__gte=from_date, recorded_at__date__lte=to_date).select_related('bustard')
    field_incidents = get_base_incidents(from_date, to_date).filter(category='BIRD_SIGHTING').select_related('location')

    context = {
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d'),
        'movements': movements,
        'field_incidents': field_incidents,
    }
    return render(request, 'research/movements.html', context)

@role_required(ROLE_RESEARCHER)
def research_high_risk(request):
    risk_zones = calculate_high_risk_zones()
    return render(request, 'research/high_risk.html', {'risk_zones': risk_zones})

@role_required(ROLE_RESEARCHER)
def research_reports(request):
    from_date, to_date = parse_date_range(request)
    current_report = ConservationReport.objects.filter(period_start=from_date, period_end=to_date).order_by('-created_at').first()
    
    if request.method == 'POST':
        if 'create_draft' in request.POST:
            if not current_report:
                report = ConservationReport.objects.create(
                    period_start=from_date,
                    period_end=to_date,
                    generated_by=request.user,
                    status='DRAFT'
                )
                messages.success(request, f"Draft report created for {from_date.strftime('%Y-%m-%d')} to {to_date.strftime('%Y-%m-%d')}")
            return redirect(f"{request.path}?from_date={from_date.strftime('%Y-%m-%d')}&to_date={to_date.strftime('%Y-%m-%d')}")
            
    context = {
        'current_report': current_report,
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d'),
    }
    return render(request, 'research/reports.html', context)

@role_required(ROLE_RESEARCHER)
def research_report_finalize(request, report_id):
    report = get_object_or_404(ConservationReport, id=report_id)
    
    if report.generated_by != request.user:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You can only finalize your own research reports.")
        
    if request.method == 'POST':
        report.status = 'FINALIZED'
        report.save()
        
        log_activity(request.user, "REPORT_GEN", f"Finalized Conservation Report #{report.id}", model_name="ConservationReport", request=request)
        messages.success(request, "Report finalized and ready for submission.")
    
    report_url = reverse('research_reports')
    return redirect(f"{report_url}?from_date={report.period_start.strftime('%Y-%m-%d')}&to_date={report.period_end.strftime('%Y-%m-%d')}")

@role_required(ROLE_RESEARCHER)
def research_report_submit(request, report_id, target):
    report = get_object_or_404(ConservationReport, id=report_id)
    if report.generated_by != request.user:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied("You can only submit your own research reports.")
        
    if report.status != 'FINALIZED':
        messages.error(request, "Report must be finalized before submission.")
        report_url = reverse('research_reports')
        return redirect(f"{report_url}?from_date={report.period_start.strftime('%Y-%m-%d')}&to_date={report.period_end.strftime('%Y-%m-%d')}")

    if request.method == 'POST':
        if target == 'fo' and not report.submitted_to_fo:
            report.submitted_to_fo = True
            report.submitted_at_fo = timezone.now()
            report.save()
            
            officers = UserProfile.objects.filter(role=ROLE_FOREST_OFFICER)
            for officer in officers:
                Notification.objects.create(
                    recipient=officer.user,
                    title="Monthly Conservation Analysis Report Submitted",
                    message=f"The Researcher has submitted the conservation analysis report for {report.period_start.strftime('%B %Y')}.",
                    category="RESEARCH_REPORT",
                    link_url=f"/reports/pdf/?type=CONSERVATION_ANALYSIS_REPORT&report_id={report.id}"
                )
            messages.success(request, "Report successfully submitted to Forest Officers.")
            
        elif target == 'admin' and not report.submitted_to_admin:
            report.submitted_to_admin = True
            report.submitted_at_admin = timezone.now()
            report.save()
            
            admins = UserProfile.objects.filter(role=ROLE_ADMIN)
            for admin in admins:
                Notification.objects.create(
                    recipient=admin.user,
                    title="Monthly Conservation Analysis Report Submitted",
                    message=f"The Researcher has submitted the conservation analysis report for {report.period_start.strftime('%B %Y')}.",
                    category="RESEARCH_REPORT",
                    link_url=f"/reports/pdf/?type=CONSERVATION_ANALYSIS_REPORT&report_id={report.id}"
                )
            messages.success(request, "Report successfully submitted to Admin.")

    report_url = reverse('research_reports')
    return redirect(f"{report_url}?from_date={report.period_start.strftime('%Y-%m-%d')}&to_date={report.period_end.strftime('%Y-%m-%d')}")

@role_required(ROLE_RESEARCHER)
def api_analytics_data(request):
    from_date, to_date = parse_date_range(request)
    incidents = get_base_incidents(from_date, to_date)
    
    # 1. Incident Categories Breakdown
    cat_counts = incidents.values('category').annotate(total=Count('id'))
    category_labels = [c['category'].replace('_', ' ').title() for c in cat_counts]
    category_data = [c['total'] for c in cat_counts]

    # 2. Zone-wise Incidents
    all_zones = list(ConservationZone.objects.values_list('name', flat=True))
    zone_counts = incidents.values('location__zone__name').annotate(total=Count('id'))
    zone_dict = {z['location__zone__name']: z['total'] for z in zone_counts if z['location__zone__name']}
    
    zone_labels = all_zones
    zone_data = [zone_dict.get(z, 0) for z in all_zones]

    # 3. Priority Breakdown
    pri_counts = incidents.values('priority').annotate(total=Count('id'))
    pri_labels = [p['priority'].title() for p in pri_counts]
    pri_data = [p['total'] for p in pri_counts]

    # Medical Graph Data
    medical_cases = MedicalCase.objects.filter(created_at__date__gte=from_date, created_at__date__lte=to_date)
    med_counts = medical_cases.values('status').annotate(total=Count('id', distinct=True))
    
    # We want these specific actual status values + zero counts where appropriate
    medical_status_types = ['ACTIVE', 'UNDER_TREATMENT', 'REHABILITATION', 'RECOVERED', 'CLOSED']
    med_dict = {m['status']: m['total'] for m in med_counts}
    
    medical_labels = [s.replace('_', ' ').title() for s in medical_status_types]
    medical_data = [med_dict.get(s, 0) for s in medical_status_types]

    # 4. Movement / Observation Timeline
    from django.db.models.functions import TruncDate
    
    # Sightings timeline
    sightings = incidents.filter(category='BIRD_SIGHTING').annotate(date=TruncDate('reported_at')).values('date').annotate(total=Count('id')).order_by('date')
    
    # Movements timeline
    movements = BustardMovement.objects.filter(recorded_at__date__gte=from_date, recorded_at__date__lte=to_date).annotate(date=TruncDate('recorded_at')).values('date').annotate(total=Count('id')).order_by('date')
    
    # Combine dates
    all_dates = sorted(list(set([s['date'].strftime('%Y-%m-%d') for s in sightings] + [m['date'].strftime('%Y-%m-%d') for m in movements])))
    
    sighting_data = []
    movement_data = []
    for d in all_dates:
        s_count = next((s['total'] for s in sightings if s['date'].strftime('%Y-%m-%d') == d), 0)
        m_count = next((m['total'] for m in movements if m['date'].strftime('%Y-%m-%d') == d), 0)
        sighting_data.append(s_count)
        movement_data.append(m_count)

    return JsonResponse({
        'categories': {
            'labels': category_labels,
            'data': category_data,
        },
        'zones': {
            'labels': zone_labels,
            'data': zone_data,
        },
        'priorities': {
            'labels': pri_labels,
            'data': pri_data,
        },
        'medical': {
            'labels': medical_labels,
            'data': medical_data,
        },
        'timeline': {
            'labels': all_dates,
            'sightings': sighting_data,
            'movements': movement_data,
        }
    })

@role_required(ROLE_RESEARCHER, ROLE_FOREST_OFFICER, ROLE_ADMIN)
@xframe_options_sameorigin
def research_generate_report(request):
    from_date, to_date = parse_date_range(request)
    analytics = get_analytics_data(from_date, to_date)
    
    context = {
        'from_date': from_date.strftime('%Y-%m-%d'),
        'to_date': to_date.strftime('%Y-%m-%d'),
        'analytics': analytics,
        'generated_at': timezone.now().strftime('%Y-%m-%d %H:%M'),
        'researcher_name': request.user.get_full_name() or request.user.username,
    }
    return render(request, 'research/report_preview.html', context)
