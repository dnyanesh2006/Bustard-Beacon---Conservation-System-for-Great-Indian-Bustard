import random
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from core.models import (
    Incident, Bustard, BustardMovement, ConservationZone, IncidentLocation, 
    MedicalCase, UserProfile, ROLE_RANGER
)
from django.contrib.auth.models import User

class Command(BaseCommand):
    help = 'Seeds realistic demonstration data for the Researcher Dashboard.'

    def handle(self, *args, **kwargs):
        self.stdout.write("Checking environment...")
        
        ranger_user, _ = User.objects.get_or_create(username='demo_ranger')
        UserProfile.objects.get_or_create(user=ranger_user, defaults={'role': ROLE_RANGER})
        
        zones = [
            'Nannaj Core Breeding Sanctuary',
            'Solapur Grassland Buffer Zone',
            'Maldhok Tourism & Visitor Area',
            'Karmala Migration Corridor',
            'Mohol Agro-Forestry Patch'
        ]
        db_zones = []
        for z in zones:
            obj, _ = ConservationZone.objects.get_or_create(name=z, defaults={'zone_type': 'CORE', 'code': f'Z{random.randint(100,999)}'})
            db_zones.append(obj)
            
        now = timezone.now()
        categories = ['BIRD_SIGHTING', 'BIRD_SIGHTING', 'BIRD_SIGHTING', 'INJURED_BIRD', 'POACHING_ATTEMPT', 'POWERLINE_COLLISION', 'HABITAT_ENCROACHMENT']
        priorities = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
        medical_statuses = ['ACTIVE', 'UNDER_TREATMENT', 'REHABILITATION', 'RECOVERED', 'CLOSED']
        
        self.stdout.write("Seeding 30 demonstration incidents and medical cases...")
        
        for i in range(30):
            days_ago = random.randint(0, 29)
            incident_date = now - timedelta(days=days_ago)
            
            cat = random.choice(categories)
            pri = random.choice(priorities) if cat != 'BIRD_SIGHTING' else 'LOW'
            
            inc = Incident.objects.create(
                reporter=ranger_user,
                category=cat,
                priority=pri,
                description=f"[DEMO DATA] Generated incident {i}",
                status='VERIFIED' if cat == 'BIRD_SIGHTING' else 'INVESTIGATING',
                data_environment='DEMO'
            )
            Incident.objects.filter(id=inc.id).update(reported_at=incident_date)
            
            zone = random.choice(db_zones)
            loc = IncidentLocation.objects.create(
                incident=inc,
                latitude=17.5 + random.random(), 
                longitude=75.5 + random.random(),
                zone=zone
            )
            
            if cat in ['INJURED_BIRD', 'POWERLINE_COLLISION']:
                med = MedicalCase.objects.create(
                    incident=inc,
                    assigned_team=ranger_user,
                    status=random.choice(medical_statuses),
                    diagnosis="[DEMO DATA] Sample Diagnosis",
                    condition_summary="[DEMO DATA] Sample Summary",
                )
                MedicalCase.objects.filter(id=med.id).update(created_at=incident_date)
                
        self.stdout.write("Seeding 40 demonstration movement tracks...")
        for i in range(40):
            days_ago = random.randint(0, 29)
            mov_date = now - timedelta(days=days_ago)
            zone = random.choice(db_zones)
            b_obj, _ = Bustard.objects.get_or_create(
                tag_id=f"BIRD-DEMO-{random.randint(1,5)}",
                defaults={'name': f"Demo Bird {i}", 'data_environment': 'DEMO'}
            )
            mov = BustardMovement.objects.create(
                bustard=b_obj,
                latitude=17.5 + random.random(),
                longitude=75.5 + random.random(),
                data_source='DEMO',
                confidence=80
            )
            BustardMovement.objects.filter(id=mov.id).update(recorded_at=mov_date)
            
        self.stdout.write(self.style.SUCCESS('Successfully seeded demo data!'))
