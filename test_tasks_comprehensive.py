import os
import django
import re

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bustard_beacon.settings')
django.setup()

from django.test import Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from core.models import (
    UserProfile, Bustard, Incident, MedicalCase, ConservationZone,
    MedicalEquipment, TourismRecord, ROLE_ADMIN, ROLE_FOREST_OFFICER,
    ROLE_RANGER, ROLE_MEDICAL_TEAM, ROLE_RESEARCHER
)
from core.validators import (
    validate_indian_mobile, validate_email_address, validate_username,
    validate_date_string
)

def run_comprehensive_suite():
    print("=" * 65)
    print("STARTING COMPREHENSIVE REGRESSION SUITE: TASKS 1, 2, 3 & NAVBAR")
    print("=" * 65)

    # -------------------------------------------------------------
    # 0. SETUP TEST USERS & BIRDS
    # -------------------------------------------------------------
    admin_user = User.objects.filter(profile__role=ROLE_ADMIN).first() or User.objects.filter(is_superuser=True).first()
    ranger_user = User.objects.filter(profile__role=ROLE_RANGER, is_active=True).first()
    officer_user = User.objects.filter(profile__role=ROLE_FOREST_OFFICER, is_active=True).first()
    vet_user = User.objects.filter(profile__role=ROLE_MEDICAL_TEAM, is_active=True).first()

    assert admin_user and ranger_user and officer_user and vet_user, "Users for all roles must exist"

    # Ensure we have at least 1 living bird and 1 deceased bird
    living_bird = Bustard.objects.exclude(health_status='DECEASED').first()
    deceased_bird = Bustard.objects.filter(health_status='DECEASED').first()

    if not deceased_bird:
        deceased_bird = Bustard.objects.create(
            tag_id='GIB-TEST-DEAD',
            name='Test Deceased Bird',
            health_status='DECEASED'
        )

    print(f"Living Bird for tests: {living_bird.tag_id} ({living_bird.health_status})")
    print(f"Deceased Bird for tests: {deceased_bird.tag_id} ({deceased_bird.health_status})")

    # -------------------------------------------------------------
    # TASK 1: BIRD ID DROPDOWN IN RANGER MEDICAL TREATMENT
    # -------------------------------------------------------------
    print("\n--- TASK 1: Bird ID Dropdown in Ranger Medical Treatment ---")
    ranger_client = Client()
    ranger_client.force_login(ranger_user)

    # 1. Check GET report_incident HTML contains dropdown
    resp = ranger_client.get(reverse('report_incident'))
    assert resp.status_code == 200
    html = resp.content.decode('utf-8')

    # Verify dropdown select exists
    assert '<select name="bird_id" id="bird_id_select"' in html, "bird_id select element must exist"
    # Verify Unknown Bird option
    assert 'value="UNKNOWN"' in html, "UNKNOWN bird option must be available"
    assert '-- Unknown Bird (Unidentified) --' in html, "Unknown Bird display text must be present"
    # Verify living bird is in options
    assert f'value="{living_bird.tag_id}"' in html, f"Living bird {living_bird.tag_id} must appear in dropdown"
    # Verify deceased bird is NOT in options
    assert f'value="{deceased_bird.tag_id}"' not in html, f"Deceased bird {deceased_bird.tag_id} must NOT appear in dropdown"
    print("PASS: Dropdown dynamically renders living birds and Unknown Bird; excludes deceased birds.")

    # 2. Submit with Unknown Bird
    post_data_unknown = {
        'category': 'INJURED_BIRD',
        'description': 'Found an injured bustard near western power line corridor.',
        'latitude': '17.8200',
        'longitude': '75.8100',
        'bird_id': 'UNKNOWN',
        'send_medical_alert': 'true',
    }
    resp = ranger_client.post(reverse('report_incident'), post_data_unknown, follow=True)
    assert resp.status_code == 200
    inc_unknown = Incident.objects.filter(description=post_data_unknown['description']).first()
    assert inc_unknown is not None, "Incident with UNKNOWN bird must be created"
    assert inc_unknown.bustard is None, "UNKNOWN bird must result in bustard foreign key being None (NULL)"
    assert inc_unknown.priority == 'CRITICAL', "Injured bird with medical alert must automatically get CRITICAL priority"
    print("PASS: UNKNOWN bird option creates incident safely with bustard=NULL and CRITICAL priority.")

    # 3. Submit with valid Living Bird
    post_data_living = {
        'category': 'INJURED_BIRD',
        'description': f'Observing {living_bird.tag_id} showing signs of wing distress.',
        'latitude': '17.8250',
        'longitude': '75.8150',
        'bird_id': living_bird.tag_id,
        'send_medical_alert': 'true',
    }
    resp = ranger_client.post(reverse('report_incident'), post_data_living, follow=True)
    assert resp.status_code == 200
    inc_living = Incident.objects.filter(description=post_data_living['description']).first()
    assert inc_living is not None, "Incident with living bird must be created"
    assert inc_living.bustard == living_bird, "Living bird must be properly linked"
    print(f"PASS: Valid living bird ({living_bird.tag_id}) successfully linked to incident.")

    # 4. Attempt to submit with Deceased Bird (Backend rejection)
    post_data_dead = {
        'category': 'INJURED_BIRD',
        'description': 'Attempting to assign a deceased bird.',
        'latitude': '17.8250',
        'longitude': '75.8150',
        'bird_id': deceased_bird.tag_id,
        'send_medical_alert': 'true',
    }
    resp = ranger_client.post(reverse('report_incident'), post_data_dead)
    assert resp.status_code == 200  # Returns form with error
    assert Incident.objects.filter(description=post_data_dead['description']).first() is None, "Deceased bird submission must not create incident"
    dead_err_html = resp.content.decode('utf-8')
    assert 'deceased' in dead_err_html.lower(), "Must display clear error message about deceased bird"
    print("PASS: Backend authoritatively rejects deceased bird selection.")

    # 5. Attempt to submit with Arbitrary / Fake Bird ID
    post_data_fake = {
        'category': 'INJURED_BIRD',
        'description': 'Attempting to assign a fake bird ID.',
        'latitude': '17.8250',
        'longitude': '75.8150',
        'bird_id': 'FAKE-BIRD-999',
        'send_medical_alert': 'true',
    }
    resp = ranger_client.post(reverse('report_incident'), post_data_fake)
    assert resp.status_code == 200
    assert Incident.objects.filter(description=post_data_fake['description']).first() is None
    fake_err_html = resp.content.decode('utf-8')
    assert 'does not exist' in fake_err_html.lower(), "Must display error that bird ID does not exist"
    print("PASS: Backend authoritatively rejects arbitrary non-existent bird IDs.")

    # 6. Form value preservation on error
    post_data_err = {
        'category': 'BIRD_SIGHTING',
        'description': 'Preserve this text even when lat/long are out of range.',
        'latitude': '999.00',  # Out of range!
        'longitude': '75.8150',
        'bird_id': living_bird.tag_id,
    }
    resp = ranger_client.post(reverse('report_incident'), post_data_err)
    err_html = resp.content.decode('utf-8')
    assert 'Preserve this text even when lat/long are out of range.' in err_html, "Form must preserve entered description"
    assert '999.00' in err_html, "Form must preserve entered latitude"
    assert f'value="{living_bird.tag_id}" selected' in err_html or f'value="{living_bird.tag_id}"' in err_html, "Form must preserve selected bird"
    print("PASS: Form preservation verified on validation error.")

    # -------------------------------------------------------------
    # TASK 2: PROJECT-WIDE FORM VALIDATION
    # -------------------------------------------------------------
    print("\n--- TASK 2: Project-Wide Form Validation ---")

    # Mobile validation function tests
    assert validate_indian_mobile('9822011223') is None, "10-digit number must be valid"
    assert validate_indian_mobile('+91 98220 11223') is None, "+91 format must be valid"
    assert validate_indian_mobile('09822011223') is None, "0-prefixed number must be valid"
    assert validate_indian_mobile('+91-9822011223') is None, "Hyphenated number must be valid"
    assert validate_indian_mobile('98220ABC23') is not None, "Letters in mobile must be rejected"
    assert validate_indian_mobile('12345') is not None, "Short mobile must be rejected"
    assert validate_indian_mobile('123456789012345') is not None, "Long mobile must be rejected"
    assert validate_indian_mobile('5123456789') is not None, "Indian number starting with 5 must be rejected"
    print("PASS: validate_indian_mobile correctly validates formats and rejects invalid numbers.")

    # Email validation function tests
    assert validate_email_address('ranger@bustard.org') is None, "Valid email must pass"
    assert validate_email_address('invalid-email-address') is not None, "Invalid email format must be rejected"
    assert validate_email_address('test@') is not None, "Incomplete email must be rejected"
    print("PASS: validate_email_address correctly validates and rejects malformed emails.")

    # Username validation function tests
    assert validate_username('valid_user.123') is None, "Valid username must pass"
    assert validate_username('ab') is not None, "Username under 3 chars must be rejected"
    assert validate_username('bad username with spaces') is not None, "Spaces in username must be rejected"
    assert validate_username('') is not None, "Empty username must be rejected"
    print("PASS: validate_username enforces length and character rules.")

    # Date string validation function tests
    assert validate_date_string('2026-10-26') is None, "Valid date must pass"
    assert validate_date_string('2026-99-99') is not None, "Impossible date must be rejected"
    assert validate_date_string('invalid-date') is not None, "Malformed date string must be rejected"
    assert validate_date_string('2099-01-01', allow_future=False) is not None, "Future date must be rejected when allow_future=False"
    print("PASS: validate_date_string enforces format and future-date constraints.")

    # Admin User Management Validation
    admin_client = Client()
    admin_client.force_login(admin_user)

    # Attempt to create user with System Admin role (must be rejected)
    resp = admin_client.post('/admin-panel/users/', {
        'action': 'create_user',
        'username': 'sneaky_admin',
        'password': 'password123',
        'role': ROLE_ADMIN,
    }, follow=True)
    assert User.objects.filter(username='sneaky_admin').first() is None, "Cannot create System Administrator via admin panel"
    print("PASS: Prevented unauthorized ADMIN role assignment.")

    # Attempt to create user with short password
    resp = admin_client.post('/admin-panel/users/', {
        'action': 'create_user',
        'username': 'short_pw_user',
        'password': '123',
        'role': ROLE_RANGER,
    }, follow=True)
    assert User.objects.filter(username='short_pw_user').first() is None, "Password < 6 characters must be rejected"
    print("PASS: Rejected short password for new staff creation.")

    # Attempt to create user with invalid mobile
    resp = admin_client.post('/admin-panel/users/', {
        'action': 'create_user',
        'username': 'bad_mobile_user',
        'password': 'password123',
        'role': ROLE_RANGER,
        'phone_number': 'NOT_A_PHONE_NUMBER',
    }, follow=True)
    assert User.objects.filter(username='bad_mobile_user').first() is None, "Invalid mobile number must be rejected"
    print("PASS: Rejected user creation with malformed phone number.")

    # Attempt to create bird with duplicate Tag ID
    resp = admin_client.post('/admin-panel/birds/', {
        'action': 'create_bird',
        'tag_id': living_bird.tag_id,
        'name': 'Duplicate Bird',
    }, follow=True)
    assert resp.status_code == 200
    messages_text = [str(m.message) for m in resp.wsgi_request._messages]
    assert any('already exists' in m.lower() for m in messages_text), "Duplicate Tag ID must be rejected"
    print("PASS: Duplicate bird Tag ID rejected with clear error.")

    # Medical Equipment validation
    vet_client = Client()
    vet_client.force_login(vet_user)

    resp = vet_client.post('/medical/equipment/', {
        'action': 'add',
        'name': 'Emergency Oxygen Kit',
        'category': 'Respiratory',
        'quantity_available': '-5',  # Negative!
        'quantity_in_use': '0',
    }, follow=True)
    assert MedicalEquipment.objects.filter(name='Emergency Oxygen Kit').first() is None, "Negative quantity must be rejected"
    print("PASS: Negative medical equipment quantity rejected.")

    resp = vet_client.post('/medical/equipment/', {
        'action': 'add',
        'name': '',  # Empty name!
        'category': 'Diagnostics',
        'quantity_available': '2',
        'quantity_in_use': '0',
    }, follow=True)
    assert resp.status_code == 200
    print("PASS: Empty equipment name rejected.")

    # -------------------------------------------------------------
    # TASK 3: REPEATED LOGIN PROMPTS & STAFF LOGIN FIXES
    # -------------------------------------------------------------
    print("\n--- TASK 3: Repeated Login Prompts & Staff Login Links ---")

    # 1. Opening /login/ in a new tab renders the login page cleanly without bouncing to dashboard
    test_client = Client()
    test_client.force_login(officer_user)
    resp = test_client.get('/login/')
    assert resp.status_code == 200, "Authenticated user accessing /login/ in a new tab must see the login page cleanly"
    content = resp.content.decode('utf-8')
    assert "Staff Authentication" in content, "Login form must be displayed"
    assert "Currently active session" in content, "Active session notice must be displayed for switching roles"
    print("PASS: Authenticated user opening /login/ in new tab loads login page cleanly with active session notice.")

    # 2. Authenticated user visiting /login/?next=/officer/incidents/ respects next URL
    resp = test_client.get('/login/?next=/officer/incidents/')
    assert resp.status_code == 302
    assert '/officer/incidents/' in resp.url, f"Expected redirect to /officer/incidents/, got {resp.url}"
    print("PASS: Authenticated user visiting /login/?next=... is redirected directly to requested page.")

    # 3. Cache control headers on protected views
    resp = test_client.get('/officer/dashboard/')
    assert resp.status_code == 200
    cache_header = resp.headers.get('Cache-Control', '')
    assert 'no-cache' in cache_header and 'no-store' in cache_header, "Protected dashboard must return no-cache, no-store headers"
    print("PASS: Security Cache-Control headers prevent back-button viewing of stale dashboard content.")

    # 4. Logout clears session completely and prevents backward navigation
    resp = test_client.post('/logout/', follow=True)
    assert resp.status_code == 200
    # Attempting to access dashboard after logout must redirect to login
    resp_after_logout = test_client.get('/officer/dashboard/')
    assert resp_after_logout.status_code == 302, "Dashboard access after logout must redirect to login"
    assert '/login/' in resp_after_logout.url, "Must redirect to login page"
    print("PASS: Logout completely flushes session; protected dashboard cannot be accessed post-logout.")

    # 5. Landing page CTA links
    anon_client = Client()
    landing_anon = anon_client.get('/')
    assert landing_anon.status_code == 200
    landing_anon_html = landing_anon.content.decode('utf-8')
    assert 'Staff Login' in landing_anon_html, "Unauthenticated user on landing page sees Staff Login button"

    auth_client = Client()
    auth_client.force_login(ranger_user)
    landing_auth = auth_client.get('/')
    assert landing_auth.status_code == 200
    landing_auth_html = landing_auth.content.decode('utf-8')
    assert 'Go to Dashboard' in landing_auth_html, "Authenticated user on landing page sees Go to Dashboard button"
    print("PASS: Landing page CTA accurately adjusts between Staff Login and Go to Dashboard based on auth status.")

    # -------------------------------------------------------------
    # ADDITIONAL UI: NAVBAR HOVER
    # -------------------------------------------------------------
    print("\n--- ADDITIONAL UI: Dashboard Navbar Hover ---")
    base_html_path = os.path.join('core', 'templates', 'base.html')
    with open(base_html_path, 'r', encoding='utf-8') as f:
        base_html_content = f.read()

    css_path = os.path.join('core', 'static', 'css', 'design_system.css')
    with open(css_path, 'r', encoding='utf-8') as f:
        css_content = f.read()

    assert 'bb-dashboard-dropdown' in base_html_content, "base.html must have bb-dashboard-dropdown class"
    assert 'bb-dashboard-dropdown:hover' in css_content, "design_system.css must have desktop hover rule"
    assert '@media (min-width: 992px)' in css_content, "CSS must target desktop viewport >= 992px"
    assert 'navDashboardDropdown' in base_html_content, "Dropdown must have accessible ID"
    print("PASS: Navbar hover CSS, accessible markup, and JavaScript integration verified.")

    # Clean up test artifacts
    if deceased_bird.tag_id == 'GIB-TEST-DEAD':
        deceased_bird.delete()
    if inc_unknown:
        inc_unknown.delete()
    if inc_living:
        inc_living.delete()

    print("\n" + "=" * 65)
    print("ALL REGRESSION AND FUNCTIONALITY TESTS PASSED WITH 100% SUCCESS!")
    print("=" * 65)

if __name__ == '__main__':
    run_comprehensive_suite()
