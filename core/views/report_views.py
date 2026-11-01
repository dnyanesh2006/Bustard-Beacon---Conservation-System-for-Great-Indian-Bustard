from datetime import datetime, time
from django.shortcuts import render, redirect, get_object_or_404
from django.http import HttpResponse
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from ..models import (
    Incident, MedicalCase, PatrolAssignment, ActivityLog, ConservationReport,
    ROLE_ADMIN, ROLE_FOREST_OFFICER, ROLE_RANGER, ROLE_MEDICAL_TEAM, ROLE_RESEARCHER,
)
from ..services.pdf_service import generate_pdf_report
from ..services.audit_service import log_activity
from ..decorators import role_required


REPORT_ACCESS = {
    'FIELD_PATROL_INCIDENT_REPORT': {ROLE_ADMIN, ROLE_FOREST_OFFICER, ROLE_RANGER},
    'OFFICER_OPERATIONAL_SUMMARY': {ROLE_ADMIN, ROLE_FOREST_OFFICER},
    'MEDICAL_RESCUE_REPORT': {ROLE_ADMIN, ROLE_MEDICAL_TEAM},
    'WILDLIFE_POPULATION_REPORT': {ROLE_ADMIN},
    'SYSTEM_AUDIT_REPORT': {ROLE_ADMIN},
    'CONSERVATION_ANALYSIS_REPORT': {ROLE_ADMIN, ROLE_FOREST_OFFICER, ROLE_RESEARCHER},
}


