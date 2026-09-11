import json
import os
import re
from typing import Dict, Any, Optional
import requests
from django.conf import settings

US_STATE_NAMES_TO_CODE = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
    'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
    'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
    'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
    'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
    'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
    'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
    'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
    'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV',
    'wisconsin': 'WI', 'wyoming': 'WY', 'district of columbia': 'DC'
}

# In-memory cache
_GEOCODE_CACHE: Dict[str, Dict[str, Any]] = {}
_LOCAL_CITIES_DB: Optional[Dict[str, list]] = None


def _get_local_cities_db() -> Dict[str, list]:
    global _LOCAL_CITIES_DB
    if _LOCAL_CITIES_DB is None:
        db_path = os.path.join(settings.BASE_DIR, 'route_optimizer', 'data', 'us_cities_compact.json')
        if os.path.exists(db_path):
            with open(db_path, 'r', encoding='utf-8') as f:
                _LOCAL_CITIES_DB = json.load(f)
        else:
            _LOCAL_CITIES_DB = {}
    return _LOCAL_CITIES_DB


def is_in_usa(lat: float, lon: float) -> bool:
    """Check if coordinates are approximately within the United States (including AK/HI)."""
    # Continental US: lat 24.396 to 49.384, lon -124.848 to -66.885
    continental = (24.0 <= lat <= 50.0) and (-125.0 <= lon <= -66.0)
    alaska = (51.0 <= lat <= 71.5) and (-179.0 <= lon <= -129.0)
    hawaii = (18.5 <= lat <= 22.5) and (-161.0 <= lon <= -154.0)
    return continental or alaska or hawaii


def parse_coordinates(location_str: str) -> Optional[Dict[str, Any]]:
    """Check if the string is in 'lat,lon' format."""
    match = re.match(r'^\s*([-+]?\d+(?:\.\d+)?)\s*,\s*([-+]?\d+(?:\.\d+)?)\s*$', location_str)
    if match:
        lat = float(match.group(1))
        lon = float(match.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            if not is_in_usa(lat, lon):
                raise ValueError(f"Coordinates ({lat}, {lon}) are outside the United States.")
            return {
                'lat': lat,
                'lon': lon,
                'name': f"{lat:.4f}, {lon:.4f}",
                'source': 'coordinates'
            }
    return None


def lookup_local_city(location_str: str) -> Optional[Dict[str, Any]]:
    """Attempt fast local matching against the bundled US cities database."""
    city_db = _get_local_cities_db()
    if not city_db:
        return None

    cleaned = location_str.strip().lower()
    # If formatted as "City, State", normalize state if full name was passed
    if ',' in cleaned:
        parts = [p.strip() for p in cleaned.split(',', 1)]
        city_part = parts[0]
        state_part = parts[1]
        state_code = US_STATE_NAMES_TO_CODE.get(state_part, state_part.upper())
        key = f"{city_part}, {state_code}"
        if key in city_db:
            lat, lon = city_db[key]
            return {
                'lat': lat,
                'lon': lon,
                'name': f"{city_part.title()}, {state_code}",
                'source': 'local_db'
            }

    # Try direct key
    if cleaned in city_db:
        lat, lon = city_db[cleaned]
        return {
            'lat': lat,
            'lon': lon,
            'name': cleaned.title(),
            'source': 'local_db'
        }

    return None


def geocode_location(location_str: str) -> Dict[str, Any]:
    """
    Geocode a location string into latitude and longitude within the USA.
    Supports:
    1. Raw coordinates: '40.7128, -74.0060'
    2. Local city database lookup: 'Austin, TX', 'New York, NY' (0ms, 0 external API calls)
    3. Nominatim API fallback for addresses, POIs, landmarks.
    """
    if not location_str or not location_str.strip():
        raise ValueError("Location string cannot be empty.")

    query = location_str.strip()
    cache_key = query.lower()

    if cache_key in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[cache_key]

    # 1. Coordinates check
    coord_result = parse_coordinates(query)
    if coord_result:
        _GEOCODE_CACHE[cache_key] = coord_result
        return coord_result

    # 2. Local US cities database
    local_result = lookup_local_city(query)
    if local_result:
        _GEOCODE_CACHE[cache_key] = local_result
        return local_result

    # 3. Fallback to Nominatim
    url = 'https://nominatim.openstreetmap.org/search'
    headers = {
        'User-Agent': 'FuelRouteOptimizerApp/1.0 (spotter_assessment; contact: contact@fuelroute.local)'
    }
    params = {
        'q': query,
        'format': 'json',
        'countrycodes': 'us',
        'limit': 1
    }

    try:
        response = requests.get(url, params=params, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        raise ValueError(f"Geocoding service unavailable for '{query}': {exc}") from exc

    if not data:
        raise ValueError(f"Location not found within the USA: '{query}'")

    first = data[0]
    lat = float(first['lat'])
    lon = float(first['lon'])

    if not is_in_usa(lat, lon):
        raise ValueError(f"Location '{query}' resolved to coordinates ({lat}, {lon}) which are outside the USA.")

    result = {
        'lat': lat,
        'lon': lon,
        'name': first.get('display_name', query),
        'source': 'nominatim'
    }

    _GEOCODE_CACHE[cache_key] = result
    return result
