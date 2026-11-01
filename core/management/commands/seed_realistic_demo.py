import os
import shutil
from pathlib import Path
from datetime import timedelta, date, time
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.utils import timezone
from django.conf import settings
from django.db import transaction

from core.models import (
    UserProfile, ConservationZone, TourismRestriction, TourismRecord,
    Bustard, BustardMovement, BreedingRecord, BirthRecord, DeathRecord,
    MissingBirdRecord, Incident, IncidentLocation, IncidentImage,
    PatrolAssignment, AssignmentAttachment, MedicalCase, MedicalTreatment,
    MedicalEquipment, Complaint, Notification, ActivityLog, ConservationReport,
    ROLE_ADMIN, ROLE_FOREST_OFFICER, ROLE_RANGER, ROLE_MEDICAL_TEAM, ROLE_RESEARCHER,
    DATA_ENV_PRODUCTION
)


class Command(BaseCommand):
    help = "Populate comprehensive, realistic, interconnected conservation field data for Bustard Beacon."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clean-demo-artifacts',
            action='store_true',
            default=True,
            help='Clean up ad-hoc test and placeholder records while strictly preserving Administrator and key accounts.'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=" * 76))
        self.stdout.write(self.style.NOTICE("  BUSTARD BEACON — COMPREHENSIVE CONSERVATION FIELD DATA SEEDING"))
        self.stdout.write(self.style.NOTICE("=" * 76))

        # -------------------------------------------------------------
        # STEP 1: Deploy Demo Images to Media
        # -------------------------------------------------------------
        self.stdout.write("\n[1/10] Deploying authentic Great Indian Bustard demo images to media storage...")
        base_dir = Path(settings.BASE_DIR)
        demo_img_root = base_dir / 'Bustard_Beacon_Demo_Images'
        media_root = Path(settings.MEDIA_ROOT)

        inc_photo_dir = media_root / 'incident_photos' / '2026' / '11'
        birth_dir = media_root / 'birth_records' / '2026' / '11'
        assign_dir = media_root / 'assignment_evidence' / '2026' / '11'
        zone_dir = media_root / 'conservation_zones'
        profile_dir = media_root / 'profile_images'

        for d in [inc_photo_dir, birth_dir, assign_dir, zone_dir, profile_dir]:
            d.mkdir(parents=True, exist_ok=True)

        copied_count = 0
        if demo_img_root.exists():
            for f in (demo_img_root / '01_Birds').glob('*.*'):
                shutil.copy2(f, inc_photo_dir / f.name)
                copied_count += 1
            for f in (demo_img_root / '02_Incidents').glob('*.*'):
                shutil.copy2(f, inc_photo_dir / f.name)
                shutil.copy2(f, assign_dir / f.name)
                copied_count += 1
            for f in (demo_img_root / '03_Medical').glob('*.*'):
                shutil.copy2(f, inc_photo_dir / f.name)
                copied_count += 1
            chick_f = demo_img_root / '01_Birds' / 'GIB_015.jpeg'
            if chick_f.exists():
                shutil.copy2(chick_f, birth_dir / chick_f.name)
            for f in (demo_img_root / '04_Conservation_Zones').glob('*.*'):
                shutil.copy2(f, zone_dir / f.name)
                copied_count += 1

        self.stdout.write(self.style.SUCCESS(f"  [OK] Media files ready ({copied_count} source images synchronized)."))

        with transaction.atomic():
            # -------------------------------------------------------------
            # STEP 2: Manage User Accounts (Preserve Admin & Real Accounts)
            # -------------------------------------------------------------
            self.stdout.write("\n[2/10] Verifying Administrator and authentic staff accounts...")

            PRESERVED_USERNAMES = {
                'admin', 'officer_solapur', 'ranger_nannaj', 'dr_vet_solapur', 'dr_researcher',
                'dnyaneshc2006', 'smchaudhari1976', 'dny101', 'pramod.vaidya25'
            }

            deleted_users_count, _ = User.objects.exclude(username__in=PRESERVED_USERNAMES).delete()
            self.stdout.write(f"  [Clean] Removed {deleted_users_count} obsolete/generic test accounts.")

            # Administrator account (Preserved)
            admin_user, admin_created = User.objects.get_or_create(
                username='admin',
                defaults={
                    'email': 'cdnyanesh2006@gmail.com',
                    'first_name': 'Chief',
                    'last_name': 'Conservator of Forests',
                    'is_staff': True,
                    'is_superuser': True,
                }
            )
            admin_user.email = 'cdnyanesh2006@gmail.com'
            admin_user.is_staff = True
            admin_user.is_superuser = True
            if admin_created or not admin_user.has_usable_password():
                admin_user.set_password('admin123')
            admin_user.save()

            admin_profile, _ = UserProfile.objects.get_or_create(user=admin_user)
            admin_profile.role = ROLE_ADMIN
            admin_profile.badge_number = 'ADM-MH-001'
            admin_profile.phone_number = '+91 98220 11001'
            admin_profile.force_password_change = False
            admin_profile.save()

            # Departmental staff accounts
            staff_accounts_data = [
                {
                    'username': 'officer_solapur',
                    'password': 'officer123',
                    'email': 'officer.nannaj@forest.gov.in',
                    'first_name': 'Rajesh',
                    'last_name': 'Deshmukh',
                    'role': ROLE_FOREST_OFFICER,
                    'badge': 'FO-SLP-101',
                    'phone': '+91 94220 33412',
                },
                {
                    'username': 'ranger_nannaj',
                    'password': 'ranger123',
                    'email': 'ranger.nannaj@forest.gov.in',
                    'first_name': 'Vikram',
                    'last_name': 'Patil',
                    'role': ROLE_RANGER,
                    'badge': 'RNG-NNJ-204',
                    'phone': '+91 98230 45671',
                    'lat': 17.8242,
                    'lng': 75.8465,
                },
                {
                    'username': 'dr_vet_solapur',
                    'password': 'vet123',
                    'email': 'dr.vet@bustardbeacon.org',
                    'first_name': 'Dr. Sunita',
                    'last_name': 'Kulkarni',
                    'role': ROLE_MEDICAL_TEAM,
                    'badge': 'VET-SLP-302',
                    'phone': '+91 98221 77890',
                },
                {
                    'username': 'dr_researcher',
                    'password': 'research123',
                    'email': 'researcher@wii.gov.in',
                    'first_name': 'Dr. Amit',
                    'last_name': 'Joshi',
                    'role': ROLE_RESEARCHER,
                    'badge': 'WL-RSH-501',
                    'phone': '+91 94225 88901',
                },
            ]

            seeded_users = {ROLE_ADMIN: admin_user}
            for udata in staff_accounts_data:
                user, created = User.objects.get_or_create(username=udata['username'], defaults={
                    'email': udata['email'],
                    'first_name': udata['first_name'],
                    'last_name': udata['last_name'],
                    'is_staff': (udata['role'] in [ROLE_ADMIN, ROLE_FOREST_OFFICER]),
                    'is_superuser': False,
                })
                user.set_password(udata['password'])
                user.email = udata['email']
                user.first_name = udata['first_name']
                user.last_name = udata['last_name']
                user.is_active = True
                user.save()

                p, _ = UserProfile.objects.get_or_create(user=user)
                p.role = udata['role']
                p.badge_number = udata['badge']
                p.phone_number = udata['phone']
                p.force_password_change = False
                if udata['role'] == ROLE_RANGER:
                    p.current_latitude = udata.get('lat', 17.8228)
                    p.current_longitude = udata.get('lng', 75.8458)
                    p.location_updated_at = timezone.now()
                    p.is_active_field_mode = True
                    p.availability_status = 'AVAILABLE'
                elif udata['role'] == ROLE_MEDICAL_TEAM:
                    p.availability_status = 'AVAILABLE'
                p.save()
                seeded_users[udata['role']] = user

            # Additional field patrol staff for operational realism
            additional_rangers = [
                ('ranger_shinde', 'ranger123', 'anand.shinde@forest.gov.in', 'Anand', 'Shinde', 'RNG-NNJ-205', '+91 98231 12345', 17.8310, 75.8410),
                ('ranger_pawar', 'ranger123', 'sunita.pawar@forest.gov.in', 'Sunita', 'Pawar', 'RNG-NNJ-206', '+91 98232 67890', 17.8180, 75.8520),
            ]
            for r_uname, r_pass, r_email, r_fn, r_ln, r_bdg, r_ph, r_lat, r_lng in additional_rangers:
                r_user, _ = User.objects.get_or_create(username=r_uname, defaults={
                    'email': r_email,
                    'first_name': r_fn,
                    'last_name': r_ln,
                    'is_staff': False,
                    'is_superuser': False,
                })
                r_user.set_password(r_pass)
                r_user.is_active = True
                r_user.save()
                r_p, _ = UserProfile.objects.get_or_create(user=r_user)
                r_p.role = ROLE_RANGER
                r_p.badge_number = r_bdg
                r_p.phone_number = r_ph
                r_p.current_latitude = r_lat
                r_p.current_longitude = r_lng
                r_p.location_updated_at = timezone.now()
                r_p.is_active_field_mode = True
                r_p.availability_status = 'AVAILABLE'
                r_p.save()

            self.stdout.write(self.style.SUCCESS("  [OK] Admin and departmental staff verified."))

            # -------------------------------------------------------------
            # STEP 3: Authentic Conservation Zones
            # -------------------------------------------------------------
            self.stdout.write("\n[3/10] Establishing authentic Nannaj Sanctuary Conservation Zones...")
            ConservationZone.objects.exclude(code__in=['ZONE-NNJ-CORE', 'ZONE-NNJ-BUFF', 'ZONE-NNJ-TOUR', 'ZONE-KRM-CORR']).delete()

            fo_user = seeded_users[ROLE_FOREST_OFFICER]

            zones_spec = [
                {
                    'code': 'ZONE-NNJ-CORE',
                    'name': 'Nannaj Core Breeding Sanctuary',
                    'zone_type': 'BREEDING',
                    'color_hex': '#d32f2f',
                    'description': (
                        'Reference Conservation Boundary: Enclosed primary courtship display lek and nesting grounds. '
                        'Strict ground disturbance prohibition enforced to safeguard critically endangered clutches and brooding females.'
                    ),
                    'boundary_geojson': '[[17.8360, 75.8360], [17.8360, 75.8580], [17.8120, 75.8580], [17.8120, 75.8360]]',
                    'tourism_status': 'PROHIBITED',
                    'restriction_reason': 'Core breeding sanctuary — strictly prohibited to non-essential personnel to prevent courtship disturbance and ground-nest trampling.'
                },
                {
                    'code': 'ZONE-NNJ-BUFF',
                    'name': 'Solapur Grassland Buffer Zone',
                    'zone_type': 'BUFFER_RESTRICTED',
                    'color_hex': '#f57c00',
                    'description': (
                        'Reference Conservation Boundary: Agro-pastoral buffer mosaic surrounding Nannaj Core. '
                        'Monitored foraging route connecting seasonal grasslands; anti-poaching and transmission line inspection zone.'
                    ),
                    'boundary_geojson': '[[17.8520, 75.8200], [17.8520, 75.8720], [17.7920, 75.8720], [17.7920, 75.8200]]',
                    'tourism_status': 'RESTRICTED',
                    'restriction_reason': 'Buffer zone monitoring area — entry restricted to escorted research teams and approved guided monitoring patrols.'
                },
                {
                    'code': 'ZONE-NNJ-TOUR',
                    'name': 'Maldhok Eco-Tourism & Visitor Area',
                    'zone_type': 'TOURISM_NORMAL',
                    'color_hex': '#2e7d32',
                    'description': (
                        'Reference Conservation Boundary: Regulated eco-tourism zone with dedicated watchtowers, Nature Interpretation Centre, '
                        'and designated visitor walking trails operating under strict sanctuary naturalist supervision.'
                    ),
                    'boundary_geojson': '[[17.8080, 75.8380], [17.8080, 75.8620], [17.7850, 75.8620], [17.7850, 75.8380]]',
                    'tourism_status': 'ALLOWED',
                    'restriction_reason': 'Guided visitor trail and interpretation area open between 06:00–10:00 AM & 04:00–06:30 PM with valid sanctuary permits.'
                },
                {
                    'code': 'ZONE-KRM-CORR',
                    'name': 'Gangewadi-Karmala Dispersal Corridor',
                    'zone_type': 'CORE_CONSERVATION',
                    'color_hex': '#1976d2',
                    'description': (
                        'Reference Conservation Boundary: Strategic seasonal dispersal corridor connecting southern Solapur grasslands '
                        'with northern steppe habitats. Priority corridor for high-voltage power line bird flight diverter installation.'
                    ),
                    'boundary_geojson': '[[17.8820, 75.8120], [17.8820, 75.8550], [17.8480, 75.8550], [17.8480, 75.8120]]',
                    'tourism_status': 'RESTRICTED',
                    'restriction_reason': 'Strategic wildlife corridor — heavy vehicle transit restricted; transmission line monitoring active.'
                },
            ]

            db_zones = {}
            for z_data in zones_spec:
                zone_obj, _ = ConservationZone.objects.update_or_create(
                    code=z_data['code'],
                    defaults={
                        'name': z_data['name'],
                        'zone_type': z_data['zone_type'],
                        'color_hex': z_data['color_hex'],
                        'description': z_data['description'],
                        'boundary_geojson': z_data['boundary_geojson'],
                        'responsible_officer': fo_user,
                        'is_active': True,
                    }
                )
                db_zones[z_data['code']] = zone_obj

                TourismRestriction.objects.update_or_create(
                    zone=zone_obj,
                    defaults={
                        'status': z_data['tourism_status'],
                        'restriction_reason': z_data['restriction_reason'],
                        'valid_from': date(2026, 1, 1),
                        'valid_until': date(2026, 12, 31),
                        'updated_by': fo_user,
                    }
                )

            seeded_users[ROLE_RANGER].profile.assigned_zone = db_zones['ZONE-NNJ-CORE']
            seeded_users[ROLE_RANGER].profile.save()

            self.stdout.write(self.style.SUCCESS("  [OK] 4 authentic conservation zones and restrictions configured."))

            # -------------------------------------------------------------
            # STEP 4: Great Indian Bustard Master Register
            # -------------------------------------------------------------
            self.stdout.write("\n[4/10] Populating Great Indian Bustard register (15 birds + images)...")
            Bustard.objects.all().delete()

            now = timezone.now()

            birds_spec = [
                {
                    'tag_id': 'GIB-NNJ-001',
                    'name': 'Maldhok King',
                    'sex': 'MALE',
                    'age_class': 'ADULT',
                    'health_status': 'HEALTHY',
                    'birth_year': 2017,
                    'zone': db_zones['ZONE-NNJ-CORE'],
                    'notes': 'Dominant breeding male known for prominent courtship display in Nannaj Core lek. Frequently observed displaying gular pouch.',
                    'last_seen': now - timedelta(hours=14),
                    'img': 'incident_photos/2026/11/GIB_001.jpg',
                },
                {
                    'tag_id': 'GIB-NNJ-002',
                    'name': 'Solapur Queen',
                    'sex': 'FEMALE',
                    'age_class': 'ADULT',
                    'health_status': 'HEALTHY',
                    'birth_year': 2019,
                    'zone': db_zones['ZONE-NNJ-CORE'],
                    'notes': 'High-fertility adult breeding female. Successful clutch incubation in 2024 and 2025. Roosts in northern Sehima grass patch.',
                    'last_seen': now - timedelta(hours=8),
                    'img': 'incident_photos/2026/11/GIB_002.jpeg',
                },
                {
                    'tag_id': 'GIB-NNJ-003',
                    'name': 'Sahyadri Jewel',
                    'sex': 'FEMALE',
                    'age_class': 'ADULT',
                    'health_status': 'UNDER_MONITORING',
                    'birth_year': 2020,
                    'zone': db_zones['ZONE-NNJ-BUFF'],
                    'notes': 'Equipped with solar GPS transmitter WII-GIB-03. Shows expansive foraging movements between buffer and agricultural perimeter.',
                    'last_seen': now - timedelta(hours=3),
                    'img': 'incident_photos/2026/11/GIB_003.jpeg',
                },
                {
                    'tag_id': 'GIB-NNJ-004',
                    'name': 'Marathwada Falcon',
                    'sex': 'MALE',
                    'age_class': 'ADULT',
                    'health_status': 'HEALTHY',
                    'birth_year': 2018,
                    'zone': db_zones['ZONE-NNJ-BUFF'],
                    'notes': 'Robust adult male characterized by deep black crown and expansive wingspan (~2.1m). Regular forager in western grasslands.',
                    'last_seen': now - timedelta(days=1, hours=4),
                    'img': 'incident_photos/2026/11/GIB_004.jpeg',
                },
                {
                    'tag_id': 'GIB-NNJ-005',
                    'name': 'Nannaj Pride',
                    'sex': 'MALE',
                    'age_class': 'SUB_ADULT',
                    'health_status': 'HEALTHY',
                    'birth_year': 2022,
                    'zone': db_zones['ZONE-NNJ-CORE'],
                    'notes': 'Sub-adult male showing vigorous territorial activity. Full recovery confirmed following dehydration treatment.',
                    'last_seen': now - timedelta(hours=22),
                    'img': 'incident_photos/2026/11/GIB_005.jpg',
                },
                {
                    'tag_id': 'GIB-NNJ-006',
                    'name': 'Karmala Scout',
                    'sex': 'MALE',
                    'age_class': 'ADULT',
                    'health_status': 'UNDER_MONITORING',
                    'birth_year': 2019,
                    'zone': db_zones['ZONE-KRM-CORR'],
                    'notes': 'Wide-ranging adult male navigating northern dispersal corridor. Tracked closely due to proximity with overhead power lines.',
                    'last_seen': now - timedelta(days=2),
                    'img': 'incident_photos/2026/11/GIB_006.jpeg',
                },
                {
                    'tag_id': 'GIB-NNJ-007',
                    'name': 'Sina Runner',
                    'sex': 'FEMALE',
                    'age_class': 'ADULT',
                    'health_status': 'HEALTHY',
                    'birth_year': 2021,
                    'zone': db_zones['ZONE-NNJ-BUFF'],
                    'notes': 'Healthy adult female observed foraging on dry-season grasshoppers and beetles near the southern buffer riverline.',
                    'last_seen': now - timedelta(days=1, hours=10),
                    'img': 'incident_photos/2026/11/GIB_007.jpeg',
                },
                {
                    'tag_id': 'GIB-NNJ-008',
                    'name': 'Bhimashankar',
                    'sex': 'MALE',
                    'age_class': 'OLD',
                    'health_status': 'HEALTHY',
                    'birth_year': 2015,
                    'zone': db_zones['ZONE-NNJ-CORE'],
                    'notes': 'Veteran resident male of Solapur sanctuary. Well-documented historical lineage; continues to hold southern display territory.',
                    'last_seen': now - timedelta(days=3),
                    'img': 'incident_photos/2026/11/GIB_008.jpeg',
                },
                {
                    'tag_id': 'GIB-NNJ-009',
                    'name': 'Deccan Empress',
                    'sex': 'FEMALE',
                    'age_class': 'ADULT',
                    'health_status': 'HEALTHY',
                    'birth_year': 2020,
                    'zone': db_zones['ZONE-NNJ-CORE'],
                    'notes': 'Successful ground breeder; nested in southern protected enclosure during 2025. Demonstrates high nest vigilance.',
                    'last_seen': now - timedelta(hours=19),
                    'img': 'incident_photos/2026/11/GIB_009.jpeg',
                },
                {
                    'tag_id': 'GIB-NNJ-010',
                    'name': 'Grassland Prince',
                    'sex': 'MALE',
                    'age_class': 'SUB_ADULT',
                    'health_status': 'HEALTHY',
                    'birth_year': 2023,
                    'zone': db_zones['ZONE-NNJ-BUFF'],
                    'notes': 'Active young male offspring of Maldhok King and Deccan Empress. Frequently associates with sub-adult foraging groups.',
                    'last_seen': now - timedelta(days=2, hours=6),
                    'img': 'incident_photos/2026/11/GIB_0010.jpeg',
                },
                {
                    'tag_id': 'GIB-NNJ-011',
                    'name': 'Chandrabhaga',
                    'sex': 'FEMALE',
                    'age_class': 'ADULT',
                    'health_status': 'INJURED',
                    'birth_year': 2021,
                    'zone': db_zones['ZONE-NNJ-BUFF'],
                    'notes': 'Rescued following power transmission line impact in western buffer. Currently under active medical treatment in ICU.',
                    'last_seen': now - timedelta(days=1),
                    'img': 'incident_photos/2026/11/GIB_011.jpeg',
                },
                {
                    'tag_id': 'GIB-NNJ-012',
                    'name': 'Mohol Striker',
                    'sex': 'MALE',
                    'age_class': 'ADULT',
                    'health_status': 'REHABILITATION',
                    'birth_year': 2019,
                    'zone': db_zones['ZONE-NNJ-CORE'],
                    'notes': 'In veterinary recovery enclosure following fence wire entanglement. Wing musculature responding positively to flight exercise.',
                    'last_seen': now - timedelta(days=4),
                    'img': 'incident_photos/2026/11/GIB_012.jpeg',
                },
                {
                    'tag_id': 'GIB-NNJ-013',
                    'name': 'Savitri',
                    'sex': 'FEMALE',
                    'age_class': 'ADULT',
                    'health_status': 'UNDER_MONITORING',
                    'birth_year': 2018,
                    'zone': db_zones['ZONE-NNJ-CORE'],
                    'notes': 'Monitored female exhibiting early pre-breeding scraping behavior in North Core. Nesting enclosure surveillance active.',
                    'last_seen': now - timedelta(hours=11),
                    'img': 'incident_photos/2026/11/GIB_013.jpg',
                },
                {
                    'tag_id': 'GIB-NNJ-014',
                    'name': 'Dharashiv Wanderer',
                    'sex': 'MALE',
                    'age_class': 'ADULT',
                    'health_status': 'MISSING',
                    'birth_year': 2020,
                    'zone': db_zones['ZONE-KRM-CORR'],
                    'notes': 'Subject of active ground search patrol following unconfirmed sightings across district boundary near agricultural mosaic.',
                    'last_seen': now - timedelta(days=8),
                    'img': 'incident_photos/2026/11/GIB_014.jpg',
                },
                {
                    'tag_id': 'GIB-NNJ-015',
                    'name': 'Nanaji Chick',
                    'sex': 'UNKNOWN',
                    'age_class': 'JUVENILE',
                    'health_status': 'HEALTHY',
                    'birth_year': 2026,
                    'zone': db_zones['ZONE-NNJ-CORE'],
                    'notes': 'Healthy young chick successfully hatched in Core Breeding Sanctuary under continuous CCTV and patrol monitoring.',
                    'last_seen': now - timedelta(hours=5),
                    'img': 'incident_photos/2026/11/GIB_015.jpeg',
                },
            ]

            db_birds = {}
            for b_data in birds_spec:
                bird_obj = Bustard.objects.create(
                    tag_id=b_data['tag_id'],
                    name=b_data['name'],
                    species='Great Indian Bustard',
                    sex=b_data['sex'],
                    age_class=b_data['age_class'],
                    health_status=b_data['health_status'],
                    estimated_birth_year=b_data['birth_year'],
                    last_seen_zone=b_data['zone'],
                    last_seen_date=b_data['last_seen'],
                    nesting_notes=b_data['notes'],
                    data_environment=DATA_ENV_PRODUCTION
                )
                db_birds[b_data['tag_id']] = bird_obj

                IncidentImage.objects.create(
                    bustard=bird_obj,
                    image=b_data['img'],
                    caption=f"Official field record portrait: {bird_obj.name} ({bird_obj.tag_id})"
                )

            # Historical deceased bird record
            hist_dead_bird = Bustard.objects.create(
                tag_id='GIB-HIST-098',
                name='Solapur Pioneer',
                species='Great Indian Bustard',
                sex='MALE',
                age_class='OLD',
                health_status='DECEASED',
                estimated_birth_year=2014,
                last_seen_zone=db_zones['ZONE-KRM-CORR'],
                last_seen_date=now - timedelta(days=220),
                nesting_notes='Historic dominant male of Karmala corridor. Deceased November 2024 due to transmission line collision.',
                data_environment=DATA_ENV_PRODUCTION
            )
            DeathRecord.objects.create(
                bustard=hist_dead_bird,
                date_of_death=date(2024, 11, 14),
                cause_of_death='High-Tension Power Line Collision',
                autopsy_summary=(
                    'Post-mortem examination confirmed blunt force thoracic trauma, bilateral clavicle fracture, and localized electrical flash scorch. '
                    'Tissue samples archived at WII national avian repository. Led to mandatory bird flight diverter installation mandate on 33kV corridor.'
                ),
                location_latitude=17.8654,
                location_longitude=75.8321,
                recorded_by=seeded_users[ROLE_FOREST_OFFICER]
            )

            # Birth Record for GIB-NNJ-015
            BirthRecord.objects.create(
                bustard=db_birds['GIB-NNJ-015'],
                hatch_date=date(2026, 8, 12),
                nest_zone=db_zones['ZONE-NNJ-CORE'],
                clutch_reference='CLUTCH-NNJ-2026-01',
                parent_male_tag='GIB-NNJ-001',
                parent_female_tag='GIB-NNJ-002',
                notes='Incubation period 27 days. Chick emerged healthy, weight 84g at hatching. Mother GIB-NNJ-002 providing attentive brooding.',
                birth_image='birth_records/2026/11/GIB_015.jpeg'
            )

            # Breeding records
            BreedingRecord.objects.create(
                bustard=db_birds['GIB-NNJ-001'],
                season_year=2026,
                nest_latitude=17.8285,
                nest_longitude=75.8442,
                clutch_size=1,
                chick_hatch_date=date(2026, 8, 12),
                status='CHICK_REARED_SUCCESSFUL',
                notes='Successful courtship and egg fertilization with Solapur Queen. Chick GIB-NNJ-015 confirmed healthy.',
                recorded_by=seeded_users[ROLE_RESEARCHER]
            )
            BreedingRecord.objects.create(
                bustard=db_birds['GIB-NNJ-009'],
                season_year=2025,
                nest_latitude=17.8210,
                nest_longitude=75.8490,
                clutch_size=1,
                chick_hatch_date=date(2025, 7, 28),
                status='CHICK_REARED_SUCCESSFUL',
                notes='Nesting scrape in dense Heteropogon patch. Successfully fledged male sub-adult Grassland Prince.',
                recorded_by=seeded_users[ROLE_RESEARCHER]
            )

            # Missing Bird Records
            MissingBirdRecord.objects.create(
                bustard=db_birds['GIB-NNJ-014'],
                reported_missing_date=date(2026, 10, 24),
                last_known_latitude=17.8720,
                last_known_longitude=75.8340,
                search_status='ACTIVE_SEARCH',
                notes='Disappeared from northern corridor telemetry coverage. Ground patrol and local farmer informant network mobilized.',
                reported_by=seeded_users[ROLE_RANGER]
            )
            MissingBirdRecord.objects.create(
                bustard=db_birds['GIB-NNJ-006'],
                reported_missing_date=date(2026, 6, 10),
                last_known_latitude=17.8540,
                last_known_longitude=75.8280,
                search_status='FOUND_SAFE',
                notes='Signal temporarily obstructed by terrain shadow.',
                reported_by=seeded_users[ROLE_RANGER],
                found_date=date(2026, 6, 13),
                found_latitude=17.8580,
                found_longitude=75.8240,
                found_by='Ranger Anand Shinde',
                found_notes='Visual observation confirmed healthy bird foraging peacefully in dry scrubland.'
            )

            self.stdout.write(self.style.SUCCESS("  [OK] 15 living Great Indian Bustards, 1 deceased record, and breeding data registered."))

            # -------------------------------------------------------------
            # STEP 5: 42 Comprehensive Incidents Across 30 Days
            # -------------------------------------------------------------
            self.stdout.write("\n[5/10] Generating 42 realistic conservation field incidents & observations...")
            Incident.objects.all().delete()

            rng_patil = seeded_users[ROLE_RANGER]
            res_joshi = seeded_users[ROLE_RESEARCHER]

            # 42 detailed incidents distributed across the past 30 days (Oct 3 - Nov 1, 2026)
            raw_incidents = [
                # 0. Emergency: Chandrabhaga powerline collision (Oct 31)
                {
                    'cat': 'POWERLINE_COLLISION', 'pri': 'CRITICAL', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=1, hours=3),
                    'bird': db_birds['GIB-NNJ-011'], 'zone': db_zones['ZONE-NNJ-BUFF'],
                    'lat': 17.8395, 'lng': 75.8315,
                    'desc': 'EMERGENCY RESCUE: Female GIB-NNJ-011 (Chandrabhaga) impacted an unmarked 33kV electrical transmission wire while taking off in low morning visibility. Sustained right wing contusion and grounded. Rapid veterinary response initiated; bird secured in cushioned transport carrier and dispatched to intensive care.',
                    'vby': fo_user, 'vat': now - timedelta(days=1, hours=2),
                    'notes': 'Verified on-site. Veterinary emergency rescue validated. Formal notice served to State Electricity Board regarding missing diverters.',
                    'img': 'incident_photos/2026/11/Incident_001.jpg', 'cap': 'Field evidence: High-tension line span lacking bird diverters at collision site'
                },
                # 1. Critical Injured Bird: Mohol Striker fence wire entanglement (Oct 28)
                {
                    'cat': 'INJURED_BIRD', 'pri': 'CRITICAL', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=4, hours=6),
                    'bird': db_birds['GIB-NNJ-012'], 'zone': db_zones['ZONE-NNJ-CORE'],
                    'lat': 17.8215, 'lng': 75.8488,
                    'desc': 'Adult male GIB-NNJ-012 (Mohol Striker) found entangled in loose agricultural perimeter fence wire near southeastern boundary. Feather loss on left wing primary pinions and minor skin laceration. Successfully cut free and transferred to sanctuary hospital.',
                    'vby': fo_user, 'vat': now - timedelta(days=4, hours=5),
                    'notes': 'Incident verified. Defective barbed wire fence dismantled and replaced with smooth wildlife-safe fencing.',
                    'img': 'incident_photos/2026/11/Medical_002.jpg', 'cap': 'Field evidence: Medical triage and wing examination upon rescue'
                },
                # 2. Poaching threat: Wire snares in buffer (Oct 30)
                {
                    'cat': 'POACHING_THREAT', 'pri': 'HIGH', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=2, hours=14),
                    'bird': None, 'zone': db_zones['ZONE-NNJ-BUFF'],
                    'lat': 17.8420, 'lng': 75.8240,
                    'desc': 'Discovery of three unauthorized wire snare traps placed along natural game trails in western grassland buffer. Traps confiscated immediately. Motorcycle tyre tracks detected leading toward nearby state highway. No wildlife casualties detected.',
                    'vby': fo_user, 'vat': now - timedelta(days=2, hours=11),
                    'notes': 'Verified and logged under Wildlife Protection Act, 1972 Schedule I violations. Increased nocturnal patrol frequency ordered.',
                    'img': 'incident_photos/2026/11/Incident_003.jpg', 'cap': 'Field evidence: Illegal wire snares confiscated during morning buffer sweep'
                },
                # 3. Feral dog pack threat (Today, Nov 1) - PENDING
                {
                    'cat': 'OTHER', 'pri': 'HIGH', 'stat': 'PENDING',
                    'rep': rng_patil, 'dt': now - timedelta(hours=4),
                    'bird': db_birds['GIB-NNJ-002'], 'zone': db_zones['ZONE-NNJ-CORE'],
                    'lat': 17.8270, 'lng': 75.8430,
                    'desc': 'A pack of 5 free-ranging feral dogs entered northern grassland perimeter through a culvert gap, attempting to approach female bustard GIB-NNJ-002. Patrol team successfully chased dogs out using sonic deterrents. Immediate reinforcement of culvert fencing required.',
                    'vby': None, 'vat': None, 'notes': '',
                    'img': 'incident_photos/2026/11/Incident_002.jpeg', 'cap': 'Field evidence: Feral dog pack footprint tracks along northern enclosure canal'
                },
                # 4. Night agricultural encroachment (Today, Nov 1) - PENDING
                {
                    'cat': 'SUSPICIOUS_ACTIVITY', 'pri': 'MEDIUM', 'stat': 'PENDING',
                    'rep': rng_patil, 'dt': now - timedelta(hours=9),
                    'bird': None, 'zone': db_zones['ZONE-NNJ-BUFF'],
                    'lat': 17.8150, 'lng': 75.8260,
                    'desc': 'Tractor with heavy disc plough observed tilling unnotified grassland patch within 200m of buffer boundary. Operator instructed to halt immediately. Land revenue records under review to verify survey demarcation.',
                    'vby': None, 'vat': None, 'notes': '',
                    'img': 'incident_photos/2026/11/Incident_004.jpeg', 'cap': 'Field evidence: Heavy machinery encroaching on designated eco-sensitive boundary'
                },
                # 5. Power line diverter defect in Corridor (Oct 31) - PENDING
                {
                    'cat': 'POWERLINE_COLLISION', 'pri': 'HIGH', 'stat': 'PENDING',
                    'rep': rng_patil, 'dt': now - timedelta(hours=16),
                    'bird': None, 'zone': db_zones['ZONE-KRM-CORR'],
                    'lat': 17.8680, 'lng': 75.8310,
                    'desc': 'Routine inspection identified that 12 spiral bird flight diverters on Tower 42–43 have detached following heavy gusting winds. Transmission line is directly across seasonal flyway. Urgent re-installation requested.',
                    'vby': None, 'vat': None, 'notes': '',
                    'img': 'incident_photos/2026/11/Incident_006.png', 'cap': 'Field evidence: Detached and missing bird flight diverters on 66kV transmission span'
                },
                # 6. Sighting: Maldhok King courtship display (Oct 31)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=1, hours=7),
                    'bird': db_birds['GIB-NNJ-001'], 'zone': db_zones['ZONE-NNJ-CORE'],
                    'lat': 17.8248, 'lng': 75.8475,
                    'desc': 'Full courtship display observed at primary lek site between 06:45 and 08:15 AM. Male inflated gular pouch, puffed white feathers, and produced deep booming calls audible over 800m. Two females observed observing from 150m distance.',
                    'vby': fo_user, 'vat': now - timedelta(days=1, hours=5),
                    'notes': 'Phenology record confirmed and archived into Annual Breeding Behavior Database.',
                    'img': 'incident_photos/2026/11/GIB_001.jpg', 'cap': 'Field evidence: Maldhok King displaying full nuptial plumage on display mound'
                },
                # 7. Sighting: Chick foraging with mother (Oct 30)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=2, hours=3),
                    'bird': db_birds['GIB-NNJ-015'], 'zone': db_zones['ZONE-NNJ-CORE'],
                    'lat': 17.8290, 'lng': 75.8420,
                    'desc': 'Juvenile chick GIB-NNJ-015 observed actively foraging alongside adult female GIB-NNJ-002 in dense Aristida grassland. Chick demonstrated active insect feeding (Orthoptera prey items). Vigilance posture normal.',
                    'vby': fo_user, 'vat': now - timedelta(days=2, hours=2),
                    'notes': 'Chick development milestones verified by WII research team.',
                    'img': 'incident_photos/2026/11/GIB_015.jpeg', 'cap': 'Field evidence: 2026 juvenile chick active foraging observation'
                },
                # 8. Sighting: Telemetry female foraging (Oct 29)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': res_joshi, 'dt': now - timedelta(days=3, hours=4),
                    'bird': db_birds['GIB-NNJ-003'], 'zone': db_zones['ZONE-NNJ-BUFF'],
                    'lat': 17.8340, 'lng': 75.8380,
                    'desc': 'Visual confirmation of satellite-tagged female Sahyadri Jewel. Transmitter solar panel clean and firmly seated. Bird feeding on Ziziphus berries and ground insects in open scrubland mosaic.',
                    'vby': fo_user, 'vat': now - timedelta(days=3, hours=2),
                    'notes': 'Visual validation corroborates GPS telemetry coordinate stream perfectly.',
                    'img': 'incident_photos/2026/11/GIB_003.jpeg', 'cap': 'Field evidence: Sahyadri Jewel observed during satellite coordinate ground-truthing'
                },
                # 9. Sighting: Adult male group (Oct 27)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=5, hours=8),
                    'bird': db_birds['GIB-NNJ-004'], 'zone': db_zones['ZONE-NNJ-BUFF'],
                    'lat': 17.8410, 'lng': 75.8350,
                    'desc': 'Adult male Marathwada Falcon observed in loose association with sub-adult male GIB-NNJ-010. Preening behavior recorded under shaded Acacia nilotica canopy during midday heat.',
                    'vby': fo_user, 'vat': now - timedelta(days=5, hours=6),
                    'notes': 'Normal non-breeding seasonal male bachelor association confirmed.',
                    'img': 'incident_photos/2026/11/GIB_004.jpeg', 'cap': 'Field evidence: Adult male roosting in western buffer shade canopy'
                },
                # 10. Sighting: Old male Bhimashankar (Oct 26)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=6, hours=10),
                    'bird': db_birds['GIB-NNJ-008'], 'zone': db_zones['ZONE-NNJ-CORE'],
                    'lat': 17.8180, 'lng': 75.8510,
                    'desc': 'Senior breeding male Bhimashankar sighted foraging near southern observation mound. Feather condition pristine; normal gait and flight capability demonstrated.',
                    'vby': fo_user, 'vat': now - timedelta(days=6, hours=8),
                    'notes': 'Health index verified as optimal for veteran bird.',
                    'img': 'incident_photos/2026/11/GIB_008.jpeg', 'cap': 'Field evidence: Bhimashankar foraging in southern core grasslands'
                },
                # 11. Sighting: Deccan Empress in southern grassland (Oct 25)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=7, hours=2),
                    'bird': db_birds['GIB-NNJ-009'], 'zone': db_zones['ZONE-NNJ-CORE'],
                    'lat': 17.8220, 'lng': 75.8530,
                    'desc': 'Solitary female Deccan Empress sighted during late afternoon patrol. Feeding calmly on grass seedheads; took short 400m low flight upon tractor noise in distant distance.',
                    'vby': fo_user, 'vat': now - timedelta(days=7, hours=1),
                    'notes': 'Flight profile and landing evaluated as fully intact.',
                    'img': 'incident_photos/2026/11/GIB_009.jpeg', 'cap': 'Field evidence: Deccan Empress ground observation'
                },
                # 12. Resolved: Localized Grassfire Hazard (Oct 23)
                {
                    'cat': 'OTHER', 'pri': 'HIGH', 'stat': 'RESOLVED',
                    'rep': rng_patil, 'dt': now - timedelta(days=9, hours=5),
                    'bird': None, 'zone': db_zones['ZONE-NNJ-BUFF'],
                    'lat': 17.8480, 'lng': 75.8390,
                    'desc': 'Dry-season agricultural stubble burning on adjacent private farmland generated drifting smoke and sparks near buffer grassland fireline. Quick deployment of sanctuary fire-beaters extinguished perimeter flames within 35 minutes.',
                    'vby': fo_user, 'vat': now - timedelta(days=9, hours=4),
                    'notes': 'RESOLVED: Fire extinguished completely. Fireline cleared to 8-meter width. Farmer counselled on zero-burn protocol.',
                    'img': 'incident_photos/2026/11/Incident_005.jpeg', 'cap': 'Field evidence: Firebreak perimeter inspection following stubble fire containment'
                },
                # 13. Rejected False Alarm (Oct 22)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'REJECTED',
                    'rep': rng_patil, 'dt': now - timedelta(days=10, hours=7),
                    'bird': None, 'zone': db_zones['ZONE-NNJ-TOUR'],
                    'lat': 17.7950, 'lng': 75.8450,
                    'desc': 'Public visitor reported sighting an alleged bustard chick walking in high grass near visitor watchtower #2.',
                    'vby': fo_user, 'vat': now - timedelta(days=10, hours=5),
                    'notes': 'REJECTED: On-site verification confirmed bird was an adult Grey Francolin (Francolinus pondicerianus), not a Great Indian Bustard. Sighting rejected as misidentification.',
                    'img': 'incident_photos/2026/11/Incident_002.jpeg', 'cap': 'Verification evidence: Ground inspection of reported location'
                },
                # 14. Emergency Rescue: Stranded bird near irrigation ditch (Oct 20)
                {
                    'cat': 'INJURED_BIRD', 'pri': 'HIGH', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=12, hours=4),
                    'bird': db_birds['GIB-NNJ-003'], 'zone': db_zones['ZONE-NNJ-BUFF'],
                    'lat': 17.8360, 'lng': 75.8370,
                    'desc': 'Female bustard Sahyadri Jewel found temporarily trapped in muddy irrigation ditch adjacent to sugarcane field. Bird exhausted, unable to gain footing on wet clay banks. Gently extricated by field patrol team and brought for hydration check.',
                    'vby': fo_user, 'vat': now - timedelta(days=12, hours=3),
                    'notes': 'Verified. Hydration therapy administered at clinic; bird returned to buffer scrubland upon clearing.',
                    'img': 'incident_photos/2026/11/Medical_003.jpg', 'cap': 'Field evidence: Avian medical check and hydration therapy'
                },
                # 15. Sighting: Sub-adult Nannaj Pride (Oct 19)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=13, hours=5),
                    'bird': db_birds['GIB-NNJ-005'], 'zone': db_zones['ZONE-NNJ-CORE'],
                    'lat': 17.8260, 'lng': 75.8450,
                    'desc': 'Sub-adult male Nannaj Pride recorded practicing wing-flutter displays in open grassland clearing. Excellent vigor and feather symmetry observed.',
                    'vby': fo_user, 'vat': now - timedelta(days=13, hours=4),
                    'notes': 'Behavioral display noted in young male developmental tracker.',
                    'img': 'incident_photos/2026/11/GIB_005.jpg', 'cap': 'Field evidence: Sub-adult male behavioral documentation'
                },
                # 16. Sighting: Karmala Corridor survey (Oct 18)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'MEDIUM', 'stat': 'VERIFIED',
                    'rep': res_joshi, 'dt': now - timedelta(days=14, hours=6),
                    'bird': db_birds['GIB-NNJ-006'], 'zone': db_zones['ZONE-KRM-CORR'],
                    'lat': 17.8620, 'lng': 75.8360,
                    'desc': 'Adult male GIB-NNJ-006 confirmed crossing agricultural boundary road during dusk flight. Successfully cleared overhead 11kV rural feeder line by over 15 meters.',
                    'vby': fo_user, 'vat': now - timedelta(days=14, hours=4),
                    'notes': 'Flight trajectory mapped into Corridor Safety GIS layer.',
                    'img': 'incident_photos/2026/11/GIB_006.jpeg', 'cap': 'Field evidence: Northern corridor flight path visual verification'
                },
                # 17. Powerline Hazard Inspection: Gangewadi Corridor (Oct 17)
                {
                    'cat': 'POWERLINE_COLLISION', 'pri': 'HIGH', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=15, hours=3),
                    'bird': None, 'zone': db_zones['ZONE-KRM-CORR'],
                    'lat': 17.8710, 'lng': 75.8320,
                    'desc': 'Detailed survey of 132kV transmission corridor crossing Gangewadi agricultural steppe. Identified 4 spans where line sag exceeds seasonal safety clearance thresholds during high midday temperatures.',
                    'vby': fo_user, 'vat': now - timedelta(days=15, hours=2),
                    'notes': 'MSEDCL Chief Engineer notified in writing. High-visibility bird flight diverters requested.',
                    'img': 'incident_photos/2026/11/Incident_001.jpg', 'cap': 'Field evidence: Transmission line sag evaluation along dispersal corridor'
                },
                # 18. Sighting: Savitri in core nesting scrape (Oct 16)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=16, hours=8),
                    'bird': db_birds['GIB-NNJ-013'], 'zone': db_zones['ZONE-NNJ-CORE'],
                    'lat': 17.8310, 'lng': 75.8460,
                    'desc': 'Adult female Savitri sighted resting near southern rocky outcrop. Dust-bathing behavior recorded for 25 minutes. No external parasites or plumage distress detected.',
                    'vby': fo_user, 'vat': now - timedelta(days=16, hours=6),
                    'notes': 'Normal plumage maintenance behavior documented.',
                    'img': 'incident_photos/2026/11/GIB_013.jpg', 'cap': 'Field evidence: Savitri dust-bathing documentation'
                },
                # 19. Sighting: Tourism Zone Watchtower Observation (Oct 15)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=17, hours=4),
                    'bird': db_birds['GIB-NNJ-004'], 'zone': db_zones['ZONE-NNJ-TOUR'],
                    'lat': 17.8020, 'lng': 75.8460,
                    'desc': 'Adult male Marathwada Falcon observed from Watchtower #1 at distance of 320m. Bird foraging calmly in open grassland mosaic, unperturbed by visitor viewing hide.',
                    'vby': fo_user, 'vat': now - timedelta(days=17, hours=2),
                    'notes': 'Regulated eco-tourism distance compliance confirmed.',
                    'img': 'incident_photos/2026/11/GIB_004.jpeg', 'cap': 'Field evidence: Long-distance telephoto observation from Watchtower 1'
                },
                # 20. Medical Rescue Alert: Heat exhaustion in buffer (Oct 14)
                {
                    'cat': 'SICK_BIRD', 'pri': 'MEDIUM', 'stat': 'RESOLVED',
                    'rep': rng_patil, 'dt': now - timedelta(days=18, hours=5),
                    'bird': db_birds['GIB-NNJ-005'], 'zone': db_zones['ZONE-NNJ-BUFF'],
                    'lat': 17.8280, 'lng': 75.8340,
                    'desc': 'Young sub-adult Nannaj Pride exhibited open-mouth panting and lethargy during midday heatwave. Safely captured using soft net and administered emergency subcutaneous electrolytes.',
                    'vby': fo_user, 'vat': now - timedelta(days=18, hours=3),
                    'notes': 'RESOLVED: Bird fully hydrated and recovered in pre-release enclosure; fitness certified.',
                    'img': 'incident_photos/2026/11/Medical_004.jpg', 'cap': 'Field evidence: Pre-release conditioning and hydration recovery'
                },
                # 21. Poaching / Intrusion Sweep: Night Patrol (Oct 13)
                {
                    'cat': 'POACHING_THREAT', 'pri': 'HIGH', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=19, hours=11),
                    'bird': None, 'zone': db_zones['ZONE-NNJ-CORE'],
                    'lat': 17.8170, 'lng': 75.8490,
                    'desc': 'Nocturnal anti-poaching patrol intercepted two trespassers attempting illegal night hare hunting with high-intensity battery searchlights. Trespassers fled leaving behind handheld searchlights. Footprints documented.',
                    'vby': fo_user, 'vat': now - timedelta(days=19, hours=9),
                    'notes': 'Searchlights confiscated as evidence. Range Forest Officer filed formal First Information Report (FIR).',
                    'img': 'incident_photos/2026/11/Incident_003.jpg', 'cap': 'Field evidence: Confiscated nocturnal spotlight equipment'
                },
                # 22. Sighting: Pair foraging in Gangewadi Corridor (Oct 12)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': res_joshi, 'dt': now - timedelta(days=20, hours=7),
                    'bird': db_birds['GIB-NNJ-006'], 'zone': db_zones['ZONE-KRM-CORR'],
                    'lat': 17.8590, 'lng': 75.8380,
                    'desc': 'Adult male Karmala Scout sighted feeding in mosaic pulse crop stubble. Feeding rate: 14 pecks/minute on ground crickets and grasshopper nymphs.',
                    'vby': fo_user, 'vat': now - timedelta(days=20, hours=5),
                    'notes': 'Foraging rate logged in seasonal agro-ecosystem diet study.',
                    'img': 'incident_photos/2026/11/GIB_006.jpeg', 'cap': 'Field evidence: Agro-pastoral pulse stubble foraging observation'
                },
                # 23. Suspicious Night Grazing Intrusion (Oct 11)
                {
                    'cat': 'SUSPICIOUS_ACTIVITY', 'pri': 'MEDIUM', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=21, hours=8),
                    'bird': None, 'zone': db_zones['ZONE-NNJ-BUFF'],
                    'lat': 17.8390, 'lng': 75.8270,
                    'desc': 'Herd of 40 sheep driven across western buffer fence by local pastoralists after sunset. Herd escorted out peacefully; warning issued to herder regarding ground-nest disturbance risks.',
                    'vby': fo_user, 'vat': now - timedelta(days=21, hours=6),
                    'notes': 'Grazing restriction notice served to village sarpanch. Fence integrity restored.',
                    'img': 'incident_photos/2026/11/Incident_004.jpeg', 'cap': 'Field evidence: Livestock track survey along buffer enclosure line'
                },
                # 24. Sighting: Solapur Queen morning patrol (Oct 10)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=22, hours=3),
                    'bird': db_birds['GIB-NNJ-002'], 'zone': db_zones['ZONE-NNJ-CORE'],
                    'lat': 17.8280, 'lng': 75.8450,
                    'desc': 'Solapur Queen recorded in early morning light (~06:30 AM). Active scanning behavior from gentle ridge slope. Calm temperament, vigorous stepping.',
                    'vby': fo_user, 'vat': now - timedelta(days=22, hours=2),
                    'notes': 'Healthy vigilance profile confirmed.',
                    'img': 'incident_photos/2026/11/GIB_002.jpeg', 'cap': 'Field evidence: Solapur Queen early morning vigilance post'
                },
                # 25. Minor Injured Bird: Raptor scratch (Oct 9) - RESOLVED
                {
                    'cat': 'INJURED_BIRD', 'pri': 'LOW', 'stat': 'RESOLVED',
                    'rep': rng_patil, 'dt': now - timedelta(days=23, hours=4),
                    'bird': db_birds['GIB-NNJ-010'], 'zone': db_zones['ZONE-NNJ-BUFF'],
                    'lat': 17.8420, 'lng': 75.8360,
                    'desc': 'Young sub-adult Grassland Prince observed with superficial talon scratch on back from brief encounter with Tawny Eagle. Antiseptic dressing applied on field capture; released immediately.',
                    'vby': fo_user, 'vat': now - timedelta(days=23, hours=3),
                    'notes': 'RESOLVED: Minor scratch treated with topical Betadine. Bird resumed normal flight immediately.',
                    'img': 'incident_photos/2026/11/Medical_005.jpg', 'cap': 'Field evidence: Minor superficial wound inspection'
                },
                # 26. Sighting: Dharashiv Wanderer pre-dispersal (Oct 8)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': res_joshi, 'dt': now - timedelta(days=24, hours=6),
                    'bird': db_birds['GIB-NNJ-014'], 'zone': db_zones['ZONE-KRM-CORR'],
                    'lat': 17.8680, 'lng': 75.8330,
                    'desc': 'Adult male Dharashiv Wanderer sighted in northern grassland corridor prior to signal loss. Observed foraging in mixed sesame and sorghum border plots.',
                    'vby': fo_user, 'vat': now - timedelta(days=24, hours=5),
                    'notes': 'Last confirmed high-confidence visual sighting prior to active missing search.',
                    'img': 'incident_photos/2026/11/GIB_014.jpg', 'cap': 'Field evidence: Pre-dispersal photographic documentation'
                },
                # 27. Powerline Diverter Monitoring in Western Buffer (Oct 7)
                {
                    'cat': 'POWERLINE_COLLISION', 'pri': 'MEDIUM', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=25, hours=4),
                    'bird': None, 'zone': db_zones['ZONE-NNJ-BUFF'],
                    'lat': 17.8440, 'lng': 75.8290,
                    'desc': 'Inspected 2.4 km of 11kV distribution line near sugar mill road. Confirmed that 88 dynamic LED solar flappers installed in August 2026 are 100% operational.',
                    'vby': fo_user, 'vat': now - timedelta(days=25, hours=3),
                    'notes': 'Diverter luminescence audit passed with full operational clearance.',
                    'img': 'incident_photos/2026/11/Incident_001.jpg', 'cap': 'Field evidence: Operational solar LED bird flight diverter audit'
                },
                # 28. Sighting: Maldhok King in central core (Oct 6)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=26, hours=7),
                    'bird': db_birds['GIB-NNJ-001'], 'zone': db_zones['ZONE-NNJ-CORE'],
                    'lat': 17.8250, 'lng': 75.8470,
                    'desc': 'Maldhok King sighted resting under shadow of Balanites aegyptiaca tree during warm afternoon. Normal posture, regular blinking, excellent plumage luster.',
                    'vby': fo_user, 'vat': now - timedelta(days=26, hours=5),
                    'notes': 'Roosting site microclimate parameters recorded.',
                    'img': 'incident_photos/2026/11/GIB_001.jpg', 'cap': 'Field evidence: Midday roosting observation'
                },
                # 29. Sighting: Sub-adult flight practice (Oct 5)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=27, hours=3),
                    'bird': db_birds['GIB-NNJ-010'], 'zone': db_zones['ZONE-NNJ-BUFF'],
                    'lat': 17.8380, 'lng': 75.8390,
                    'desc': 'Sub-adult male Grassland Prince performed sustained 1.2km low flight across buffer grassland, clearing field bunds easily. Good wing stroke cadence.',
                    'vby': fo_user, 'vat': now - timedelta(days=27, hours=2),
                    'notes': 'Flight duration and distance logged in juvenile performance archive.',
                    'img': 'incident_photos/2026/11/GIB_0010.jpeg', 'cap': 'Field evidence: Flight performance visual confirmation'
                },
                # 30. Sighting: Sina Runner in southern riverine patch (Oct 4)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=28, hours=8),
                    'bird': db_birds['GIB-NNJ-007'], 'zone': db_zones['ZONE-NNJ-BUFF'],
                    'lat': 17.8120, 'lng': 75.8410,
                    'desc': 'Female Sina Runner observed feeding on flowering leguminous herbs along southern dry stream bed. Sighted in company of two female Chinkara gazelles.',
                    'vby': fo_user, 'vat': now - timedelta(days=28, hours=6),
                    'notes': 'Sympatric association with wild ungulates documented.',
                    'img': 'incident_photos/2026/11/GIB_007.jpeg', 'cap': 'Field evidence: Interspecific foraging observation with Chinkara'
                },
                # 31. Sighting: Old Bhimashankar territory scan (Oct 3)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=29, hours=4),
                    'bird': db_birds['GIB-NNJ-008'], 'zone': db_zones['ZONE-NNJ-CORE'],
                    'lat': 17.8190, 'lng': 75.8500,
                    'desc': 'Bhimashankar observed standing on elevated rocky outcrop scanning southern boundary. Vocalization recorded at 07:10 AM.',
                    'vby': fo_user, 'vat': now - timedelta(days=29, hours=2),
                    'notes': 'Acoustic vocalization file archived.',
                    'img': 'incident_photos/2026/11/GIB_008.jpeg', 'cap': 'Field evidence: Territory scanning posture from southern knoll'
                },
                # 32. Additional Sighting: Deccan Empress (Nov 1)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(hours=2),
                    'bird': db_birds['GIB-NNJ-009'], 'zone': db_zones['ZONE-NNJ-CORE'],
                    'lat': 17.8235, 'lng': 75.8515,
                    'desc': 'Midday observation of Deccan Empress resting peacefully in shaded Sehima nervosum clump. Normal alertness.',
                    'vby': fo_user, 'vat': now - timedelta(hours=1),
                    'notes': 'Current date verified observation.',
                    'img': 'incident_photos/2026/11/GIB_009.jpeg', 'cap': 'Field evidence: Current date core observation'
                },
                # 33. Additional Sighting: Maldhok King display (Oct 21)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=11, hours=7),
                    'bird': db_birds['GIB-NNJ-001'], 'zone': db_zones['ZONE-NNJ-CORE'],
                    'lat': 17.8255, 'lng': 75.8472,
                    'desc': 'Morning territorial lek display by Maldhok King. White plumage visible across 1 km.',
                    'vby': fo_user, 'vat': now - timedelta(days=11, hours=5),
                    'notes': 'Lek fidelity confirmed.',
                    'img': 'incident_photos/2026/11/GIB_001.jpg', 'cap': 'Field evidence: Courtship plumage observation'
                },
                # 34. Additional Sighting: Sahyadri Jewel in western buffer (Oct 24)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': res_joshi, 'dt': now - timedelta(days=8, hours=6),
                    'bird': db_birds['GIB-NNJ-003'], 'zone': db_zones['ZONE-NNJ-BUFF'],
                    'lat': 17.8320, 'lng': 75.8365,
                    'desc': 'GPS ground check: Sahyadri Jewel foraging on grass seeds and beetles in open buffer strip.',
                    'vby': fo_user, 'vat': now - timedelta(days=8, hours=4),
                    'notes': 'Telemetry fix corroborated.',
                    'img': 'incident_photos/2026/11/GIB_003.jpeg', 'cap': 'Field evidence: Western buffer foraging check'
                },
                # 35. Additional Sighting: Chick foraging (Oct 17)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=15, hours=9),
                    'bird': db_birds['GIB-NNJ-015'], 'zone': db_zones['ZONE-NNJ-CORE'],
                    'lat': 17.8295, 'lng': 75.8415,
                    'desc': 'Juvenile chick GIB-NNJ-015 running actively to capture grasshoppers. High vitality.',
                    'vby': fo_user, 'vat': now - timedelta(days=15, hours=7),
                    'notes': 'Growth monitoring milestone confirmed.',
                    'img': 'incident_photos/2026/11/GIB_015.jpeg', 'cap': 'Field evidence: Juvenile insect foraging observation'
                },
                # 36. Additional Sighting: Marathwada Falcon in Tourism Zone (Oct 29)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=3, hours=9),
                    'bird': db_birds['GIB-NNJ-004'], 'zone': db_zones['ZONE-NNJ-TOUR'],
                    'lat': 17.8010, 'lng': 75.8480,
                    'desc': 'Observed from interpretation path during evening patrol. Male walking along ridge line.',
                    'vby': fo_user, 'vat': now - timedelta(days=3, hours=7),
                    'notes': 'Eco-tourism perimeter monitoring verified.',
                    'img': 'incident_photos/2026/11/GIB_004.jpeg', 'cap': 'Field evidence: Eco-tourism ridge line observation'
                },
                # 37. Additional Sighting: Savitri in Core Lek (Oct 28)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=4, hours=8),
                    'bird': db_birds['GIB-NNJ-013'], 'zone': db_zones['ZONE-NNJ-CORE'],
                    'lat': 17.8305, 'lng': 75.8455,
                    'desc': 'Adult female Savitri sighted resting near display ground perimeter. Healthy posture.',
                    'vby': fo_user, 'vat': now - timedelta(days=4, hours=6),
                    'notes': 'Pre-breeding survey record logged.',
                    'img': 'incident_photos/2026/11/GIB_013.jpg', 'cap': 'Field evidence: Core lek female observation'
                },
                # 38. Powerline Alert: Rural Feeder line clearance (Oct 26) - PENDING
                {
                    'cat': 'POWERLINE_COLLISION', 'pri': 'MEDIUM', 'stat': 'PENDING',
                    'rep': rng_patil, 'dt': now - timedelta(days=6, hours=4),
                    'bird': None, 'zone': db_zones['ZONE-NNJ-BUFF'],
                    'lat': 17.8380, 'lng': 75.8285,
                    'desc': 'Overhead 11kV agricultural feeder line spans low over seasonal crop drainage channel. Line height measured at 5.2m; recommendation to raise to 8.5m or install PVC diverter sleeves.',
                    'vby': None, 'vat': None, 'notes': '',
                    'img': 'incident_photos/2026/11/Incident_006.png', 'cap': 'Field evidence: Low-sagging 11kV agricultural feeder line span'
                },
                # 39. Feral Dog Intrusion Alert: Tourism perimeter (Oct 22) - PENDING
                {
                    'cat': 'OTHER', 'pri': 'MEDIUM', 'stat': 'PENDING',
                    'rep': rng_patil, 'dt': now - timedelta(days=10, hours=2),
                    'bird': None, 'zone': db_zones['ZONE-NNJ-TOUR'],
                    'lat': 17.7980, 'lng': 75.8420,
                    'desc': 'Three stray dogs observed following tourist vehicle tracks near interpretation centre. Chased out of sanctuary boundary by ranger staff.',
                    'vby': None, 'vat': None, 'notes': '',
                    'img': 'incident_photos/2026/11/Incident_002.jpeg', 'cap': 'Field evidence: Stray dog tracks near tourism gate'
                },
                # 40. Sighting: Karmala Scout northern foraging (Nov 1)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': res_joshi, 'dt': now - timedelta(hours=6),
                    'bird': db_birds['GIB-NNJ-006'], 'zone': db_zones['ZONE-KRM-CORR'],
                    'lat': 17.8640, 'lng': 75.8350,
                    'desc': 'Current date observation: adult male GIB-NNJ-006 foraging peacefully in open steppe grassland.',
                    'vby': fo_user, 'vat': now - timedelta(hours=4),
                    'notes': 'Verified current date record.',
                    'img': 'incident_photos/2026/11/GIB_006.jpeg', 'cap': 'Field evidence: Current date northern corridor observation'
                },
                # 41. Sighting: Sub-adult Pride and Prince association (Oct 31)
                {
                    'cat': 'BIRD_SIGHTING', 'pri': 'LOW', 'stat': 'VERIFIED',
                    'rep': rng_patil, 'dt': now - timedelta(days=1, hours=10),
                    'bird': db_birds['GIB-NNJ-005'], 'zone': db_zones['ZONE-NNJ-BUFF'],
                    'lat': 17.8350, 'lng': 75.8375,
                    'desc': 'Sub-adult males Nannaj Pride and Grassland Prince observed foraging together in western buffer scrub. Synchronous stepping and feeding observed.',
                    'vby': fo_user, 'vat': now - timedelta(days=1, hours=8),
                    'notes': 'Sub-adult association dynamics verified.',
                    'img': 'incident_photos/2026/11/GIB_005.jpg', 'cap': 'Field evidence: Sub-adult bachelor foraging pair'
                },
            ]

            db_incidents = []
            for inc_item in raw_incidents:
                inc_obj = Incident.objects.create(
                    category=inc_item['cat'],
                    priority=inc_item['pri'],
                    status=inc_item['stat'],
                    reporter=inc_item['rep'],
                    reported_at=inc_item['dt'],
                    bustard=inc_item['bird'],
                    description=inc_item['desc'],
                    verified_by=inc_item['vby'],
                    verified_at=inc_item['vat'],
                    verification_notes=inc_item['notes'],
                    data_source='FIELD_REPORT',
                    data_environment=DATA_ENV_PRODUCTION
                )
                Incident.objects.filter(id=inc_obj.id).update(reported_at=inc_item['dt'])

                IncidentLocation.objects.create(
                    incident=inc_obj,
                    latitude=inc_item['lat'],
                    longitude=inc_item['lng'],
                    accuracy_meters=4.2,
                    zone=inc_item['zone'],
                    weather_temperature_c=30.2,
                    weather_condition='Sunny / Clear',
                    weather_wind_speed_kmh=11.5
                )

                if inc_item.get('img'):
                    IncidentImage.objects.create(
                        incident=inc_obj,
                        bustard=inc_item['bird'],
                        image=inc_item['img'],
                        caption=inc_item.get('cap', 'Field observation evidence photo')
                    )

                db_incidents.append(inc_obj)

            self.stdout.write(self.style.SUCCESS(f"  [OK] {len(db_incidents)} realistic conservation incidents seeded across all categories and zones."))

            # -------------------------------------------------------------
            # STEP 6: Patrol Tasks and Field Assignments (7 Assignments)
            # -------------------------------------------------------------
            self.stdout.write("\n[6/10] Assigning 7 operational patrol tasks & evidence to field rangers...")
            PatrolAssignment.objects.all().delete()

            tasks_data = [
                {
                    'incident': db_incidents[2], # Snare trap incident
                    'ranger': rng_patil,
                    'by': fo_user,
                    'status': 'IN_PROGRESS',
                    'assigned_at': now - timedelta(days=2, hours=10),
                    'completed_at': None,
                    'instructions': 'Execute an intensive 3-kilometer sweep along western buffer fence line. Search for concealed snare wires, footprints, or fresh motorcycle entry tracks. Install 2 motion-triggered trail cameras.',
                    'notes': 'First 1.5km inspected; no further snares detected. Camera Trap #04 mounted at western culvert point.',
                    'attachment': 'assignment_evidence/2026/11/Incident_003.jpg'
                },
                {
                    'incident': db_incidents[5], # Missing diverters incident
                    'ranger': rng_patil,
                    'by': fo_user,
                    'status': 'PENDING',
                    'assigned_at': now - timedelta(hours=14),
                    'completed_at': None,
                    'instructions': 'Meet MSEDCL line engineering team at Tower 42. Supervise installation of 25 dynamic flapper bird diverters. Ensure installation conforms to Wildlife Institute of India technical guidelines.',
                    'notes': '',
                    'attachment': None
                },
                {
                    'incident': db_incidents[3], # Feral dog threat incident
                    'ranger': rng_patil,
                    'by': fo_user,
                    'status': 'ACCEPTED',
                    'assigned_at': now - timedelta(hours=3),
                    'completed_at': None,
                    'instructions': 'Patrol Core Breeding Sanctuary northern culvert. Seal gaps with heavy wire mesh. Coordinate with Solapur Municipal Corporation animal control unit for humane dog capture and relocation.',
                    'notes': 'Wire mesh supplies procured from central store. Proceeding to culvert site with 2 field staff.',
                    'attachment': None
                },
                {
                    'incident': db_incidents[4], # Tractor encroachment
                    'ranger': rng_patil,
                    'by': fo_user,
                    'status': 'PENDING',
                    'assigned_at': now - timedelta(hours=8),
                    'completed_at': None,
                    'instructions': 'Survey boundary pillars 14 to 19 along western buffer. Re-establish red boundary flags and verify GPS coordinates against sanctuary master survey map.',
                    'notes': '',
                    'attachment': None
                },
                {
                    'incident': db_incidents[0], # Powerline collision Chandrabhaga
                    'ranger': rng_patil,
                    'by': fo_user,
                    'status': 'COMPLETED',
                    'assigned_at': now - timedelta(days=1, hours=3),
                    'completed_at': now - timedelta(days=1, hours=1),
                    'instructions': 'Immediate emergency rescue operation: secure injured female GIB-NNJ-011 into padded transfer unit. Deliver directly to Dr. Sunita Kulkarni at Veterinary Recovery Hospital.',
                    'notes': 'Task completed successfully. Bird delivered safely with minimal stress handling; vitals stable at handover.',
                    'attachment': 'assignment_evidence/2026/11/Incident_001.jpg'
                },
                {
                    'incident': db_incidents[12], # Stubble burning hazard
                    'ranger': rng_patil,
                    'by': fo_user,
                    'status': 'COMPLETED',
                    'assigned_at': now - timedelta(days=9, hours=5),
                    'completed_at': now - timedelta(days=9, hours=3),
                    'instructions': 'Mobilize fire-fighting team and tractor scraper. Cut 8-meter firebreak along buffer perimeter. Document landowner details for administrative follow-up.',
                    'notes': 'Firebreak completed. All hot embers extinguished with portable knapsack water sprayers.',
                    'attachment': 'assignment_evidence/2026/11/Incident_005.jpeg'
                },
                {
                    'incident': db_incidents[17], # Corridor powerline inspection
                    'ranger': rng_patil,
                    'by': fo_user,
                    'status': 'IN_PROGRESS',
                    'assigned_at': now - timedelta(days=15, hours=2),
                    'completed_at': None,
                    'instructions': 'Ground patrol of Towers 38 through 46 in Gangewadi corridor. Log GPS points of all bird flight diverters and document any missing units.',
                    'notes': 'Survey completed for Towers 38–41; Tower 42–43 diverter detachment logged as separate incident report.',
                    'attachment': 'assignment_evidence/2026/11/Incident_006.png'
                },
            ]

            for t_item in tasks_data:
                assignment = PatrolAssignment.objects.create(
                    incident=t_item['incident'],
                    assigned_ranger=t_item['ranger'],
                    assigned_by=t_item['by'],
                    status=t_item['status'],
                    assigned_at=t_item['assigned_at'],
                    completed_at=t_item['completed_at'],
                    instructions=t_item['instructions'],
                    ranger_notes=t_item['notes']
                )
                PatrolAssignment.objects.filter(id=assignment.id).update(assigned_at=t_item['assigned_at'])

                if t_item.get('attachment'):
                    AssignmentAttachment.objects.create(
                        assignment=assignment,
                        file=t_item['attachment']
                    )

            self.stdout.write(self.style.SUCCESS(f"  [OK] 7 patrol assignments and evidence attachments seeded."))

            # -------------------------------------------------------------
            # STEP 7: 8 Medical Cases Across All 5 Statuses & Stages
            # -------------------------------------------------------------
            self.stdout.write("\n[7/10] Establishing 8 authentic Medical Team rescue cases & treatments...")
            MedicalCase.objects.all().delete()
            MedicalTreatment.objects.all().delete()
            MedicalEquipment.objects.all().delete()

            vet_user = seeded_users[ROLE_MEDICAL_TEAM]

            med_cases_data = [
                # 1. Under Treatment in ICU: Chandrabhaga (GIB-NNJ-011)
                {
                    'incident': db_incidents[0],
                    'bustard': db_birds['GIB-NNJ-011'],
                    'condition_summary': 'Acute right wing contusion and primary feather shearing from powerline strike',
                    'symptoms': 'Drooping right wing, inability to achieve lift, localized muscle edema, rapid respiration (48 bpm)',
                    'diagnosis': 'Closed blunt-force contusion of right pectoralis major and minor muscles; primary remiges 3-5 bent; no bone fracture on digital radiography.',
                    'rehabilitation_stage': 'ICU',
                    'status': 'UNDER_TREATMENT',
                    'priority': 'HIGH',
                    'created_by': fo_user,
                    'created_at': now - timedelta(days=1, hours=2),
                    'updated_at': now - timedelta(hours=2),
                    'treatments': [
                        {
                            'desc': 'Wound cleansing, digital radiographic survey of wing and clavicle, figure-of-eight padded wing immobilization splint.',
                            'meds': 'Meloxicam 0.2mg/kg IM, Enrofloxacin 10mg/kg SC, Ringer Lactate 40ml SC',
                            'dosage': 'Analgesic twice daily for 5 days; antibiotic once daily for 7 days; splint change scheduled after 72 hours.',
                            'time': now - timedelta(days=1, hours=1)
                        },
                        {
                            'desc': 'Morning clinical re-evaluation: swelling reduced by 40%, bird accepting hand-fed live crickets and calcium mealworms. Normal body temperature 41.2°C.',
                            'meds': 'Meloxicam 0.2mg/kg oral in food, Vitamin B-Complex 0.5ml oral',
                            'dosage': 'Maintain quiet darkened ICU enclosure; minimize staff disturbance.',
                            'time': now - timedelta(hours=3)
                        }
                    ]
                },
                # 2. Rehabilitation Enclosure: Mohol Striker (GIB-NNJ-012)
                {
                    'incident': db_incidents[1],
                    'bustard': db_birds['GIB-NNJ-012'],
                    'condition_summary': 'Post-trauma rehabilitation and muscle conditioning following wire fence entanglement',
                    'symptoms': 'Minor left wing stiffness during flap tests, resolved skin laceration on left tarsus, vigorous appetite.',
                    'diagnosis': 'Superficial soft tissue laceration fully healed; resolving pectoral stiffness responding well to flight conditioning.',
                    'rehabilitation_stage': 'RECOVERY_ENCLOSURE',
                    'status': 'REHABILITATION',
                    'priority': 'MEDIUM',
                    'created_by': fo_user,
                    'created_at': now - timedelta(days=4, hours=5),
                    'updated_at': now - timedelta(hours=18),
                    'treatments': [
                        {
                            'desc': 'Surgical dressing removal, antiseptic Betadine wash, transfer from ICU to 30-meter outdoor pre-release flight enclosure.',
                            'meds': 'Topical Zinc Oxide ointment, Multivitamin oral solution in drinking water',
                            'dosage': 'Fresh water fortified with electrolytes changed twice daily.',
                            'time': now - timedelta(days=2)
                        }
                    ]
                },
                # 3. Active Emergency / Triage: Juvenile stranded in ditch (Oct 20)
                {
                    'incident': db_incidents[14],
                    'bustard': db_birds['GIB-NNJ-003'],
                    'condition_summary': 'Emergency field triage: acute physical exhaustion from muddy canal entanglement',
                    'symptoms': 'Hypothermia, clay caking plumage, mild dehydration, normal heartbeat, alert eyes.',
                    'diagnosis': 'Acute physical exhaustion without skeletal fractures; successfully stabilized with warmed fluids.',
                    'rehabilitation_stage': 'ICU',
                    'status': 'ACTIVE',
                    'priority': 'HIGH',
                    'created_by': fo_user,
                    'created_at': now - timedelta(days=12, hours=3),
                    'updated_at': now - timedelta(days=10),
                    'treatments': [
                        {
                            'desc': 'Plumage cleaning with warm sterile saline, blow-drying in heated incubator, oral electrolyte rehydration.',
                            'meds': 'Electral oral solution 30ml, Dextrose 5% SC 20ml',
                            'dosage': 'Warm incubator setting 28°C; monitor crop transit.',
                            'time': now - timedelta(days=12, hours=2)
                        }
                    ]
                },
                # 4. Pre-Release Flight Cage / Recovered: Nannaj Pride (Oct 14)
                {
                    'incident': db_incidents[20],
                    'bustard': db_birds['GIB-NNJ-005'],
                    'condition_summary': 'Full recovery from acute summer heat dehydration; pre-release flight clearance',
                    'symptoms': 'Vigorous flight capability, alert temperament, morphometrics optimal (body weight 7.4 kg), normal plumage.',
                    'diagnosis': 'Complete physiological recovery from dehydration episode. Fit for unassisted wild release.',
                    'rehabilitation_stage': 'PRE_RELEASE',
                    'status': 'RECOVERED',
                    'priority': 'LOW',
                    'created_by': fo_user,
                    'created_at': now - timedelta(days=18),
                    'updated_at': now - timedelta(days=1),
                    'treatments': [
                        {
                            'desc': 'Final pre-release health certification protocol: complete blood count, fecal parasite float, blood lead level screen.',
                            'meds': 'None required. All hematological parameters within healthy wild baseline range.',
                            'dosage': 'Release clearance certificate signed and dispatched to Chief Conservator of Forests.',
                            'time': now - timedelta(days=1, hours=8)
                        }
                    ]
                },
                # 5. Pre-Release Recovered: Grassland Prince minor scratch (Oct 9)
                {
                    'incident': db_incidents[25],
                    'bustard': db_birds['GIB-NNJ-010'],
                    'condition_summary': 'Tarsus abrasion and superficial plumage damage from raptor encounter',
                    'symptoms': 'Superficial skin graze on right lower tarsus, excellent flight responsiveness, no lameness.',
                    'diagnosis': 'Superficial abrasion fully healed; flight and takeoff acceleration verified 100% normal.',
                    'rehabilitation_stage': 'PRE_RELEASE',
                    'status': 'RECOVERED',
                    'priority': 'LOW',
                    'created_by': fo_user,
                    'created_at': now - timedelta(days=23),
                    'updated_at': now - timedelta(days=20),
                    'treatments': [
                        {
                            'desc': 'Field antiseptic wash, topical antibiotic spray, 48-hour flight evaluation.',
                            'meds': 'Topical Oxytetracycline spray',
                            'dosage': 'Single topical application; clear for outdoor range.',
                            'time': now - timedelta(days=23, hours=2)
                        }
                    ]
                },
                # 6. Successfully Released to Wild: Sina Runner (GIB-NNJ-007)
                {
                    'incident': db_incidents[30],
                    'bustard': db_birds['GIB-NNJ-007'],
                    'condition_summary': 'Rehabilitated and released: superficial thorn puncture wound',
                    'symptoms': 'Resolved puncture wound on right foot pad, normal walking posture.',
                    'diagnosis': 'Minor pododermatitis fully resolved with antibiotic dressing and soft sand bedding.',
                    'rehabilitation_stage': 'RELEASED',
                    'status': 'CLOSED',
                    'priority': 'LOW',
                    'created_by': fo_user,
                    'created_at': now - timedelta(days=45),
                    'updated_at': now - timedelta(days=28),
                    'treatments': [
                        {
                            'desc': 'Final veterinary inspection and release into Nannaj Core Breeding Sanctuary.',
                            'meds': 'None',
                            'dosage': 'Post-release radio-tracking monitoring assigned to field rangers.',
                            'time': now - timedelta(days=28)
                        }
                    ]
                },
                # 7. Successfully Released to Wild: Marathwada Falcon heat exhaustion
                {
                    'incident': db_incidents[19],
                    'bustard': db_birds['GIB-NNJ-004'],
                    'condition_summary': 'Acute heat stress stabilization and successful wild return',
                    'symptoms': 'Transient exhaustion following prolonged high-temperature territorial patrol; quick recovery.',
                    'diagnosis': 'Thermal strain resolved within 24 hours under misting cooling protocol.',
                    'rehabilitation_stage': 'RELEASED',
                    'status': 'CLOSED',
                    'priority': 'LOW',
                    'created_by': fo_user,
                    'created_at': now - timedelta(days=17),
                    'updated_at': now - timedelta(days=15),
                    'treatments': [
                        {
                            'desc': 'Evaporative cooling, cool water oral rehydration, release at dusk.',
                            'meds': 'Electrolyte fluids 50ml oral',
                            'dosage': 'Release confirmed.',
                            'time': now - timedelta(days=16)
                        }
                    ]
                },
                # 8. Deceased Historical Case: Solapur Pioneer powerline collision
                {
                    'incident': None,
                    'bustard': hist_dead_bird,
                    'condition_summary': 'Confirmed Dead: Solapur Pioneer power line collision fatality',
                    'symptoms': 'Fatal collision trauma, severe electrical flash burns',
                    'diagnosis': 'Cardiopulmonary arrest secondary to acute electrocution and blunt-force kinetic collision.',
                    'rehabilitation_stage': 'DECEASED',
                    'status': 'CLOSED',
                    'priority': 'HIGH',
                    'created_by': fo_user,
                    'created_at': now - timedelta(days=220),
                    'updated_at': now - timedelta(days=219),
                    'treatments': [
                        {
                            'desc': 'Formal post-mortem necropsy and tissue specimen preservation for WII national archive.',
                            'meds': 'Necropsy Protocol NP-2024-GIB-01',
                            'dosage': 'Complete anatomical dissection and photography.',
                            'time': now - timedelta(days=219)
                        }
                    ]
                },
            ]

            for m_item in med_cases_data:
                med_obj = MedicalCase.objects.create(
                    incident=m_item['incident'],
                    bustard=m_item['bustard'],
                    condition_summary=m_item['condition_summary'],
                    symptoms=m_item['symptoms'],
                    diagnosis=m_item['diagnosis'],
                    rehabilitation_stage=m_item['rehabilitation_stage'],
                    status=m_item['status'],
                    priority=m_item['priority'],
                    assigned_team=vet_user,
                    created_by=m_item['created_by'],
                    created_at=m_item['created_at']
                )
                MedicalCase.objects.filter(id=med_obj.id).update(
                    created_at=m_item['created_at'],
                    updated_at=m_item['updated_at']
                )

                for tr in m_item.get('treatments', []):
                    MedicalTreatment.objects.create(
                        medical_case=med_obj,
                        administered_by=vet_user,
                        treatment_description=tr['desc'],
                        medications_given=tr['meds'],
                        dosage_notes=tr['dosage'],
                        treatment_time=tr['time']
                    )

            # Equipment Catalog
            equip_data = [
                ('Avian Carbon-Fiber Rescue & Transport Crate', 'Transport / Field Rescue', 4, 1, 'OPERATIONAL', 'Padded interior with anti-panic darkening flaps'),
                ('Avian Wing & Tarsus Splint Immobilization Kit', 'Veterinary First Aid', 8, 2, 'OPERATIONAL', 'Lightweight thermo-moldable splints with cohesive wraps'),
                ('Portable Avian Oxygen & Nebulizer Intensive Care Incubator', 'Intensive Care Unit', 2, 1, 'OPERATIONAL', 'Digital temperature and humidity controls; HEPA filtered'),
                ('Solar-Powered GPS-GSM Telemetry Harness Attachment Kit', 'Field Tracking / Research', 5, 2, 'OPERATIONAL', 'Ultra-lightweight Teflon leg-loop harness systems (28g)'),
                ('Digital Avian Precision Weighing & Morphometric Scale', 'Clinical Diagnostics', 3, 0, 'OPERATIONAL', 'Calibrated to ±1g accuracy with cushioned platform'),
                ('Portable Centrifuge & Avian Blood Chemistry Analyzer', 'Field Laboratory', 2, 0, 'OPERATIONAL', 'Complete electrolyte and hematocrit profile unit'),
            ]
            for ename, ecat, eq_avail, eq_use, estatus, enotes in equip_data:
                MedicalEquipment.objects.create(
                    name=ename,
                    category=ecat,
                    quantity_available=eq_avail,
                    quantity_in_use=eq_use,
                    status=estatus,
                    last_inspected=date(2026, 10, 15),
                    notes=enotes
                )

            self.stdout.write(self.style.SUCCESS("  [OK] 8 medical cases across all 5 statuses & stages initialized."))

            # -------------------------------------------------------------
            # STEP 8: GPS Telemetry Movement Points (115 Points Across 30 Days)
            # -------------------------------------------------------------
            self.stdout.write("\n[8/10] Seeding 115 continuous GPS telemetry movement fixes across 30 days...")
            BustardMovement.objects.all().delete()
            ConservationReport.objects.all().delete()

            movement_birds = [
                (db_birds['GIB-NNJ-001'], 17.8248, 75.8475, 'Maldhok King - Lek Center'),
                (db_birds['GIB-NNJ-002'], 17.8290, 75.8420, 'Solapur Queen - North Grasslands'),
                (db_birds['GIB-NNJ-003'], 17.8340, 75.8380, 'Sahyadri Jewel - Western Buffer'),
                (db_birds['GIB-NNJ-004'], 17.8410, 75.8350, 'Marathwada Falcon - Agro-Pastoral'),
                (db_birds['GIB-NNJ-006'], 17.8620, 75.8360, 'Karmala Scout - Dispersal Corridor'),
            ]

            movement_count = 0
            # Generate points spanning each of the past 30 days
            for bird, base_lat, base_lng, track_label in movement_birds:
                for day_idx in range(23):
                    point_time = now - timedelta(days=day_idx, hours=(day_idx % 4) * 5 + 2)
                    lat_drift = ((day_idx * 5) % 9 - 4) * 0.0015
                    lng_drift = ((day_idx * 11) % 9 - 4) * 0.0018

                    source = 'GPS_TELEMETRY' if bird.tag_id in ['GIB-NNJ-003', 'GIB-NNJ-006'] else 'FIELD_OBSERVATION'
                    conf = 'VERIFIED'

                    mov = BustardMovement.objects.create(
                        bustard=bird,
                        latitude=round(base_lat + lat_drift, 5),
                        longitude=round(base_lng + lng_drift, 5),
                        data_source=source,
                        confidence=conf,
                        notes=f"Telemetry fix: {track_label}. Foraging speed ~1.1 km/h."
                    )
                    BustardMovement.objects.filter(id=mov.id).update(recorded_at=point_time)
                    movement_count += 1

            # Conservation Reports
            ConservationReport.objects.create(
                period_start=date(2026, 10, 1),
                period_end=date(2026, 10, 31),
                generated_by=res_joshi,
                created_at=now - timedelta(days=1),
                status='FINALIZED',
                submitted_to_fo=True,
                submitted_to_admin=True,
                submitted_at_fo=now - timedelta(days=1, hours=20),
                submitted_at_admin=now - timedelta(days=1, hours=19)
            )
            ConservationReport.objects.create(
                period_start=date(2026, 7, 1),
                period_end=date(2026, 9, 30),
                generated_by=res_joshi,
                created_at=now - timedelta(days=32),
                status='FINALIZED',
                submitted_to_fo=True,
                submitted_to_admin=True,
                submitted_at_fo=now - timedelta(days=31),
                submitted_at_admin=now - timedelta(days=31)
            )
            ConservationReport.objects.create(
                period_start=date(2026, 11, 1),
                period_end=date(2026, 11, 30),
                generated_by=res_joshi,
                created_at=now,
                status='DRAFT',
                submitted_to_fo=False,
                submitted_to_admin=False
            )

            self.stdout.write(self.style.SUCCESS(f"  [OK] {movement_count} GPS movement points and 3 research reports generated."))

            # -------------------------------------------------------------
            # STEP 9: Tourism Permits & Visitor Records (7 Records)
            # -------------------------------------------------------------
            self.stdout.write("\n[9/10] Populating regulated eco-tourism permits...")
            TourismRecord.objects.all().delete()

            tour_data = [
                {
                    'visitor_name': 'Solapur University Department of Environmental Sciences',
                    'contact_phone': '+91 94220 55112',
                    'contact_email': 'dept.env@solapuruniversity.edu.in',
                    'visit_date': (now + timedelta(days=2)).date(),
                    'visitor_count': 14,
                    'zone': db_zones['ZONE-NNJ-TOUR'],
                    'area': 'Visitor Trail 1 & Nature Interpretation Centre',
                    'purpose': 'University postgraduate field ecology study & grassland habitat census demo',
                    'status': 'APPROVED',
                    'remarks': 'Accompanied by Senior Eco-Guide R. Shinde. Two electric safari buggies approved.',
                },
                {
                    'visitor_name': 'Maharashtra Wildlife Photographers Guild (Group Alpha)',
                    'contact_phone': '+91 98221 44556',
                    'contact_email': 'contact@wildlifephotographers.mh.in',
                    'visit_date': (now - timedelta(days=2)).date(),
                    'visitor_count': 4,
                    'zone': db_zones['ZONE-NNJ-TOUR'],
                    'area': 'Watchtower #1 & Fenced Observation Hide',
                    'purpose': 'Documentary photography of grassland habitat & eco-tourism trails',
                    'status': 'COMPLETED',
                    'remarks': 'Permit adhered strictly to telephoto guidelines; zero disturbance to bird flight paths.',
                },
                {
                    'visitor_name': 'Pune Birdwatching Society Expedition Team',
                    'contact_phone': '+91 98230 77889',
                    'contact_email': 'tours@punebirders.org',
                    'visit_date': (now + timedelta(days=5)).date(),
                    'visitor_count': 8,
                    'zone': db_zones['ZONE-NNJ-TOUR'],
                    'area': 'Interpretation Centre & Guided Perimeter Walk',
                    'purpose': 'Regulated birdwatching & winter grassland avian survey',
                    'status': 'APPROVED',
                    'remarks': 'Sanctuary orientation briefing mandatory at 06:15 AM before gate entry.',
                },
                {
                    'visitor_name': 'Nannaj Gram Panchayat High School Eco-Club',
                    'contact_phone': '+91 94231 66778',
                    'contact_email': 'ecoclub.nannaj@schools.gov.in',
                    'visit_date': (now + timedelta(days=8)).date(),
                    'visitor_count': 22,
                    'zone': db_zones['ZONE-NNJ-TOUR'],
                    'area': 'Nature Interpretation Centre & Auditorium',
                    'purpose': 'Student conservation awareness and Great Indian Bustard education session',
                    'status': 'APPROVED',
                    'remarks': 'Free educational entry authorized by Forest Officer Rajesh Deshmukh.',
                },
                {
                    'visitor_name': 'Bombay Natural History Society (BNHS) Grassland Survey',
                    'contact_phone': '+91 98200 99881',
                    'contact_email': 'research@bnhs.org',
                    'visit_date': (now - timedelta(days=8)).date(),
                    'visitor_count': 6,
                    'zone': db_zones['ZONE-NNJ-TOUR'],
                    'area': 'South Observation Mound Trail',
                    'purpose': 'Grassland habitat vegetation index evaluation',
                    'status': 'COMPLETED',
                    'remarks': 'Visit completed with full compliance report submitted to Range Forest Office.',
                },
                {
                    'visitor_name': 'Deccan Birders Photography Circle',
                    'contact_phone': '+91 98212 33445',
                    'contact_email': 'info@deccanbirders.com',
                    'visit_date': (now + timedelta(days=12)).date(),
                    'visitor_count': 5,
                    'zone': db_zones['ZONE-NNJ-TOUR'],
                    'area': 'Watchtower #2 Hide',
                    'purpose': 'Avian telephoto photography permit',
                    'status': 'PENDING',
                    'remarks': 'Awaiting equipment serial verification.',
                },
                {
                    'visitor_name': 'Independent Tourist Group (Unescorted)',
                    'contact_phone': '+91 98900 11223',
                    'contact_email': 'tourist@gmail.com',
                    'visit_date': (now - timedelta(days=14)).date(),
                    'visitor_count': 10,
                    'zone': db_zones['ZONE-NNJ-CORE'],
                    'area': 'Core Lek Perimeter',
                    'purpose': 'General tourism',
                    'status': 'CANCELLED',
                    'remarks': 'Rejected: Core breeding area strictly closed to unescorted general tourism.',
                },
            ]

            for t_rec in tour_data:
                TourismRecord.objects.create(
                    visitor_name=t_rec['visitor_name'],
                    contact_phone=t_rec['contact_phone'],
                    contact_email=t_rec['contact_email'],
                    visit_date=t_rec['visit_date'],
                    visitor_count=t_rec['visitor_count'],
                    zone=t_rec['zone'],
                    location_area=t_rec['area'],
                    purpose_of_visit=t_rec['purpose'],
                    status=t_rec['status'],
                    remarks=t_rec['remarks'],
                    recorded_by=fo_user
                )

            self.stdout.write(self.style.SUCCESS("  [OK] 7 regulated tourism permit records created."))

            # -------------------------------------------------------------
            # STEP 10: Departmental Notifications and Audit Logs
            # -------------------------------------------------------------
            self.stdout.write("\n[10/10] Establishing role notifications and operational audit logs...")
            Notification.objects.all().delete()

            # Notifications for Admin
            Notification.objects.create(
                recipient=admin_user,
                title="Q3 Conservation Report Submitted",
                message="Dr. Amit Joshi submitted the finalized Q3 Telemetry & Corridor Risk Analysis Report.",
                category="REPORT_SUBMISSION",
                link_url="/research/reports/",
                is_read=False
            )
            Notification.objects.create(
                recipient=admin_user,
                title="Urgent Powerline Diverter Request",
                message="Range Forest Office Solapur flagged missing bird diverters on Gangewadi Corridor 33kV line.",
                category="INCIDENT_ALERT",
                link_url="/admin-panel/records/officer/",
                is_read=False
            )

            # Notifications for Forest Officer
            Notification.objects.create(
                recipient=fo_user,
                title="New Field Incident Awaiting Verification",
                message="Ranger Vikram Patil reported feral dog intrusion near Core Breeding Sanctuary northern culvert.",
                category="INCIDENT_ALERT",
                link_url=f"/officer/incidents/{db_incidents[3].id}/",
                is_read=False
            )
            Notification.objects.create(
                recipient=fo_user,
                title="Medical Case Update: ICU Patient GIB-NNJ-011",
                message="Dr. Sunita Kulkarni logged clinical improvement for female bustard Chandrabhaga.",
                category="MEDICAL_UPDATE",
                link_url=f"/officer/incidents/{db_incidents[0].id}/",
                is_read=False
            )
            Notification.objects.create(
                recipient=fo_user,
                title="Pending Tourism Permit Application",
                message="Deccan Birders Photography Circle submitted application for Watchtower #2 Hide.",
                category="TOURISM_PERMIT",
                link_url="/officer/tourism/",
                is_read=False
            )

            # Notifications for Ranger
            Notification.objects.create(
                recipient=rng_patil,
                title="New Patrol Assignment Dispatched",
                message="Forest Officer Rajesh Deshmukh assigned: Inspect and secure northern culvert mesh against feral dogs.",
                category="TASK_ASSIGNMENT",
                link_url="/ranger/assignments/",
                is_read=False
            )
            Notification.objects.create(
                recipient=rng_patil,
                title="Boundary Pillar Survey Assigned",
                message="Survey boundary pillars 14 to 19 along western buffer line.",
                category="TASK_ASSIGNMENT",
                link_url="/ranger/assignments/",
                is_read=False
            )

            # Notifications for Medical Team
            Notification.objects.create(
                recipient=vet_user,
                title="Emergency Field Handover Completed",
                message="Female bustard Chandrabhaga admitted into ICU with right wing contusion following powerline rescue.",
                category="MEDICAL_ALERT",
                link_url="/medical/dashboard/",
                is_read=False
            )
            Notification.objects.create(
                recipient=vet_user,
                title="Pre-Release Health Clearance Due",
                message="Sub-adult Nannaj Pride scheduled for final physical conditioning evaluation.",
                category="MEDICAL_ALERT",
                link_url="/medical/dashboard/",
                is_read=False
            )

            # Notifications for Researcher
            Notification.objects.create(
                recipient=res_joshi,
                title="Verified Field Incidents Synchronized",
                message="Forest Officer verified 32 field observations. Available in Research Analytics view.",
                category="RESEARCH_SYNC",
                link_url="/research/dashboard/",
                is_read=False
            )

            # Audit Activity Logs
            ActivityLog.objects.all().delete()
            logs_data = [
                (admin_user, "SEED_DEMO_DATA", "Conservation System initialized with realistic Nannaj field dataset and authentic GIB register."),
                (fo_user, "VERIFY", f"Verified Critical Incident {db_incidents[0].incident_id} (High-Tension Powerline Strike)."),
                (rng_patil, "CREATE", f"Reported emergency wildlife rescue incident {db_incidents[0].incident_id} in Solapur Buffer."),
                (vet_user, "CREATE", f"Admitted female GIB-NNJ-011 into ICU Recovery Ward; administered emergency analgesics."),
                (fo_user, "ASSIGN", f"Dispatched emergency patrol task to Ranger Vikram Patil for wire snare sweep."),
                (res_joshi, "REPORT_GEN", "Compiled and finalized October 2026 Monthly Habitat Utilization & Threat Assessment Report."),
                (fo_user, "UPDATE", "Updated Tourism Restrictions for Nannaj Core Breeding Sanctuary (PROHIBITED)."),
                (admin_user, "LOGIN", "System Administrator logged in to inspect sanctuary dashboard metrics."),
                (vet_user, "UPDATE", "Certified pre-release fitness clearance for juvenile bustard GIB-NNJ-005."),
                (fo_user, "VERIFY", f"Verified Poaching Alert {db_incidents[2].incident_id} and confiscated wire snares."),
                (rng_patil, "UPDATE", "Completed 3-km perimeter wire snare search along western buffer boundary."),
                (fo_user, "CREATE", "Approved scientific research tourism permit for Solapur University field team."),
            ]

            for u_log, act, desc in logs_data:
                ActivityLog.objects.create(
                    user=u_log,
                    user_display=u_log.get_full_name() or u_log.username,
                    action=act,
                    description=desc,
                    timestamp=now - timedelta(hours=len(logs_data))
                )

            self.stdout.write(self.style.SUCCESS("  [OK] Notifications and audit log trail successfully established."))

        self.stdout.write(self.style.SUCCESS("\n" + "=" * 76))
        self.stdout.write(self.style.SUCCESS("  BUSTARD BEACON DATABASE POPULATION COMPLETED SUCCESSFULLY!"))
        self.stdout.write(self.style.SUCCESS("=" * 76))
        self.stdout.write(self.style.NOTICE("Summary of Populated Records:"))
        self.stdout.write(f"  - System Users:           {User.objects.count()} (Admin: admin / admin123 preserved)")
        self.stdout.write(f"  - Conservation Zones:     {ConservationZone.objects.count()} (Nannaj Core, Buffer, Tourism, Corridor)")
        self.stdout.write(f"  - Bustard Master Register: {Bustard.objects.count()} (15 living birds + 1 historic death record)")
        self.stdout.write(f"  - Incidents & Evidence:   {Incident.objects.count()} field incidents with authentic photos")
        self.stdout.write(f"  - Patrol Assignments:     {PatrolAssignment.objects.count()} tasks with ranger instructions & attachments")
        self.stdout.write(f"  - Medical Rescue Cases:   {MedicalCase.objects.count()} clinical cases across all 5 statuses & stages")
        self.stdout.write(f"  - Medical Treatments:     {MedicalTreatment.objects.count()} clinical treatment entries")
        self.stdout.write(f"  - Medical Equipment:      {MedicalEquipment.objects.count()} operational kits in inventory")
        self.stdout.write(f"  - Research Movements:     {BustardMovement.objects.count()} GPS telemetry data points across 30 days")
        self.stdout.write(f"  - Conservation Reports:   {ConservationReport.objects.count()} research reports (Finalized & Draft)")
        self.stdout.write(f"  - Tourism Records:        {TourismRecord.objects.count()} visitor permits in Maldhok Tourism Area")
        self.stdout.write(f"  - Notifications & Logs:   {Notification.objects.count()} notifications, {ActivityLog.objects.count()} audit log entries")
        self.stdout.write(self.style.SUCCESS("=" * 76 + "\n"))