def parse_date_range_safely(date_from_str, date_to_str):
    """
    Parses and validates date_from and date_to (%Y-%m-%d).
    Returns (dt_from, dt_to, error_message).
    """
    dt_from = None
    dt_to = None
    error = None

    if date_from_str and date_from_str.strip():
        try:
            dt_from = datetime.strptime(date_from_str.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None, None, f"Invalid 'From Date' format ('{date_from_str}'). Please use YYYY-MM-DD."

    if date_to_str and date_to_str.strip():
        try:
            dt_to = datetime.strptime(date_to_str.strip(), "%Y-%m-%d").date()
        except ValueError:
            return None, None, f"Invalid 'To Date' format ('{date_to_str}'). Please use YYYY-MM-DD."

    if dt_from and dt_to and dt_from > dt_to:
        error = "Start date cannot be later than end date."

    return dt_from, dt_to, error


def filter_datetime_range(queryset, field_name, dt_from, dt_to):
    """
    Applies SQLite-safe timezone-aware boundary filtering for DateTimeField.
    """
    if dt_from:
        start_dt = timezone.make_aware(datetime.combine(dt_from, time.min))
        queryset = queryset.filter(**{f"{field_name}__gte": start_dt})
    if dt_to:
        end_dt = timezone.make_aware(datetime.combine(dt_to, time.max))
        queryset = queryset.filter(**{f"{field_name}__lte": end_dt})
    return queryset


@role_required(
    ROLE_ADMIN,
    ROLE_FOREST_OFFICER,
    ROLE_RANGER,
    ROLE_MEDICAL_TEAM,
    ROLE_RESEARCHER,
)
def report_center(request):
    """
    Role-specific Report Generation Hub.
    Routes each actor to their dedicated, strictly-isolated reporting interface.
    """
    profile = getattr(request.user, 'profile', None)
    role = profile.role if profile else (ROLE_ADMIN if request.user.is_superuser else None)

    # Researchers already have their fixed monthly report interface
    if role == ROLE_RESEARCHER:
        return redirect('research_reports')

    # =========================================================================
    # 1. ADMIN REPORT CENTER
    # =========================================================================
    if role == ROLE_ADMIN or request.user.is_superuser:
        # A. Ranger Reports (Consolidated)
        r_from_raw = request.GET.get('ranger_date_from') or (request.GET.get('date_from', '') if request.GET.get('section') == 'ranger' else '')
        r_to_raw = request.GET.get('ranger_date_to') or (request.GET.get('date_to', '') if request.GET.get('section') == 'ranger' else '')
        r_from, r_to, r_err = parse_date_range_safely(r_from_raw, r_to_raw)
        if r_err:
            messages.error(request, f"Ranger Report filter error: {r_err}")

        ranger_incidents = Incident.objects.all().select_related('reporter', 'location', 'location__zone').order_by('-reported_at')
        if not r_err:
            ranger_incidents = filter_datetime_range(ranger_incidents, 'reported_at', r_from, r_to)

        # B. Forest Officer Operational Summary
        fo_from_raw = request.GET.get('officer_date_from') or (request.GET.get('date_from', '') if request.GET.get('section') == 'officer' else '')
        fo_to_raw = request.GET.get('officer_date_to') or (request.GET.get('date_to', '') if request.GET.get('section') == 'officer' else '')
        fo_from, fo_to, fo_err = parse_date_range_safely(fo_from_raw, fo_to_raw)
        if fo_err:
            messages.error(request, f"Officer Report filter error: {fo_err}")

        fo_incidents = Incident.objects.all().select_related('reporter', 'reporter__profile', 'verified_by', 'location', 'location__zone').order_by('-reported_at')
        fo_med = MedicalCase.objects.all()
        fo_patrols = PatrolAssignment.objects.all()
        fo_actions = ActivityLog.objects.filter(action__in=['VERIFY', 'ASSIGN', 'UPDATE'])
        if not fo_err:
            fo_incidents = filter_datetime_range(fo_incidents, 'reported_at', fo_from, fo_to)
            fo_med = filter_datetime_range(fo_med, 'created_at', fo_from, fo_to)
            fo_patrols = filter_datetime_range(fo_patrols, 'assigned_at', fo_from, fo_to)
            fo_actions = filter_datetime_range(fo_actions, 'timestamp', fo_from, fo_to)

        fo_metrics = {
            'total_incidents': fo_incidents.count(),
            'resolved_incidents': fo_incidents.filter(status='VERIFIED').count(),
            'pending_incidents': fo_incidents.filter(status__in=['PENDING', 'MORE_INFO']).count(),
            'critical_incidents': fo_incidents.filter(priority__in=['CRITICAL', 'HIGH']).count(),
            'total_medical': fo_med.count(),
            'active_medical': fo_med.filter(status__in=['ACTIVE', 'UNDER_TREATMENT', 'REHABILITATION']).count(),
            'patrols_count': fo_patrols.count(),
            'actions_count': fo_actions.count(),
        }

        # C. Medical Team Reports
        m_from_raw = request.GET.get('medical_date_from') or (request.GET.get('date_from', '') if request.GET.get('section') == 'medical' else '')
        m_to_raw = request.GET.get('medical_date_to') or (request.GET.get('date_to', '') if request.GET.get('section') == 'medical' else '')
        m_cat = request.GET.get('medical_sub_category', 'ALL')
        m_from, m_to, m_err = parse_date_range_safely(m_from_raw, m_to_raw)
        if m_err:
            messages.error(request, f"Medical Report filter error: {m_err}")

        medical_cases = MedicalCase.objects.all().select_related('incident', 'bustard', 'assigned_team', 'created_by').order_by('-created_at')
        if m_cat == 'ACTIVE':
            medical_cases = medical_cases.filter(status__in=['ACTIVE', 'UNDER_TREATMENT', 'REHABILITATION'])
        elif m_cat == 'ICU':
            medical_cases = medical_cases.filter(rehabilitation_stage='ICU', status__in=['ACTIVE', 'UNDER_TREATMENT'])
        elif m_cat == 'RECOVERED':
            medical_cases = medical_cases.filter(status__in=['RECOVERED', 'CLOSED'], rehabilitation_stage__in=['PRE_RELEASE', 'RELEASED'])
        elif m_cat == 'DEATH':
            medical_cases = medical_cases.filter(status='CLOSED', rehabilitation_stage='DECEASED')

        if not m_err:
            medical_cases = filter_datetime_range(medical_cases, 'created_at', m_from, m_to)

        # D. Researcher Reports (Submitted to Admin)
        res_from_raw = request.GET.get('research_date_from') or (request.GET.get('date_from', '') if request.GET.get('section') == 'research' else '')
        res_to_raw = request.GET.get('research_date_to') or (request.GET.get('date_to', '') if request.GET.get('section') == 'research' else '')
        res_from, res_to, res_err = parse_date_range_safely(res_from_raw, res_to_raw)
        if res_err:
            messages.error(request, f"Researcher Report filter error: {res_err}")

        research_reports = ConservationReport.objects.filter(status='FINALIZED', submitted_to_admin=True).select_related('generated_by').order_by('-submitted_at_admin')
        if not res_err:
            if res_from:
                research_reports = research_reports.filter(period_start__gte=res_from)
            if res_to:
                research_reports = research_reports.filter(period_end__lte=res_to)

        # E. System Audit & Compliance Report
        aud_from_raw = request.GET.get('audit_date_from') or (request.GET.get('date_from', '') if request.GET.get('section') == 'audit' else '')
        aud_to_raw = request.GET.get('audit_date_to') or (request.GET.get('date_to', '') if request.GET.get('section') == 'audit' else '')
        aud_from, aud_to, aud_err = parse_date_range_safely(aud_from_raw, aud_to_raw)
        if aud_err:
            messages.error(request, f"Audit Report filter error: {aud_err}")

        audit_logs = ActivityLog.objects.all().order_by('-timestamp')
        if not aud_err:
            audit_logs = filter_datetime_range(audit_logs, 'timestamp', aud_from, aud_to)

        context = {
            'role': ROLE_ADMIN,
            # Ranger
            'ranger_incidents': ranger_incidents[:10],
            'ranger_total_count': ranger_incidents.count(),
            'ranger_date_from': r_from_raw,
            'ranger_date_to': r_to_raw,
            # Officer
            'fo_metrics': fo_metrics,
            'fo_operational_incidents': fo_incidents[:10],
            'fo_date_from': fo_from_raw,
            'fo_date_to': fo_to_raw,
            # Medical
            'medical_cases': medical_cases[:10],
            'medical_total_count': medical_cases.count(),
            'medical_date_from': m_from_raw,
            'medical_date_to': m_to_raw,
            'medical_sub_category': m_cat,
            # Research
            'research_reports': research_reports,
            'research_date_from': res_from_raw,
            'research_date_to': res_to_raw,
            # Audit
            'audit_logs_count': audit_logs.count(),
            'audit_recent_logs': audit_logs[:5],
            'audit_date_from': aud_from_raw,
            'audit_date_to': aud_to_raw,
        }
        return render(request, 'reports/admin_reports.html', context)

    # =========================================================================
    # 2. FOREST OFFICER REPORT CENTER (EXACTLY THREE TABS)
    # =========================================================================
    elif role == ROLE_FOREST_OFFICER:
        active_tab = request.GET.get('tab', 'operational')

        # Tab 1: My Operational Report
        fo_from_raw = request.GET.get('officer_date_from') or request.GET.get('date_from', '')
        fo_to_raw = request.GET.get('officer_date_to') or request.GET.get('date_to', '')
        fo_from, fo_to, fo_err = parse_date_range_safely(fo_from_raw, fo_to_raw)
        if fo_err and active_tab == 'operational':
            messages.error(request, fo_err)

        managed_incidents = Incident.objects.filter(
            Q(verified_by=request.user) | Q(assignments__assigned_by=request.user)
        ).distinct().select_related('reporter', 'reporter__profile', 'verified_by', 'location', 'location__zone').prefetch_related('assignments', 'assignments__assigned_ranger').order_by('-reported_at')
        dispatched_patrols = PatrolAssignment.objects.filter(assigned_by=request.user).select_related('assigned_ranger', 'assigned_ranger__profile', 'incident').order_by('-assigned_at')
        officer_logs = ActivityLog.objects.filter(user=request.user).order_by('-timestamp')

        if not fo_err:
            managed_incidents = filter_datetime_range(managed_incidents, 'reported_at', fo_from, fo_to)
            dispatched_patrols = filter_datetime_range(dispatched_patrols, 'assigned_at', fo_from, fo_to)
            officer_logs = filter_datetime_range(officer_logs, 'timestamp', fo_from, fo_to)

        fo_metrics = {
            'total_managed': managed_incidents.count(),
            'verified_count': managed_incidents.filter(status='VERIFIED').count(),
            'pending_count': managed_incidents.filter(status__in=['PENDING', 'MORE_INFO']).count(),
            'critical_count': managed_incidents.filter(priority__in=['CRITICAL', 'HIGH']).count(),
            'dispatched_count': dispatched_patrols.count(),
            'actions_count': officer_logs.count(),
        }

        # Tab 2: Ranger Reports (Consolidated all Rangers)
        r_from_raw = request.GET.get('ranger_date_from') or request.GET.get('date_from', '')
        r_to_raw = request.GET.get('ranger_date_to') or request.GET.get('date_to', '')
        r_from, r_to, r_err = parse_date_range_safely(r_from_raw, r_to_raw)
        if r_err and active_tab == 'rangers':
            messages.error(request, r_err)

        ranger_incidents = Incident.objects.all().select_related('reporter', 'reporter__profile', 'location', 'location__zone').order_by('-reported_at')
        if not r_err:
            ranger_incidents = filter_datetime_range(ranger_incidents, 'reported_at', r_from, r_to)

        # Tab 3: Researcher Reports (Submitted to FO)
        res_from_raw = request.GET.get('research_date_from') or request.GET.get('date_from', '')
        res_to_raw = request.GET.get('research_date_to') or request.GET.get('date_to', '')
        res_from, res_to, res_err = parse_date_range_safely(res_from_raw, res_to_raw)
        if res_err and active_tab == 'research':
            messages.error(request, res_err)

        research_reports = ConservationReport.objects.filter(status='FINALIZED', submitted_to_fo=True).select_related('generated_by').order_by('-submitted_at_fo')
        if not res_err:
            if res_from:
                research_reports = research_reports.filter(period_start__gte=res_from)
            if res_to:
                research_reports = research_reports.filter(period_end__lte=res_to)

        context = {
            'role': ROLE_FOREST_OFFICER,
            'active_tab': active_tab,
            # Tab 1: Operations
            'managed_incidents': managed_incidents[:25],
            'verified_incidents': managed_incidents.filter(status='VERIFIED')[:15],
            'dispatched_patrols': dispatched_patrols[:15],
            'officer_logs': officer_logs[:15],
            'fo_metrics': fo_metrics,
            'verified_count': fo_metrics['verified_count'],
            'dispatched_count': fo_metrics['dispatched_count'],
            'actions_count': fo_metrics['actions_count'],
            'officer_date_from': fo_from_raw,
            'officer_date_to': fo_to_raw,
            # Tab 2: Rangers
            'ranger_incidents': ranger_incidents[:15],
            'ranger_total_count': ranger_incidents.count(),
            'ranger_date_from': r_from_raw,
            'ranger_date_to': r_to_raw,
            # Tab 3: Researcher
            'research_reports': research_reports,
            'research_date_from': res_from_raw,
            'research_date_to': res_to_raw,
        }
        return render(request, 'reports/officer_reports.html', context)

    # =========================================================================
    # 3. RANGER REPORT CENTER (ONE SINGLE REPORT OPTION)
    # =========================================================================
    elif role == ROLE_RANGER:
        date_from_raw = request.GET.get('date_from', '')
        date_to_raw = request.GET.get('date_to', '')
        dt_from, dt_to, date_err = parse_date_range_safely(date_from_raw, date_to_raw)
        if date_err:
            messages.error(request, date_err)

        # Strictly only logged-in Ranger's own records!
        my_incidents = Incident.objects.filter(reporter=request.user).select_related('location', 'location__zone').order_by('-reported_at')
        if not date_err:
            my_incidents = filter_datetime_range(my_incidents, 'reported_at', dt_from, dt_to)

        context = {
            'role': ROLE_RANGER,
            'incidents': my_incidents,
            'total_count': my_incidents.count(),
            'date_from': date_from_raw,
            'date_to': date_to_raw,
        }
        return render(request, 'reports/ranger_reports.html', context)

    # =========================================================================
    # 4. MEDICAL TEAM REPORT CENTER (OWN REPORTS ONLY)
    # =========================================================================
    elif role == ROLE_MEDICAL_TEAM:
        date_from_raw = request.GET.get('date_from', '')
        date_to_raw = request.GET.get('date_to', '')
        sub_category = request.GET.get('sub_category', 'ALL')
        dt_from, dt_to, date_err = parse_date_range_safely(date_from_raw, date_to_raw)
        if date_err:
            messages.error(request, date_err)

        # Strictly logged-in Medical Team's own authorized records!
        my_cases = MedicalCase.objects.filter(
            Q(assigned_team=request.user) | Q(created_by=request.user)
        ).select_related('incident', 'bustard').order_by('-created_at')

        if sub_category == 'ACTIVE':
            my_cases = my_cases.filter(status__in=['ACTIVE', 'UNDER_TREATMENT', 'REHABILITATION'])
        elif sub_category == 'ICU':
            my_cases = my_cases.filter(rehabilitation_stage='ICU', status__in=['ACTIVE', 'UNDER_TREATMENT'])
        elif sub_category == 'RECOVERED':
            my_cases = my_cases.filter(status__in=['RECOVERED', 'CLOSED'], rehabilitation_stage__in=['PRE_RELEASE', 'RELEASED'])
        elif sub_category == 'DEATH':
            my_cases = my_cases.filter(status='CLOSED', rehabilitation_stage='DECEASED')

        if not date_err:
            my_cases = filter_datetime_range(my_cases, 'created_at', dt_from, dt_to)

        context = {
            'role': ROLE_MEDICAL_TEAM,
            'cases': my_cases,
            'total_count': my_cases.count(),
            'sub_category': sub_category,
            'date_from': date_from_raw,
            'date_to': date_to_raw,
        }
        return render(request, 'reports/medical_reports.html', context)

    # Fallback for unrecognized role
    return render(request, 'reports/index.html', {'role': role})


@role_required(
    ROLE_ADMIN,
    ROLE_FOREST_OFFICER,
    ROLE_RANGER,
    ROLE_MEDICAL_TEAM,
    ROLE_RESEARCHER,
)
def download_pdf_report(request):
    """
    Generates and downloads formal ReportLab PDF reports based on selected category.
    Enforces strict role-based data scoping and date validation.
    """
    report_type = request.GET.get('type', 'FIELD_PATROL_INCIDENT_REPORT')
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    report_id = request.GET.get('report_id')

    if report_type not in REPORT_ACCESS:
        raise PermissionDenied("Invalid report category specified.")

    profile = getattr(request.user, 'profile', None)
    user_role = profile.role if profile else (ROLE_ADMIN if request.user.is_superuser else None)

    if not request.user.is_superuser:
        if profile is None or user_role not in REPORT_ACCESS[report_type]:
            raise PermissionDenied("You do not have permission to generate this category of report.")

    # -------------------------------------------------------------------------
    # Handling Researcher Reports View/Download
    # -------------------------------------------------------------------------
    if report_type == 'CONSERVATION_ANALYSIS_REPORT' and report_id:
        report = get_object_or_404(ConservationReport, id=report_id)

        if not request.user.is_superuser and profile:
            if user_role == ROLE_RESEARCHER and report.generated_by != request.user:
                raise PermissionDenied("You can only view your own generated research reports.")
            elif user_role == ROLE_FOREST_OFFICER and not report.submitted_to_fo:
                raise PermissionDenied("This report has not been submitted to Forest Officers.")
            elif user_role == ROLE_ADMIN and not report.submitted_to_admin:
                raise PermissionDenied("This report has not been submitted to System Administrators.")

        # Always preserve active_role to prevent login redirect loops across MultiRoleAuthMiddleware
        active_role = request.GET.get('active_role') or (user_role or '')
        redirect_url = f"/research/reports/generate/?from_date={report.period_start}&to_date={report.period_end}"
        if active_role:
            redirect_url += f"&active_role={active_role}"
        return redirect(redirect_url)

    # -------------------------------------------------------------------------
    # Date Validation
    # -------------------------------------------------------------------------
    dt_from, dt_to, date_error = parse_date_range_safely(date_from, date_to)
    if date_error:
        messages.error(request, date_error)
        return redirect(request.META.get('HTTP_REFERER', 'report_center'))

    title = "BUSTARD BEACON CONSERVATION REPORT"
    queryset = []

    # -------------------------------------------------------------------------
    # A. FIELD PATROL & INCIDENT REPORT
    # -------------------------------------------------------------------------
    if report_type == 'FIELD_PATROL_INCIDENT_REPORT':
        title = "CONSOLIDATED RANGER FIELD PATROL & INCIDENT REPORT"
        queryset = Incident.objects.all().select_related('reporter', 'reporter__profile', 'location', 'location__zone').order_by('-reported_at')

        # Ranger role can only export their own records!
        if not request.user.is_superuser and user_role == ROLE_RANGER:
            queryset = queryset.filter(reporter=request.user)
            title = f"RANGER FIELD PATROL REPORT — {request.user.get_full_name() or request.user.username}"

        queryset = filter_datetime_range(queryset, 'reported_at', dt_from, dt_to)

    # -------------------------------------------------------------------------
    # B. FOREST OFFICER OPERATIONAL SUMMARY
    # -------------------------------------------------------------------------
    elif report_type == 'OFFICER_OPERATIONAL_SUMMARY':
        title = "FOREST OFFICER OPERATIONAL SUMMARY"
        incidents = Incident.objects.all().select_related('reporter', 'reporter__profile', 'verified_by', 'location', 'location__zone').prefetch_related('assignments', 'assignments__assigned_ranger').order_by('-reported_at')
        med_cases = MedicalCase.objects.all().select_related('incident', 'bustard')
        assignments = PatrolAssignment.objects.all().select_related('assigned_ranger', 'assigned_ranger__profile', 'assigned_by', 'incident').order_by('-assigned_at')
        actions = ActivityLog.objects.filter(action__in=['VERIFY', 'ASSIGN', 'UPDATE']).order_by('-timestamp')

        if not request.user.is_superuser and user_role == ROLE_FOREST_OFFICER:
            title = f"OFFICER OPERATIONAL REPORT — {request.user.get_full_name() or request.user.username}"
            incidents = incidents.filter(Q(verified_by=request.user) | Q(assignments__assigned_by=request.user)).distinct()
            assignments = assignments.filter(assigned_by=request.user)
            actions = actions.filter(user=request.user)

        incidents = filter_datetime_range(incidents, 'reported_at', dt_from, dt_to)
        med_cases = filter_datetime_range(med_cases, 'created_at', dt_from, dt_to)
        assignments = filter_datetime_range(assignments, 'assigned_at', dt_from, dt_to)
        actions = filter_datetime_range(actions, 'timestamp', dt_from, dt_to)

        summary_metrics = {
            'total_incidents': incidents.count(),
            'resolved_incidents': incidents.filter(status='VERIFIED').count(),
            'pending_incidents': incidents.filter(status__in=['PENDING', 'MORE_INFO']).count(),
            'critical_incidents': incidents.filter(priority__in=['CRITICAL', 'HIGH']).count(),
            'total_medical': med_cases.count(),
            'active_medical': med_cases.filter(status__in=['ACTIVE', 'UNDER_TREATMENT', 'REHABILITATION']).count(),
            'patrol_assignments': assignments.count(),
            'actions_count': actions.count(),
        }

        queryset = {
            'summary': summary_metrics,
            'incidents': list(incidents[:100]),
            'assignments': list(assignments[:50]),
            'actions': list(actions[:50]),
        }

    # -------------------------------------------------------------------------
    # C. MEDICAL RESCUE REPORT
    # -------------------------------------------------------------------------
    elif report_type == 'MEDICAL_RESCUE_REPORT':
        sub_category = request.GET.get('sub_category')
        title = "MEDICAL & RESCUE OPERATIONS REPORT"
        queryset = MedicalCase.objects.all().select_related('incident', 'bustard', 'assigned_team', 'created_by').order_by('-created_at')

        # Medical Team members can only export their own assigned or created records!
        if not request.user.is_superuser and user_role == ROLE_MEDICAL_TEAM:
            queryset = queryset.filter(Q(assigned_team=request.user) | Q(created_by=request.user))
            title = f"MEDICAL TEAM CLINICAL REPORT — {request.user.get_full_name() or request.user.username}"

        if sub_category == 'ACTIVE':
            title += " (ACTIVE CASES)"
            queryset = queryset.filter(status__in=['ACTIVE', 'UNDER_TREATMENT', 'REHABILITATION'])
        elif sub_category == 'ICU':
            title += " (ICU CASES)"
            queryset = queryset.filter(rehabilitation_stage='ICU', status__in=['ACTIVE', 'UNDER_TREATMENT'])
        elif sub_category == 'RECOVERED':
            title += " (RECOVERED CASES)"
            queryset = queryset.filter(status__in=['RECOVERED', 'CLOSED'], rehabilitation_stage__in=['PRE_RELEASE', 'RELEASED'])
        elif sub_category == 'DEATH':
            title += " (DEATH RECORDS)"
            queryset = queryset.filter(status='CLOSED', rehabilitation_stage='DECEASED')

        queryset = filter_datetime_range(queryset, 'created_at', dt_from, dt_to)

    # -------------------------------------------------------------------------
    # D. WILDLIFE POPULATION REPORT
    # -------------------------------------------------------------------------
    elif report_type == 'WILDLIFE_POPULATION_REPORT':
        title = "WILDLIFE POPULATION & SIGHTING REGISTRY"
        from ..models import Bustard
        queryset = Bustard.objects.all().order_by('-created_at')
        queryset = filter_datetime_range(queryset, 'created_at', dt_from, dt_to)

    # -------------------------------------------------------------------------
    # E. SYSTEM AUDIT & COMPLIANCE REPORT
    # -------------------------------------------------------------------------
    elif report_type == 'SYSTEM_AUDIT_REPORT':
        title = "SYSTEM AUDIT & COMPLIANCE REPORT"
        queryset = ActivityLog.objects.all().order_by('-timestamp')
        queryset = filter_datetime_range(queryset, 'timestamp', dt_from, dt_to)

    pdf_bytes = generate_pdf_report(report_type, queryset, title=title, user=request.user, date_from=date_from, date_to=date_to)
    log_activity(request.user, "REPORT_GEN", f"Generated PDF Report: {title}", request=request)

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f"bustard_beacon_{report_type.lower()}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
