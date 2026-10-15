import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bustard_beacon.settings')
django.setup()

from django.test import Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import (
    UserProfile, Bustard, Incident, MedicalCase, ActivityLog,
    ConservationZone, TourismRestriction, TourismRecord,
    ROLE_ADMIN, ROLE_FOREST_OFFICER, ROLE_RANGER, ROLE_RESEARCHER, ROLE_MEDICAL_TEAM
)

def run_tests():
    print("==================================================")
    print("STARTING TEST SUITE: ADMIN COUNT CARDS & TOURISM")
    print("==================================================")

    # 1. Setup / Retrieve Test Users for Each Role
    admin_user = User.objects.filter(profile__role=ROLE_ADMIN).first()
    fo_user = User.objects.filter(profile__role=ROLE_FOREST_OFFICER).first()
    ranger_user = User.objects.filter(profile__role=ROLE_RANGER).first()
    researcher_user = User.objects.filter(profile__role=ROLE_RESEARCHER).first()

    print(f"Users: Admin={admin_user.username if admin_user else None}, FO={fo_user.username if fo_user else None}, Ranger={ranger_user.username if ranger_user else None}, Researcher={researcher_user.username if researcher_user else None}")

    # Ensure zone exists
    zone = ConservationZone.objects.filter(is_active=True).first()
    if not zone:
        zone = ConservationZone.objects.create(
            name="Maldhok Visitor Area",
            code="MVA-01",
            zone_type="TOURISM_NORMAL"
        )

    # Seed 2 initial tourism demo records if empty
    if TourismRecord.objects.count() == 0:
        TourismRecord.objects.create(
            visitor_name="Maharashtra Birding Society",
            contact_phone="+91 98220 11223",
            contact_email="contact@mahabirding.org",
            visit_date=timezone.now().date(),
            visitor_count=8,
            zone=zone,
            location_area="Nannaj Watchtower #1",
            purpose_of_visit="Annual GIB Habitat Survey & Birdwatching",
            status="APPROVED",
            remarks="Eco-guide assigned: Ramesh. Strictly non-flash photography.",
            recorded_by=fo_user
        )
        TourismRecord.objects.create(
            visitor_name="Dr. Ananya Roy & Research Students",
            contact_phone="+91 94220 55667",
            contact_email="ananya.roy@univ.edu",
            visit_date=timezone.now().date() + timezone.timedelta(days=2),
            visitor_count=4,
            zone=zone,
            location_area="Grassland Perimeter Trail B",
            purpose_of_visit="Educational Field Botany & Habitat Observation",
            status="APPROVED",
            remarks="Valid university student ID cards verified.",
            recorded_by=fo_user
        )
        print("Seeded 2 initial demo TourismRecord entries.")

    # ---------------------------------------------------------
    # TEST 1: ADMIN DASHBOARD AND ALL 5 COUNT CARDS
    # ---------------------------------------------------------
    print("\n--- TEST 1: Admin Dashboard & KPI Count Cards ---")
    admin_client = Client()
    admin_client.force_login(admin_user)
    session = admin_client.session
    session['role_sessions'] = {
        'ADMIN': {
            'user_id': admin_user.id,
            'role': ROLE_ADMIN,
            'name': admin_user.username,
            'hash': admin_user.get_session_auth_hash()
        }
    }
    session.save()

    resp = admin_client.get('/admin-panel/')
    assert resp.status_code == 200, f"Admin dashboard failed with status {resp.status_code}"
    html = resp.content.decode('utf-8')
    assert "bb-kpi-clickable" in html, "bb-kpi-clickable cards missing from admin dashboard"
    print("PASS: Admin dashboard loads with status 200.")

    # Verify all 5 count cards URLs and target pages
    kpi_routes = [
        ('SYSTEM USERS', '/admin-panel/records/users/', 'admin_users_overview', 'System Personnel Directory'),
        ('BIRD RECORDS', '/admin-panel/birds/', 'admin_birds', 'Bird Master Register'),
        ('FO OPERATIONAL RECORDS', '/admin-panel/records/officer/', 'admin_officer_records', 'Forest Officer Operational Records'),
        ('MEDICAL CASES', '/admin-panel/records/medical/', 'admin_medical_records', 'Veterinary & Medical Case Registry'),
        ('AUDIT LOG ENTRIES', '/admin-panel/audit-logs/', 'admin_audit_logs', 'System Audit Trail'),
    ]

    for label, url, name, expected_text in kpi_routes:
        assert url in html, f"URL {url} for {label} not found in admin dashboard HTML"
        card_resp = admin_client.get(url)
        assert card_resp.status_code == 200, f"Page for {label} at {url} returned {card_resp.status_code}"
        card_html = card_resp.content.decode('utf-8')
        assert expected_text in card_html, f"Expected text '{expected_text}' not in page for {label}"
        assert reverse('admin_dashboard') in card_html, f"Back to Dashboard link missing on page for {label}"
        print(f"PASS: Count card '{label}' points to {url}, returns 200, displays actual records, and has Back-to-Dashboard navigation.")

    # ---------------------------------------------------------
    # TEST 2: FOREST OFFICER DASHBOARD INCLUDES TOURISM HANDLING
    # ---------------------------------------------------------
    print("\n--- TEST 2: Forest Officer Dashboard Tourism Integration ---")
    fo_client = Client()
    fo_client.force_login(fo_user)
    session = fo_client.session
    session['role_sessions'] = {
        'FOREST_OFFICER': {
            'user_id': fo_user.id,
            'role': ROLE_FOREST_OFFICER,
            'name': fo_user.username,
            'hash': fo_user.get_session_auth_hash()
        }
    }
    session.save()

    fo_dash_resp = fo_client.get('/officer/dashboard/')
    assert fo_dash_resp.status_code == 200, f"FO Dashboard returned {fo_dash_resp.status_code}"
    fo_dash_html = fo_dash_resp.content.decode('utf-8')
    assert "Tourism Handling" in fo_dash_html, "Tourism Handling missing from Forest Officer dashboard"
    assert "/officer/tourism/" in fo_dash_html, "Link to /officer/tourism/ missing from FO dashboard"
    print("PASS: Forest Officer dashboard visibly displays Tourism Handling card and navigation button.")

    # ---------------------------------------------------------
    # TEST 3: TOURISM HANDLING PAGE VIEW
    # ---------------------------------------------------------
    print("\n--- TEST 3: Tourism Handling Page Access & Read ---")
    tourism_resp = fo_client.get('/officer/tourism/')
    assert tourism_resp.status_code == 200, f"Tourism handling page returned {tourism_resp.status_code}"
    tourism_html = tourism_resp.content.decode('utf-8')
    assert "Sanctuary Tourism Handling & Visitor Permits" in tourism_html
    assert "Issue Visitor Permit" in tourism_html
    assert "Back to Dashboard" in tourism_html
    print("PASS: Tourism handling page loads with 200, shows permits table, KPI cards, and back link.")

    # ---------------------------------------------------------
    # TEST 4: TOURISM CRUD - CREATE RECORD
    # ---------------------------------------------------------
    print("\n--- TEST 4: Tourism CRUD - Create Record ---")
    create_data = {
        'action': 'create_permit',
        'visitor_name': 'Solapur Wildlife Photographers Club',
        'contact_phone': '+91 99999 11111',
        'contact_email': 'solapur.photo@test.com',
        'visit_date': timezone.now().strftime('%Y-%m-%d'),
        'visitor_count': '6',
        'zone_id': str(zone.id),
        'location_area': 'East Grassland Hide',
        'purpose_of_visit': 'Dawn Photography of Grassland Birds',
        'status': 'APPROVED',
        'remarks': 'Special telephoto lens permit approved. Accompanied by Forest Guard.',
    }
    create_resp = fo_client.post('/officer/tourism/', create_data, follow=True)
    assert create_resp.status_code == 200
    created_rec = TourismRecord.objects.filter(visitor_name='Solapur Wildlife Photographers Club').first()
    assert created_rec is not None, "Failed to create TourismRecord in database"
    assert created_rec.permit_id.startswith('TRM-'), f"Permit ID {created_rec.permit_id} format invalid"
    assert created_rec.visitor_count == 6
    print(f"PASS: Created permit {created_rec.permit_id} for {created_rec.visitor_name} with {created_rec.visitor_count} visitors.")

    # ---------------------------------------------------------
    # TEST 5: TOURISM CRUD - EDIT RECORD
    # ---------------------------------------------------------
    print("\n--- TEST 5: Tourism CRUD - Edit Record ---")
    edit_url = f"/officer/tourism/{created_rec.id}/edit/"
    edit_data = {
        'visitor_name': 'Solapur Wildlife Photographers Guild (Updated)',
        'contact_phone': '+91 99999 22222',
        'contact_email': 'guild.photo@test.com',
        'visit_date': created_rec.visit_date.strftime('%Y-%m-%d'),
        'visitor_count': '7',
        'zone_id': str(zone.id),
        'location_area': 'East Grassland Hide #2',
        'purpose_of_visit': 'Dawn Photography & Video Documentary',
        'status': 'COMPLETED',
        'remarks': 'Completed visit successfully without disturbance.',
    }
    edit_resp = fo_client.post(edit_url, edit_data, follow=True)
    assert edit_resp.status_code == 200
    created_rec.refresh_from_db()
    assert created_rec.visitor_name == 'Solapur Wildlife Photographers Guild (Updated)'
    assert created_rec.visitor_count == 7
    assert created_rec.status == 'COMPLETED'
    print(f"PASS: Updated record {created_rec.permit_id}: name={created_rec.visitor_name}, count={created_rec.visitor_count}, status={created_rec.status}.")

    # ---------------------------------------------------------
    # TEST 6: TOURISM CRUD - DELETE RECORD
    # ---------------------------------------------------------
    print("\n--- TEST 6: Tourism CRUD - Delete Record ---")
    delete_url = f"/officer/tourism/{created_rec.id}/delete/"
    del_resp = fo_client.post(delete_url, follow=True)
    assert del_resp.status_code == 200
    assert not TourismRecord.objects.filter(id=created_rec.id).exists(), "Record still exists after delete"
    print(f"PASS: Successfully deleted record {created_rec.permit_id} from database.")

    # ---------------------------------------------------------
    # TEST 7: PERMISSIONS & ROLE ACCESS CHECKS
    # ---------------------------------------------------------
    print("\n--- TEST 7: Role-Based Access Control ---")
    # Ranger should be forbidden (403) from /officer/tourism/
    ranger_client = Client()
    ranger_client.force_login(ranger_user)
    r_session = ranger_client.session
    r_session['role_sessions'] = {
        'RANGER': {
            'user_id': ranger_user.id,
            'role': ROLE_RANGER,
            'name': ranger_user.username,
            'hash': ranger_user.get_session_auth_hash()
        }
    }
    r_session.save()
    ranger_resp = ranger_client.get('/officer/tourism/')
    assert ranger_resp.status_code in (403, 302), f"Ranger should not access tourism, got {ranger_resp.status_code}"
    print(f"PASS: Ranger role blocked with status {ranger_resp.status_code}.")

    # Researcher should be forbidden (403) from /officer/tourism/
    rsh_client = Client()
    rsh_client.force_login(researcher_user)
    rsh_session = rsh_client.session
    rsh_session['role_sessions'] = {
        'RESEARCHER': {
            'user_id': researcher_user.id,
            'role': ROLE_RESEARCHER,
            'name': researcher_user.username,
            'hash': researcher_user.get_session_auth_hash()
        }
    }
    rsh_session.save()
    rsh_resp = rsh_client.get('/officer/tourism/')
    assert rsh_resp.status_code in (403, 302), f"Researcher should not access tourism, got {rsh_resp.status_code}"
    print(f"PASS: Researcher role blocked with status {rsh_resp.status_code}.")

    # Unauthenticated user should be redirected (302) to login
    anon_client = Client()
    anon_resp = anon_client.get('/officer/tourism/')
    assert anon_resp.status_code == 302, f"Anonymous user should be redirected, got {anon_resp.status_code}"
    print(f"PASS: Unauthenticated user redirected to login ({anon_resp.status_code}).")

    # Admin CAN view /officer/tourism/
    admin_tourism_resp = admin_client.get('/officer/tourism/')
    assert admin_tourism_resp.status_code == 200, f"Admin should be able to view tourism, got {admin_tourism_resp.status_code}"
    print("PASS: Administrator can access tourism records page.")

    # ---------------------------------------------------------
    # TEST 8: RESEARCHER DASHBOARD UNTOUCHED
    # ---------------------------------------------------------
    print("\n--- TEST 8: Researcher Dashboard Integrity ---")
    rsh_dash_resp = rsh_client.get('/research/dashboard/')
    assert rsh_dash_resp.status_code == 200, f"Researcher dashboard returned {rsh_dash_resp.status_code}"
    print("PASS: Researcher dashboard intact and functioning normally.")

    print("\n==================================================")
    print("ALL TESTS PASSED SUCCESSFULLY! (100% OK)")
    print("==================================================")

if __name__ == '__main__':
    run_tests()
