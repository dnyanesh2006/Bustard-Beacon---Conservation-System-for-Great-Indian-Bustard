from django.shortcuts import render
from ..models import Incident, ConservationZone, Bustard, TourismRestriction

def landing_view(request):
    """
    Public landing page for Bustard Beacon platform.
    Displays factual conservation context for Nannaj / Solapur sanctuary.
    """
    verified_field_incidents = Incident.objects.filter(status='VERIFIED').count()
    active_zones_count = ConservationZone.objects.filter(is_active=True).count()
    registered_birds_count = Bustard.objects.filter(health_status='HEALTHY').count()

    context = {
        'verified_field_incidents': verified_field_incidents,
        'active_zones_count': active_zones_count,
        'registered_birds_count': registered_birds_count,
    }
    return render(request, 'landing.html', context)

def about_view(request):
    """
    About page detailing the Great Indian Bustard (*Ardeotis nigriceps*),
    Solapur district sanctuary history, and conservation workflow.
    """
    return render(request, 'about.html')

def tourism_view(request):
    """
    Tourism Information / Visitor Guidelines demonstration page.
    Displays current tourism restrictions and visitor guidelines for the sanctuary.
    """
    restrictions = TourismRestriction.objects.all().select_related('zone')
    return render(request, 'tourism.html', {'restrictions': restrictions})
