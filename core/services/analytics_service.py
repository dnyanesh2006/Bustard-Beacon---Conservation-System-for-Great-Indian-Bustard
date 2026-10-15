from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta
from ..models import (
    Incident, BustardMovement, ConservationZone, 
    MedicalCase, Bustard
)

def get_analytics_data(from_date, to_date):
    """
    Computes comprehensive analytics across the project based on the selected date range.
    """
    # Calculate previous period for comparison
    period_length = (to_date - from_date).days
    if period_length <= 0:
        period_length = 30
    prev_from_date = from_date - timedelta(days=period_length)
    prev_to_date = to_date - timedelta(days=period_length)

    # 1. Sightings Analysis
    sightings = Incident.objects.filter(category='BIRD_SIGHTING', reported_at__date__gte=from_date, reported_at__date__lte=to_date)
    prev_sightings = Incident.objects.filter(category='BIRD_SIGHTING', reported_at__date__gte=prev_from_date, reported_at__date__lte=prev_to_date)
    
    total_sightings = sightings.count()
    prev_total_sightings = prev_sightings.count()
    sighting_change = total_sightings - prev_total_sightings
    sighting_pct = round((sighting_change / prev_total_sightings * 100), 1) if prev_total_sightings else 0

    sightings_by_zone = sightings.values('location__zone__name').annotate(total=Count('id')).order_by('-total')
    highest_sighting_zone = sightings_by_zone.first() if sightings_by_zone else None

    # Unique identified birds in sightings (where bustard is not null)
    unique_birds_sighted = sightings.exclude(bustard__isnull=True).values('bustard').distinct().count()

    # 2. Incident Analysis
    all_incidents = Incident.objects.filter(reported_at__date__gte=from_date, reported_at__date__lte=to_date)
    total_incidents = all_incidents.count()
    
    incidents_by_zone = all_incidents.values('location__zone__name').annotate(total=Count('id')).order_by('-total')
    highest_incident_zone = incidents_by_zone.first() if incidents_by_zone else None
    
    medical_incident_count = all_incidents.filter(category__in=['INJURED_BIRD', 'SICK_BIRD']).count()
    priority_distribution = all_incidents.values('priority').annotate(total=Count('id'))
    category_distribution = all_incidents.values('category').annotate(total=Count('id'))

    # 3. Medical Analysis
    medical_cases = MedicalCase.objects.filter(created_at__date__gte=from_date, created_at__date__lte=to_date)
    total_medical = medical_cases.count()
    
    medical_statuses = medical_cases.values('status').annotate(total=Count('id'))
    active_rehab = medical_cases.filter(status__in=['ACTIVE', 'UNDER_TREATMENT', 'REHABILITATION']).count()
    recovered = medical_cases.filter(status='RECOVERED').count()
    released = medical_cases.filter(status='CLOSED', rehabilitation_stage='RELEASED').count()
    deaths = medical_cases.filter(status='CLOSED', rehabilitation_stage='DECEASED').count()

    # Medical outcomes by zone
    medical_by_zone = medical_cases.values('incident__location__zone__name').annotate(total=Count('id')).order_by('-total')

    # 4. Bird & Zone Base Stats
    total_registered_birds = Bustard.objects.exclude(health_status='DECEASED').count()

    # 5. Data Quality
    missing_zone_incidents = all_incidents.filter(location__zone__isnull=True).count()
    unidentified_sightings = sightings.filter(bustard__isnull=True).count()

    # Generate Insights
    insights = []

    # Sightings insight
    if total_sightings > 0 and prev_total_sightings > 0:
        dir_word = "increased" if sighting_change > 0 else "decreased"
        insights.append({
            'title': f'Sightings {dir_word.title()}',
            'observation': f'Recorded sightings {dir_word} by {abs(sighting_pct)}% ({total_sightings} vs {prev_total_sightings} in the previous period).',
            'interpretation': f'This indicates a potential change in bird activity or monitoring effort during this period.',
            'recommendation': 'Further field verification may help determine if this reflects actual population shifts or patrol frequency variations.'
        })
    elif total_sightings > 0:
        insights.append({
            'title': 'Sighting Baseline Established',
            'observation': f'A total of {total_sightings} sightings were recorded in the current period.',
            'interpretation': 'Initial activity baseline.',
            'recommendation': None
        })

    # Zone concentration insight
    if highest_incident_zone and highest_incident_zone['total'] > 0:
        zone_name = highest_incident_zone['location__zone__name'] or 'Unassigned Regions'
        insights.append({
            'title': 'Incident Concentration',
            'observation': f'Zone "{zone_name}" recorded the highest number of overall incidents ({highest_incident_zone["total"]}).',
            'interpretation': 'This zone is currently experiencing higher general activity or threat levels than other areas.',
            'recommendation': 'Review the incident types in this zone to determine if additional patrols or conservation measures are required.'
        })

    # Zone sightings insight
    if highest_sighting_zone and highest_sighting_zone['total'] > 0:
        zone_name = highest_sighting_zone['location__zone__name'] or 'Unassigned Regions'
        insights.append({
            'title': 'High Activity Zone',
            'observation': f'Zone "{zone_name}" recorded the most sightings ({highest_sighting_zone["total"]}).',
            'interpretation': 'This area serves as a significant active habitat or movement corridor during this timeframe.',
            'recommendation': 'Consider focusing observational research efforts and minimizing disruptive human activity in this zone.'
        })

    # Medical Insight
    if total_medical > 0:
        if deaths > 0:
            insights.append({
                'title': 'Medical Casualties',
                'observation': f'There were {deaths} confirmed death(s) out of {total_medical} medical cases.',
                'interpretation': 'Fatalities occurred during this reporting period.',
                'recommendation': 'Investigate causes of death (e.g. powerline collisions vs natural) to guide immediate preventative infrastructure changes.'
            })
        if released > 0:
            insights.append({
                'title': 'Successful Rehabilitations',
                'observation': f'{released} bird(s) were successfully rehabilitated and released to the wild.',
                'interpretation': 'Medical interventions yielded positive conservation outcomes.',
                'recommendation': None
            })

    # Data Quality Insight
    if missing_zone_incidents > 0 or unidentified_sightings > 0:
        issues = []
        if missing_zone_incidents > 0: issues.append(f"{missing_zone_incidents} incidents lack zone data")
        if unidentified_sightings > 0: issues.append(f"{unidentified_sightings} sightings lack specific bird identification")
        insights.append({
            'title': 'Data Completeness Limitation',
            'observation': " and ".join(issues) + ".",
            'interpretation': 'Incomplete field data restricts the accuracy of zone-specific and bird-specific analyses.',
            'recommendation': 'Encourage Rangers to utilize GPS features and submit clear photos for accurate bird identification.'
        })

    if not insights:
        insights.append({
            'title': 'Insufficient Data',
            'observation': 'Not enough data was recorded in the selected period to generate meaningful insights.',
            'interpretation': 'The analytical baseline is empty.',
            'recommendation': 'Ensure that field teams are actively recording sightings and incidents in the system.'
        })

    # Prepare detailed table data
    zone_stats_dict = {}
    for z in incidents_by_zone:
        name = z['location__zone__name'] or 'Unassigned'
        zone_stats_dict[name] = {'incidents': z['total'], 'sightings': 0, 'medical': 0}
    
    for z in sightings_by_zone:
        name = z['location__zone__name'] or 'Unassigned'
        if name not in zone_stats_dict: zone_stats_dict[name] = {'incidents': 0, 'sightings': 0, 'medical': 0}
        zone_stats_dict[name]['sightings'] = z['total']
        
    for z in medical_by_zone:
        name = z['incident__location__zone__name'] or 'Unassigned'
        if name not in zone_stats_dict: zone_stats_dict[name] = {'incidents': 0, 'sightings': 0, 'medical': 0}
        zone_stats_dict[name]['medical'] = z['total']
        
    zone_stats = [{'zone': k, **v} for k, v in zone_stats_dict.items()]
    zone_stats.sort(key=lambda x: (x['incidents'] + x['sightings']), reverse=True)

    return {
        'total_sightings': total_sightings,
        'sighting_change': sighting_change,
        'sighting_pct': sighting_pct,
        'unique_birds_sighted': unique_birds_sighted,
        'total_incidents': total_incidents,
        'medical_incident_count': medical_incident_count,
        'priority_distribution': list(priority_distribution),
        'category_distribution': list(category_distribution),
        'total_medical': total_medical,
        'medical_statuses': list(medical_statuses),
        'active_rehab': active_rehab,
        'recovered': recovered,
        'released': released,
        'deaths': deaths,
        'total_registered_birds': total_registered_birds,
        'missing_zone_incidents': missing_zone_incidents,
        'unidentified_sightings': unidentified_sightings,
        'insights': insights,
        'zone_stats': zone_stats,
    }
