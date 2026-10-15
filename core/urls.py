from django.urls import path
from django.contrib.auth import views as django_auth_views
from .views import (
    auth_views, landing_views, ranger_views, officer_views,
    medical_views, research_views, admin_views, map_views, report_views
)

urlpatterns = [
    # Public & Auth Routes
    path('', landing_views.landing_view, name='landing'),
    path('about/', landing_views.about_view, name='about'),
    path('tourism/', landing_views.tourism_view, name='tourism'),
    path('login/', auth_views.login_view, name='login'),
    path('auth/google/login/', auth_views.google_login_view, name='google_login'),
    path('auth/google/callback/', auth_views.google_callback_view, name='google_callback'),
    path('auth/google/register/', auth_views.google_register_view, name='google_register'),
    path('logout/', auth_views.logout_view, name='logout'),
    
    # Password Reset URLs
    path('password-reset/', django_auth_views.PasswordResetView.as_view(template_name='password_reset.html', email_template_name='password_reset_email.html'), name='password_reset'),
    path('password-reset/done/', django_auth_views.PasswordResetDoneView.as_view(template_name='password_reset_done.html'), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', django_auth_views.PasswordResetConfirmView.as_view(template_name='password_reset_confirm.html'), name='password_reset_confirm'),
    path('reset/done/', django_auth_views.PasswordResetCompleteView.as_view(template_name='password_reset_complete.html'), name='password_reset_complete'),
    
    path('dashboard/', auth_views.dashboard_redirect_view, name='dashboard'),
    path('password-change/', auth_views.password_change_view, name='password_change'),
    path('profile/', auth_views.profile_view, name='profile'),
    path('notifications/', auth_views.notifications_view, name='notifications'),
    path('api/notifications/unread/', auth_views.api_unread_notifications_count, name='api_unread_notifications_count'),

    # Map Routes
    path('map/', map_views.live_map_view, name='live_map'),
    path('conservation-map/', map_views.live_map_view, name='public_map'),
    path('api/map-data/', map_views.api_map_data, name='api_map_data'),

    # Ranger Field Routes
    path('ranger/field-mode/', ranger_views.ranger_field_mode, name='ranger_field_mode'),
    path('ranger/report-incident/', ranger_views.report_incident, name='report_incident'),
    path('ranger/incidents/', ranger_views.ranger_incidents, name='ranger_incidents'),
    path('ranger/assignments/', ranger_views.ranger_assignments, name='ranger_assignments'),
    path('api/update-location/', ranger_views.api_update_location, name='api_update_location'),

    # Forest Officer Routes
    path('officer/dashboard/', officer_views.officer_dashboard, name='officer_dashboard'),
    path('officer/incidents/', officer_views.officer_incidents, name='officer_incidents'),
    path('officer/incidents/<int:incident_id>/', officer_views.officer_incident_detail, name='officer_incident_detail'),
    path('officer/zones/', officer_views.officer_zones, name='officer_zones'),
    path('officer/tourism/', officer_views.officer_tourism, name='officer_tourism'),
    path('officer/tourism/<int:pk>/edit/', officer_views.officer_tourism_edit, name='officer_tourism_edit'),
    path('officer/tourism/<int:pk>/delete/', officer_views.officer_tourism_delete, name='officer_tourism_delete'),

    # Medical Routes
    path('medical/dashboard/', medical_views.medical_dashboard, name='medical_dashboard'),
    path('medical/cases/', medical_views.medical_cases, name='medical_cases'),
    path('medical/cases/<int:case_id>/', medical_views.medical_case_detail, name='medical_case_detail'),
    path('medical/equipment/', medical_views.medical_equipment, name='medical_equipment'),

    # Research Routes
    path('research/dashboard/', research_views.research_dashboard, name='research_dashboard'),
    path('research/add-reference-zone/', research_views.research_add_reference_zone, name='research_add_reference_zone'),
    path('research/incidents/', research_views.research_incidents, name='research_incidents'),
    path('research/movements/', research_views.research_movements, name='research_movements'),
    path('research/high-risk/', research_views.research_high_risk, name='research_high_risk'),
    path('research/reports/', research_views.research_reports, name='research_reports'),
    path('research/reports/finalize/<int:report_id>/', research_views.research_report_finalize, name='research_report_finalize'),
    path('research/reports/submit/<int:report_id>/<str:target>/', research_views.research_report_submit, name='research_report_submit'),
    path('research/reports/generate/', research_views.research_generate_report, name='research_generate_report'),
    path('api/analytics-data/', research_views.api_analytics_data, name='api_analytics_data'),

    # Admin Panel Routes
    path('admin-panel/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('admin-panel/users/', admin_views.admin_users, name='admin_users'),
    path('admin-panel/records/users/', admin_views.admin_users_overview, name='admin_users_overview'),
    path('admin-panel/records/medical/', admin_views.admin_medical_records, name='admin_medical_records'),
    path('admin-panel/records/officer/', admin_views.admin_officer_records, name='admin_officer_records'),
    path('admin-panel/birds/', admin_views.admin_birds, name='admin_birds'),
    path('admin-panel/audit-logs/', admin_views.admin_audit_logs, name='admin_audit_logs'),

    # Reports Center Routes
    path('reports/', report_views.report_center, name='report_center'),
    path('reports/pdf/', report_views.download_pdf_report, name='download_pdf_report'),
]
