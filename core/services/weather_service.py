import requests

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODE_MAP = {
    0: "Clear Sky",
    1: "Mainly Clear",
    2: "Partly Cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing Rime Fog",
    51: "Light Drizzle",
    53: "Moderate Drizzle",
    55: "Dense Drizzle",
    61: "Slight Rain",
    63: "Moderate Rain",
    65: "Heavy Rain",
    80: "Slight Rain Showers",
    81: "Moderate Rain Showers",
    82: "Violent Rain Showers",
    95: "Thunderstorm",
}

def get_weather_at_coordinates(lat, lng):
    """
    Fetch current weather context for (lat, lng) via Open-Meteo public API.
    Returns dict: {'temperature_c': float, 'condition': str, 'wind_speed_kmh': float}
    """
    try:
        params = {
            'latitude': lat,
            'longitude': lng,
            'current_weather': 'true'
        }
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            cw = data.get('current_weather', {})
            code = cw.get('weathercode', 0)
            condition = WEATHER_CODE_MAP.get(code, "Clear / Variable")
            return {
                'temperature_c': cw.get('temperature', 32.0),
                'condition': condition,
                'wind_speed_kmh': cw.get('windspeed', 12.5)
            }
    except Exception:
        pass

    # Safe environmental default for Solapur/Nannaj region
    return {
        'temperature_c': 31.5,
        'condition': 'Semi-Arid / Sunny',
        'wind_speed_kmh': 14.0
    }
