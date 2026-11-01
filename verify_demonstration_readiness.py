"""
Comprehensive Verification Script for Bustard Beacon Demonstration Readiness
Checks Researcher Dashboard, Admin, Forest Officer, Ranger, Medical dashboards,
API analytics data, charts, images, and user accounts.
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'bustard_beacon.settings')
django.setup()

from django.test import Client
from django.contrib.auth import authenticate, get_user_model
from django.db.models import Count
from core.models import (
    ConservationZone, Bustard, Incident, PatrolAssignment, AssignmentAttachment,
    MedicalCase, MedicalTreatment, BustardMovement,
    ConservationReport, TourismRecord, IncidentImage
)
import json

User = get_user_model()

def run_verification():
    print("=" * 70)
    print("  BUSTARD BEACON  DEMONSTRATION READINESS VERIFICATION")
    print("=" * 70)
    
    # 1. Verify Admin Account
    print("\n[1] Verifying Administrator Account & Credentials...")
    admin_user = authenticate(username='admin', password='admin123')
    assert admin_user is not None, "FAILED: Admin authentication failed!"
    assert admin_user.is_superuser, "FAILED: Admin is not superuser!"
    print(f"  [PASS] Admin authenticated: {admin_user.username} (Role: {admin_user.profile.role}, Superuser: {admin_user.is_superuser})")
    
    # 2. Verify Departmental Demo Accounts
    print("\n[2] Verifying Role Accounts...")
    roles = [
        ('officer_solapur', 'officer123', 'FOREST_OFFICER'),
        ('ranger_nannaj', 'ranger123', 'RANGER'),
        ('dr_vet_solapur', 'vet123', 'MEDICAL_TEAM'),
        ('dr_researcher', 'research123', 'RESEARCHER'),
    ]
    for username, pwd, role in roles:
        u = authenticate(username=username, password=pwd)
        assert u is not None, f"FAILED: User {username} authentication failed!"
        assert u.profile.role == role, f"FAILED: User {username} role mismatch! Expected {role}, got {u.profile.role}"
        print(f"  [PASS] Role User authenticated: {u.username} ({u.profile.role})")
        
    # 3. Verify Database Records
    print("\n[3] Verifying Database Record Quantities...")
    counts = {
        'Zones': ConservationZone.objects.count(),
        'Bustards': Bustard.objects.count(),
        'Living Bustards': Bustard.objects.filter(death_record__isnull=True).count(),
        'Incidents': Incident.objects.count(),
        'Patrol Assignments': PatrolAssignment.objects.count(),
        'Medical Cases': MedicalCase.objects.count(),
        'Medical Treatments': MedicalTreatment.objects.count(),
        'GPS Movements': BustardMovement.objects.count(),
        'Conservation Reports': ConservationReport.objects.count(),
        'Tourism Records': TourismRecord.objects.count(),
        'Incident Images': IncidentImage.objects.count(),
    }
    for k, v in counts.items():
        print(f"  - {k:<22}: {v}")
    
    assert counts['Zones'] == 4, "Expected 4 zones"
    assert counts['Bustards'] >= 15, "Expected >= 15 bustards"
    assert counts['Incidents'] >= 40, "Expected >= 40 incidents"
    assert counts['Medical Cases'] >= 8, "Expected >= 8 medical cases"
    assert counts['GPS Movements'] >= 100, "Expected >= 100 movement points"
    print("  [PASS] All record counts meet or exceed target demonstration thresholds.")

    # 4. Verify Media Files Existence on Disk
    print("\n[4] Verifying Media Files on Disk...")
    bird_images = IncidentImage.objects.filter(bustard__isnull=False)
    missing_files = 0
    for img in bird_images:
        if not os.path.exists(img.image.path):
            print(f"  [FAIL] Missing image file: {img.image.path}")
            missing_files += 1
    assert missing_files == 0, f"{missing_files} bird image files missing on disk!"
    print(f"  [PASS] All {bird_images.count()} Bustard profile images exist on disk.")

    # 5. Test Researcher API Analytics Data Endpoint
    print("\n[5] Testing Researcher API Analytics Data (/api/analytics-data/)...")
    client = Client()
    client.login(username='dr_researcher', password='research123')
    
    response = client.get('/api/analytics-data/')
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    data = json.loads(response.content.decode('utf-8'))
    print(f"  - API returned keys: {list(data.keys())}")
    
    # Check Categories Chart
    categories = data.get('categories', {})
    cat_labels = categories.get('labels', [])
    cat_data = categories.get('data', [])
    cat_total = sum(cat_data)
    print(f"  - Category Distribution: {len(cat_labels)} categories, Total Incidents = {cat_total}")
    assert len(cat_labels) > 0 and cat_total > 0, "Categories chart data is empty!"
    
    # Check Zones Chart
    zones = data.get('zones', {})
    zone_labels = zones.get('labels', [])
    zone_data = zones.get('data', [])
    zone_total = sum(zone_data)
    print(f"  - Zone Distribution: {len(zone_labels)} zones, Total Incidents = {zone_total}")
    assert len(zone_labels) > 0 and zone_total > 0, "Zones chart data is empty!"
    
    # Check Priorities Chart
    priorities = data.get('priorities', {})
    pri_labels = priorities.get('labels', [])
    pri_data = priorities.get('data', [])
    pri_total = sum(pri_data)
    print(f"  - Priority Distribution: {len(pri_labels)} priority levels, Total = {pri_total}")
    assert len(pri_labels) > 0 and pri_total > 0, "Priorities chart data is empty!"
    
    # Check Medical Cases Chart (THE KEY FIX REQUESTED)
    medical = data.get('medical', {})
    med_labels = medical.get('labels', [])
    med_data = medical.get('data', [])
    med_total = sum(med_data)
    print(f"  - Medical Cases Distribution: Labels: {med_labels}, Data: {med_data}, Total = {med_total}")
    assert len(med_labels) == 5, f"Expected 5 medical labels, got {len(med_labels)}"
    assert med_total >= 6, f"Expected >= 6 medical cases in chart, got {med_total}!"
    print(f"  [PASS] Medical cases chart is fully populated with {med_total} cases across statuses!")
    
    # Check Timeline Chart
    timeline = data.get('timeline', {})
    t_labels = timeline.get('labels', [])
    sightings = timeline.get('sightings', [])
    movements = timeline.get('movements', [])
    print(f"  - Timeline: {len(t_labels)} days, Sightings sum = {sum(sightings)}, Movements sum = {sum(movements)}")
    assert len(t_labels) >= 28, f"Expected >= 28 timeline days, got {len(t_labels)}"
    assert sum(sightings) > 0, "Timeline sightings are all zero!"
    assert sum(movements) > 0, "Timeline movements are all zero!"
    print(f"  [PASS] Timeline chart is fully populated over {len(t_labels)} days.")
    
    # 6. Test Researcher Dashboard Page & Context Insights
    print("\n[6] Testing Researcher Dashboard Page (/research/dashboard/)...")
    resp_dashboard = client.get('/research/dashboard/')
    assert resp_dashboard.status_code == 200, f"Dashboard returned {resp_dashboard.status_code}"
    content = resp_dashboard.content.decode('utf-8')
    assert "Research & Conservation Dashboard" in content, "Dashboard title not found"
    assert "No zone data available for this period." not in content, "Error: zone stats empty!"
    assert "No automated insights could be generated." not in content, "Error: insights empty!"
    assert "Nannaj Core Breeding Sanctuary" in content, "Error: Nannaj Core not in zone comparison!"
    assert "Follow-up:" in content, "Error: Insights follow-up recommendations not rendered!"
    
    from core.services.analytics_service import get_analytics_data
    from core.views.research_views import parse_date_range
    from_date, to_date = parse_date_range(resp_dashboard.wsgi_request)
    dash_analytics = get_analytics_data(from_date, to_date)
    print(f"  - Dashboard KPI Sightings: {dash_analytics['total_sightings']}, Total Incidents: {dash_analytics['total_incidents']}")
    print(f"  - Dashboard Insights Generated: {len(dash_analytics['insights'])}")
    print(f"  - Dashboard Zone Stats: {len(dash_analytics['zone_stats'])} zones analyzed")
    assert len(dash_analytics['insights']) >= 4, "Expected >= 4 research insights!"
    assert len(dash_analytics['zone_stats']) == 4, "Expected 4 zone stats!"
    assert dash_analytics['medical_incident_count'] > 0, "Expected medical count > 0!"
    print("  [PASS] Researcher dashboard renders cleanly with complete comparative insights and zone analytics.")
    
    # 7. Test Forest Officer Dashboard
    print("\n[7] Testing Forest Officer Dashboard (/officer/dashboard/)...")
    client.login(username='officer_solapur', password='officer123')
    resp_fo = client.get('/officer/dashboard/')
    assert resp_fo.status_code == 200, f"Forest Officer dashboard returned {resp_fo.status_code}"
    fo_content = resp_fo.content.decode('utf-8')
    assert "Forest Officer Command Center" in fo_content
    # Check pending verification items
    pending_count = Incident.objects.filter(status='PENDING').count()
    print(f"  - Pending incidents in queue for Forest Officer verification: {pending_count}")
    assert pending_count >= 5, f"Expected >= 5 pending incidents for FO demo, got {pending_count}"
    print("  [PASS] Forest Officer dashboard has live pending incidents ready for verification demo.")
    
    # 8. Test Field Ranger Mode
    print("\n[8] Testing Ranger Field Mode (/ranger/field-mode/)...")
    client.login(username='ranger_nannaj', password='ranger123')
    resp_ranger = client.get('/ranger/field-mode/')
    assert resp_ranger.status_code == 200, f"Ranger field mode returned {resp_ranger.status_code}"
    ranger_content = resp_ranger.content.decode('utf-8')
    assert "Active Mode" not in ranger_content, "Error: Active Mode toggle still present in Ranger view!"
    print("  [PASS] Ranger field mode accessible; verified Active Mode toggle is removed.")
    
    # 9. Test Medical Team Dashboard
    print("\n[9] Testing Medical Team Dashboard (/medical/dashboard/)...")
    client.login(username='dr_vet_solapur', password='vet123')
    resp_med = client.get('/medical/dashboard/')
    assert resp_med.status_code == 200, f"Medical dashboard returned {resp_med.status_code}"
    med_content = resp_med.content.decode('utf-8')
    assert "Veterinary Medical Rescue Dashboard" in med_content
    active_cases = MedicalCase.objects.filter(status__in=['ACTIVE', 'UNDER_TREATMENT', 'REHABILITATION']).count()
    print(f"  - Active/Rehabilitation clinical cases: {active_cases}")
    assert active_cases >= 3, f"Expected >= 3 active clinical cases, got {active_cases}"
    print("  [PASS] Medical dashboard has active ICU, Rehabilitation, and Pre-Release cases.")

    # 10. Test Admin Panel & Birds Gallery
    print("\n[10] Testing Admin Panel & Bird Registry (/admin-panel/)...")
    client.login(username='admin', password='admin123')
    resp_admin = client.get('/admin-panel/')
    assert resp_admin.status_code == 200, f"Admin panel returned {resp_admin.status_code}"
    resp_birds = client.get('/admin-panel/birds/')
    assert resp_birds.status_code == 200, f"Admin birds returned {resp_birds.status_code}"
    birds_content = resp_birds.content.decode('utf-8')
    assert "GIB-NNJ-001" in birds_content, "Bird GIB-NNJ-001 not found in registry"
    assert "Maldhok King" in birds_content, "Bird Maldhok King not found in registry"
    print("  [PASS] Admin Panel and Great Indian Bustard registry render with complete profiles.")

    print("\n" + "=" * 70)
    print("  ALL 10 VERIFICATION CHECKS PASSED WITH 100% SUCCESS!")
    print("=" * 70)

if __name__ == '__main__':
    run_verification()
