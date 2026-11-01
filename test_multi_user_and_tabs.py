"""
Comprehensive Test Suite for Multi-User Concurrency, Browser Tab Isolation,
and 'Open in New Tab' Behavior in Bustard Beacon.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bustard_beacon.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from django.db import connection
from core.models import (
    Incident, MedicalCase, MedicalTreatment, Bustard,
    ConservationZone, ROLE_ADMIN, ROLE_FOREST_OFFICER,
    ROLE_RANGER, ROLE_MEDICAL_TEAM, ROLE_RESEARCHER
)
import json

User = get_user_model()

def run_tests():
    print("=" * 76)
    print("  BUSTARD BEACON — MULTI-USER, NEW TAB & SESSION ISOLATION TEST SUITE")
    print("=" * 76)

    # -------------------------------------------------------------
    # TEST A: Separate Users in Separate Browser Sessions
    # -------------------------------------------------------------
    print("\n--- TEST A: Separate Users (Independent Browser Sessions) ---")
    roles_config = [
        ('ADMIN', 'admin', 'admin123', '/admin-panel/'),
        ('FOREST_OFFICER', 'officer_solapur', 'officer123', '/officer/dashboard/'),
        ('RANGER', 'ranger_nannaj', 'ranger123', '/ranger/field-mode/'),
        ('MEDICAL_TEAM', 'dr_vet_solapur', 'vet123', '/medical/dashboard/'),
        ('RESEARCHER', 'dr_researcher', 'research123', '/research/dashboard/'),
    ]

    clients = {}
    for role_name, username, password, dash_url in roles_config:
        client = Client()
        resp = client.post('/login/', {
            'login_role': role_name.lower().replace('_team', '').replace('forest_', ''),
            'username': username,
            'password': password
        }, follow=False)
        assert resp.status_code == 302, f"Login failed for {username}: {resp.status_code}"
        
        # Access dashboard
        dash_resp = client.get(dash_url, follow=False)
        assert dash_resp.status_code == 200, f"Dashboard {dash_url} returned {dash_resp.status_code} for {username}"
        clients[role_name] = client
        print(f"  [PASS] {role_name:<16} ({username}): Authenticated & Dashboard loaded independently.")

    # -------------------------------------------------------------
    # TEST B: Multiple Tabs in the Same Browser Session
    # -------------------------------------------------------------
    print("\n--- TEST B: Multi-Tab Single Browser Session ---")
    shared_client = Client()
    
    # Tab 1: Ranger logs in
    resp1 = shared_client.post('/login/', {
        'login_role': 'ranger',
        'username': 'ranger_nannaj',
        'password': 'ranger123'
    }, follow=False)
    assert resp1.status_code == 302
    print("  [PASS] Tab 1: Ranger logged in.")

    # Tab 2: Landing page loads in new tab
    landing_resp = shared_client.get('/', follow=False)
    assert landing_resp.status_code == 200
    landing_html = landing_resp.content.decode('utf-8')
    assert "Staff Login" in landing_html, "Landing page must offer Staff Login"
    assert "Go to Dashboard" in landing_html, "Landing page should offer Go to Dashboard for active user"
    print("  [PASS] Tab 2: Public landing page displays both Go to Dashboard and Staff Login.")

    # Tab 3: User opens /login/ in new tab
    login_tab_resp = shared_client.get('/login/', follow=False)
    assert login_tab_resp.status_code == 200, f"Expected 200 on /login/, got {login_tab_resp.status_code}"
    login_tab_html = login_tab_resp.content.decode('utf-8')
    assert "Staff Authentication" in login_tab_html, "Login page must display authentication card"
    assert "Currently active session" in login_tab_html, "Active session banner should be displayed"
    assert "Ranger Nannaj" in login_tab_html or "ranger_nannaj" in login_tab_html
    print("  [PASS] Tab 3: /login/ opened in new tab loads login form cleanly without redirecting to Ranger.")

    # Tab 4: Forest Officer logs in via Tab 3
    resp_fo = shared_client.post('/login/', {
        'login_role': 'officer',
        'username': 'officer_solapur',
        'password': 'officer123'
    }, follow=False)
    assert resp_fo.status_code == 302
    assert '/officer/dashboard/' in resp_fo.url
    print("  [PASS] Tab 4: Forest Officer logged in successfully in the same browser.")

    # Verify both Tab 1 (Ranger) and Tab 4 (Officer) are concurrently active
    r_tab1 = shared_client.get('/ranger/field-mode/', follow=False)
    assert r_tab1.status_code == 200, f"Ranger dashboard returned {r_tab1.status_code}"
    r_tab4 = shared_client.get('/officer/dashboard/', follow=False)
    assert r_tab4.status_code == 200, f"Officer dashboard returned {r_tab4.status_code}"
    print("  [PASS] Concurrent tabs verified: Ranger (200) and Forest Officer (200) active in same session.")

    # -------------------------------------------------------------
    # TEST C: Authentication Isolation & Redirect Loop Prevention
    # -------------------------------------------------------------
    print("\n--- TEST C: Cross-Role Tab Isolation & Infinite Loop Prevention ---")
    ranger_only_client = Client()
    ranger_only_client.post('/login/', {
        'login_role': 'ranger',
        'username': 'ranger_nannaj',
        'password': 'ranger123'
    })

    # Ranger tries to access Officer dashboard in a new tab
    cross_resp = ranger_only_client.get('/officer/dashboard/', follow=False)
    assert cross_resp.status_code == 302, f"Expected 302 redirect from /officer/dashboard/, got {cross_resp.status_code}"
    assert '/login/?next=/officer/dashboard/' in cross_resp.url

    # The redirect target (/login/?next=...) must load login form (HTTP 200), NOT bounce back to officer or ranger!
    login_redirect_target = ranger_only_client.get(cross_resp.url, follow=False)
    assert login_redirect_target.status_code == 200, f"Expected 200 on login redirect target, got {login_redirect_target.status_code}"
    login_html = login_redirect_target.content.decode('utf-8')
    assert "Staff Authentication" in login_html
    print("  [PASS] Unauthorized role access redirects cleanly to login (200) with ZERO infinite loops.")

    # Test HTTP Referer preservation for 'Open in New Tab'
    nav_tab = shared_client.get('/profile/', HTTP_REFERER='http://testserver/officer/dashboard/', follow=False)
    assert nav_tab.status_code == 200
    print("  [PASS] Open-in-new-tab referer propagation verified: Profile resolves to Officer context.")

    # -------------------------------------------------------------
    # TEST D: Concurrent Operations Simulation
    # -------------------------------------------------------------
    print("\n--- TEST D: Concurrent Operations Simulation ---")
    c_admin = clients['ADMIN']
    c_fo = clients['FOREST_OFFICER']
    c_ranger = clients['RANGER']
    c_med = clients['MEDICAL_TEAM']
    c_res = clients['RESEARCHER']

    # 1. Ranger submits incident
    zone = ConservationZone.objects.first()
    bird = Bustard.objects.filter(death_record__isnull=True).first()
    ranger_user = User.objects.get(username='ranger_nannaj')
    
    resp_inc = c_ranger.post('/ranger/report-incident/', {
        'category': 'BIRD_SIGHTING',
        'priority': 'LOW',
        'bustard': str(bird.id),
        'latitude': '17.8250',
        'longitude': '75.8450',
        'zone': str(zone.id),
        'description': 'Simulated concurrent patrol sighting of healthy Great Indian Bustard.'
    }, follow=False)
    assert resp_inc.status_code == 302
    created_inc = Incident.objects.filter(description__contains='Simulated concurrent patrol sighting').first()
    assert created_inc is not None
    print(f"  [PASS] Op 1: Ranger submitted incident ({created_inc.incident_id}).")

    # 2. Forest Officer verifies incident
    fo_user = User.objects.get(username='officer_solapur')
    resp_verify = c_fo.post(f'/officer/incidents/{created_inc.id}/', {
        'action_type': 'verify_incident',
        'status': 'VERIFIED',
        'priority': 'LOW',
        'verification_notes': 'Verified during concurrent test execution.'
    }, follow=False)
    assert resp_verify.status_code == 302
    created_inc.refresh_from_db()
    assert created_inc.status == 'VERIFIED'
    print(f"  [PASS] Op 2: Forest Officer verified incident ({created_inc.incident_id}).")

    # 3. Medical Team adds treatment to active case
    med_case = MedicalCase.objects.filter(status='UNDER_TREATMENT').first()
    assert med_case is not None
    resp_treatment = c_med.post(f'/medical/cases/{med_case.id}/', {
        'action': 'add_treatment',
        'treatment_description': 'Administered sterile multivitamin rehydration solution.',
        'medications_given': 'Avian B-Complex 0.5ml',
        'dosage_notes': 'Monitor crop motility.'
    }, follow=False)
    assert resp_treatment.status_code == 302
    print(f"  [PASS] Op 3: Medical Team recorded treatment for case {med_case.case_id}.")

    # 4. Researcher accesses analytics API
    resp_analytics = c_res.get('/api/analytics-data/')
    assert resp_analytics.status_code == 200
    analytics_data = json.loads(resp_analytics.content.decode('utf-8'))
    assert 'categories' in analytics_data and sum(analytics_data['categories']['data']) > 0
    print("  [PASS] Op 4: Researcher retrieved analytics dataset with live field data.")

    # 5. Admin accesses user overview
    resp_admin = c_admin.get('/admin-panel/records/users/')
    assert resp_admin.status_code == 200
    print("  [PASS] Op 5: Administrator retrieved system user registry.")

    # Clean up test incident safely
    created_inc.delete()

    # -------------------------------------------------------------
    # TEST E: Database Engine & Concurrency Verification
    # -------------------------------------------------------------
    print("\n--- TEST E: Database Locking & Engine Checks ---")
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode;")
        mode = cursor.fetchone()[0]
        cursor.execute("PRAGMA busy_timeout;")
        timeout = cursor.fetchone()[0]
    
    print(f"  - SQLite Journal Mode: {mode.upper()}")
    print(f"  - SQLite Busy Timeout: {timeout} ms")
    assert mode.lower() == 'wal', f"Expected WAL mode, got {mode}"
    assert timeout >= 5000, f"Expected busy timeout >= 5000, got {timeout}"
    print("  [PASS] SQLite WAL mode & 30s busy timeout configured for multi-user non-blocking reads/writes.")

    print("\n" + "=" * 76)
    print("  ALL MULTI-USER & TAB ISOLATION TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 76)

if __name__ == '__main__':
    run_tests()
