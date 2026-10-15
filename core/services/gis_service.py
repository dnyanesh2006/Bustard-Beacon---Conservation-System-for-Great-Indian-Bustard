import json
import math
from ..models import ConservationZone, IncidentLocation, Incident

def is_point_in_polygon(lat, lng, polygon_coords):
    """
    Ray casting point-in-polygon algorithm.
    polygon_coords is a list of [lat, lng] pairs.
    """
    if not polygon_coords or len(polygon_coords) < 3:
        return False

    n = len(polygon_coords)
    inside = False
    p1lat, p1lng = polygon_coords[0]

    for i in range(n + 1):
        p2lat, p2lng = polygon_coords[i % n]
        if lng > min(p1lng, p2lng):
            if lng <= max(p1lng, p2lng):
                if lat <= max(p1lat, p2lat):
                    if p1lng != p2lng:
                        xinters = (lng - p1lng) * (p2lat - p1lat) / (p2lng - p1lng) + p1lat
                    else:
                        xinters = p1lat
                    if p1lat == p2lat or lat <= xinters:
                        inside = not inside
        p1lat, p1lng = p2lat, p2lng

    return inside

def haversine_distance(lat1, lon1, lat2, lon2):
    """
    Calculate distance in km between two lat/lng points.
    """
    R = 6371.0 # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def detect_zone_for_point(lat, lng):
    """
    Detects which ConservationZone encompasses (lat, lng).
    If no polygon matches, finds closest zone centroid.
    """
    zones = ConservationZone.objects.filter(is_active=True)
    matched_zone = None

    for zone in zones:
        if zone.boundary_geojson:
            try:
                coords = json.loads(zone.boundary_geojson)
                if is_point_in_polygon(lat, lng, coords):
                    matched_zone = zone
                    break
            except Exception:
                continue

    if not matched_zone and zones.exists():
        # Fallback to closest zone by distance centroid
        min_dist = float('inf')
        for zone in zones:
            if zone.boundary_geojson:
                try:
                    coords = json.loads(zone.boundary_geojson)
                    avg_lat = sum(c[0] for c in coords) / len(coords)
                    avg_lng = sum(c[1] for c in coords) / len(coords)
                    dist = haversine_distance(lat, lng, avg_lat, avg_lng)
                    if dist < min_dist:
                        min_dist = dist
                        matched_zone = zone
                except Exception:
                    continue
        if not matched_zone:
            matched_zone = zones.first()

    return matched_zone

def calculate_high_risk_zones():
    """
    Calculate zone risk scores based on verified/pending field incidents.
    Critical = 5, High = 4, Medium = 2, Low = 1.
    """
    weight_map = {
        'CRITICAL': 5,
        'HIGH': 4,
        'MEDIUM': 2,
        'LOW': 1,
    }

    results = []
    zones = ConservationZone.objects.filter(is_active=True)

    for zone in zones:
        locations = IncidentLocation.objects.filter(
            zone=zone,
            incident__status__in=['PENDING', 'VERIFIED']
        ).select_related('incident')

        total_count = locations.count()
        critical_count = 0
        high_count = 0
        risk_score = 0

        for loc in locations:
            inc = loc.incident
            w = weight_map.get(inc.priority, 1)
            risk_score += w
            if inc.priority == 'CRITICAL':
                critical_count += 1
            elif inc.priority == 'HIGH':
                high_count += 1

        if risk_score >= 15:
            level = 'CRITICAL'
            badge_class = 'danger'
        elif risk_score >= 8:
            level = 'HIGH'
            badge_class = 'warning'
        elif risk_score >= 3:
            level = 'MEDIUM'
            badge_class = 'info'
        else:
            level = 'LOW'
            badge_class = 'success'

        results.append({
            'zone': zone,
            'total_incidents': total_count,
            'critical_count': critical_count,
            'high_count': high_count,
            'risk_score': risk_score,
            'risk_level': level,
            'badge_class': badge_class,
        })

    results.sort(key=lambda x: x['risk_score'], reverse=True)
    return results
