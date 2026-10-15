import json
from django.shortcuts import render
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from ..models import (
    ConservationZone, Incident, UserProfile,
    ROLE_ADMIN, ROLE_FOREST_OFFICER, ROLE_RANGER, ROLE_MEDICAL_TEAM,
    DATA_ENV_PRODUCTION
)

from django.conf import settings

def live_map_view(request):
    """
    Full-Screen Live Conservation GIS Map.
    Supplies real conservation zones and incident metrics to the sanctuary map view.
    """
    zones = ConservationZone.objects.filter(is_active=True).order_by('id')
    zone_list = []
    for z in zones:
        inc_count = Incident.objects.filter(location__zone=z, data_environment=DATA_ENV_PRODUCTION).count()
        zone_list.append({
            'zone': z,
            'incident_count': inc_count,
        })

    priority_counts = {
        'CRITICAL': Incident.objects.filter(priority='CRITICAL', data_environment=DATA_ENV_PRODUCTION).count(),
        'HIGH': Incident.objects.filter(priority='HIGH', data_environment=DATA_ENV_PRODUCTION).count(),
        'MEDIUM': Incident.objects.filter(priority='MEDIUM', data_environment=DATA_ENV_PRODUCTION).count(),
        'LOW': Incident.objects.filter(priority='LOW', data_environment=DATA_ENV_PRODUCTION).count(),
    }
    total_incidents = sum(priority_counts.values())

    return render(request, 'map.html', {
        'zones_data': zone_list,
        'priority_counts': priority_counts,
        'total_incidents': total_incidents,
        'google_maps_api_key': getattr(settings, 'GOOGLE_MAPS_API_KEY', '')
    })

def api_map_data(request):
    """
    REST Endpoint providing GeoJSON features and markers for Leaflet.
    Enforces sensitive location privacy level checks.
    """
    user = request.user
    is_staff_user = user.is_authenticated and (
        user.is_superuser or
        (hasattr(user, 'profile') and user.profile.role in [ROLE_ADMIN, ROLE_FOREST_OFFICER, ROLE_RANGER, ROLE_MEDICAL_TEAM])
    )

    # 1. Conservation Zones Polygons
    zones = ConservationZone.objects.filter(is_active=True)
    zone_features = []
    for zone in zones:
        coords = []
        if zone.boundary_geojson:
            try:
                coords = json.loads(zone.boundary_geojson)
            except Exception:
                coords = []
        zone_features.append({
            'id': zone.id,
            'name': zone.name,
            'code': zone.code,
            'type': zone.get_zone_type_display(),
            'color': zone.color_hex,
            'coordinates': coords
        })

    # 2. Field Incidents (Role-based coordinate precision)
    incidents = Incident.objects.filter(
        data_environment=DATA_ENV_PRODUCTION,
    ).select_related('location', 'reporter', 'location__zone').prefetch_related('images')
    if not is_staff_user:
        incidents = incidents.filter(status='VERIFIED')
    incident_markers = []
    for inc in incidents:
        if hasattr(inc, 'location') and inc.location:
            lat = inc.location.latitude
            lng = inc.location.longitude

            # If public user, generalize sensitive nesting/critical coordinates slightly (+/- ~1-2km blur)
            visibility_level = "STAFF" if is_staff_user else "PUBLIC"
            if not is_staff_user:
                # Public viewers receive a coarse grid and no operational detail.
                lat = round(lat, 2)
                lng = round(lng, 2)

            image_url = None
            if is_staff_user and inc.images.exists():
                image_url = inc.images.first().image.url

            incident_markers.append({
                'id': inc.id,
                'incident_id': inc.incident_id,
                'category': inc.get_category_display(),
                'priority': inc.priority,
                'status': inc.status,
                'description': inc.description if is_staff_user else 'Verified field report; operational details restricted.',
                'latitude': lat,
                'longitude': lng,
                'reported_at': inc.reported_at.strftime('%Y-%m-%d %H:%M'),
                'reporter': inc.reporter.username if is_staff_user else 'Authorized field team',
                'zone_name': inc.location.zone.name if inc.location.zone else 'Nannaj Sector',
                'weather_temp': inc.location.weather_temperature_c,
                'weather_cond': inc.location.weather_condition,
                'image_url': image_url,
                'data_source': inc.data_source,
                'provenance_label': 'Field Report',
                'visibility': visibility_level
            })


    # 4. Shared Ranger Locations (Only active field mode rangers)
    ranger_markers = []
    if is_staff_user:
        rangers = UserProfile.objects.filter(role=ROLE_RANGER, is_active_field_mode=True, current_latitude__isnull=False)
        for r in rangers:
            ranger_markers.append({
                'username': r.user.username,
                'name': r.user.get_full_name() or r.user.username,
                'badge': r.badge_number,
                'latitude': r.current_latitude,
                'longitude': r.current_longitude,
                'updated_at': r.location_updated_at.strftime('%H:%M:%S') if r.location_updated_at else 'Active'
            })

    return JsonResponse({
        'zones': zone_features,
        'incidents': incident_markers,
        'rangers': ranger_markers,
    })
