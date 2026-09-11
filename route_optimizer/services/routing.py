import math
from typing import Dict, Any, List
import requests

METERS_TO_MILES = 0.000621371
SECONDS_TO_HOURS = 1 / 3600.0


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth in miles."""
    r_earth = 3958.8  # Earth radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2)
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r_earth * c


class RoutingService:
    OSRM_BASE_URL = "https://router.project-osrm.org/route/v1/driving"

    @classmethod
    def get_route(cls, start: Dict[str, float], finish: Dict[str, float]) -> Dict[str, Any]:
        """
        Request driving route from OSRM demo server.
        Coordinates are [lon, lat] per GeoJSON specification.
        """
        start_lon, start_lat = start['lon'], start['lat']
        finish_lon, finish_lat = finish['lon'], finish['lat']

        url = f"{cls.OSRM_BASE_URL}/{start_lon},{start_lat};{finish_lon},{finish_lat}"
        params = {
            'overview': 'full',
            'geometries': 'geojson',
            'annotations': 'false'
        }
        headers = {
            'User-Agent': 'FuelRouteOptimizerApp/1.0 (spotter_assessment)'
        }

        try:
            response = requests.get(url, params=params, headers=headers, timeout=15)
            response.raise_for_status()
            data = response.json()

            if data.get('code') != 'Ok' or not data.get('routes'):
                raise ValueError(f"OSRM returned no valid route: {data.get('message', 'Unknown error')}")

            route = data['routes'][0]
            dist_meters = route['distance']
            duration_secs = route['duration']
            coordinates = route['geometry']['coordinates']  # [[lon, lat], ...]

            distance_miles = dist_meters * METERS_TO_MILES
            duration_hours = duration_secs * SECONDS_TO_HOURS

        except Exception as exc:
            # Fallback for offline test environments or temporary OSRM downtime
            return cls._fallback_interpolated_route(start, finish, str(exc))

        # Calculate cumulative distance along polyline vertices
        cum_dist = cls._compute_cumulative_distances(coordinates, distance_miles)

        return {
            'success': True,
            'total_distance_miles': round(distance_miles, 2),
            'total_duration_hours': round(duration_hours, 2),
            'coordinates': coordinates,
            'cumulative_distances': cum_dist,
            'source': 'osrm'
        }

    @staticmethod
    def _compute_cumulative_distances(coordinates: List[List[float]], total_reported_miles: float) -> List[float]:
        """Compute cumulative distance in miles along each vertex of the polyline."""
        if not coordinates:
            return []

        raw_dists = [0.0]
        for i in range(1, len(coordinates)):
            d = haversine_miles(
                coordinates[i - 1][1], coordinates[i - 1][0],
                coordinates[i][1], coordinates[i][0]
            )
            raw_dists.append(raw_dists[-1] + d)

        total_raw = raw_dists[-1]
        # Scale to match exact driving distance from OSRM if there is small geometry discrepancy
        scale = (total_reported_miles / total_raw) if total_raw > 0 else 1.0
        return [round(d * scale, 3) for d in raw_dists]

    @classmethod
    def _fallback_interpolated_route(cls, start: Dict[str, float], finish: Dict[str, float], error_msg: str) -> Dict[str, Any]:
        """Linear interpolation fallback if external routing API is unreachable."""
        lat1, lon1 = start['lat'], start['lon']
        lat2, lon2 = finish['lat'], finish['lon']
        direct_miles = haversine_miles(lat1, lon1, lat2, lon2)
        # Driving distance is typically ~1.2x great-circle distance
        est_driving_miles = direct_miles * 1.2
        est_duration_hours = est_driving_miles / 55.0  # ~55 mph average

        # Interpolate 100 points along the path
        num_points = max(50, int(est_driving_miles / 20.0))
        coordinates = []
        cum_dist = []
        for i in range(num_points + 1):
            fraction = i / float(num_points)
            lat = lat1 + fraction * (lat2 - lat1)
            lon = lon1 + fraction * (lon2 - lon1)
            coordinates.append([round(lon, 6), round(lat, 6)])
            cum_dist.append(round(fraction * est_driving_miles, 3))

        return {
            'success': True,
            'total_distance_miles': round(est_driving_miles, 2),
            'total_duration_hours': round(est_duration_hours, 2),
            'coordinates': coordinates,
            'cumulative_distances': cum_dist,
            'source': f'fallback_interpolation (OSRM: {error_msg})'
        }
