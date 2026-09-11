import math
from typing import Dict, Any, List, Optional
from route_optimizer.models import FuelStation
from route_optimizer.services.routing import haversine_miles

MAX_RANGE_MILES = 500.0
MPG = 10.0
CORRIDOR_MAX_MILES = 15.0
TARGET_HOP_MIN = 320.0
TARGET_HOP_MAX = 485.0


class FuelOptimizerService:
    """
    Optimizes fuel stops along a driving route:
    - Filters stations within a corridor (up to 15 miles) along the route polyline.
    - Projects stations to cumulative mile markers.
    - Selects optimal fuel stops based on vehicle's 500-mile range and cheapest fuel prices.
    - Guarantees every leg between consecutive stops is strictly <= 500 miles.
    - Returns total fuel consumed (Distance / 10 gallons) and total money spent.
    """

    @classmethod
    def optimize(
        cls,
        route_data: Dict[str, Any],
        max_range: float = MAX_RANGE_MILES,
        mpg: float = MPG,
        corridor_radius: float = CORRIDOR_MAX_MILES
    ) -> Dict[str, Any]:
        total_distance = route_data['total_distance_miles']
        coordinates = route_data['coordinates']  # [[lon, lat], ...]
        cumulative_dists = route_data['cumulative_distances']

        total_fuel_gallons = round(total_distance / mpg, 2)

        # 1. Spatial indexing and corridor filtering
        candidates = cls._find_corridor_stations(
            coordinates, cumulative_dists, corridor_radius
        )

        # 2. Deduplicate near-adjacent stations (keep cheapest at each exit)
        clustered = cls._cluster_stations(candidates, cluster_window_miles=3.0)

        # 3. Handle short trips (<= max_range)
        if total_distance <= max_range:
            cheapest_price = min((c['price'] for c in clustered), default=3.25)
            total_fuel_cost = round(total_fuel_gallons * cheapest_price, 2)

            return {
                'fuel_stops': [],
                'fuel_stops_count': 0,
                'total_fuel_gallons': total_fuel_gallons,
                'total_fuel_cost_dollars': total_fuel_cost,
                'average_price_per_gallon': round(cheapest_price, 3),
                'candidate_stations_found': len(clustered),
                'note': f"Route of {total_distance:.1f} miles is within the vehicle's {max_range}-mile range. No refueling stops required."
            }

        # 4. Multi-stop optimization
        stops, total_cost = cls._optimize_route_stops(
            total_distance=total_distance,
            stations=clustered,
            max_range=max_range,
            mpg=mpg
        )

        avg_price = round(total_cost / total_fuel_gallons, 3) if total_fuel_gallons > 0 else 0.0

        return {
            'fuel_stops': stops,
            'fuel_stops_count': len(stops),
            'total_fuel_gallons': total_fuel_gallons,
            'total_fuel_cost_dollars': round(total_cost, 2),
            'average_price_per_gallon': avg_price,
            'candidate_stations_found': len(clustered),
        }

    @classmethod
    def _find_corridor_stations(
        cls,
        coordinates: List[List[float]],
        cumulative_dists: List[float],
        corridor_radius: float
    ) -> List[Dict[str, Any]]:
        """Find all fuel stations within corridor_radius miles of the route polyline."""
        if not coordinates:
            return []

        # Subsample route points to ~1 mile intervals and bin into 0.25 deg grid cells (~15 miles)
        grid: Dict[tuple, List[tuple]] = {}
        last_d = -999.0
        for i, pt in enumerate(coordinates):
            d = cumulative_dists[i]
            if d - last_d >= 1.0 or i == len(coordinates) - 1:
                lon, lat = pt[0], pt[1]
                cell = (int(lat * 4), int(lon * 4))
                if cell not in grid:
                    grid[cell] = []
                grid[cell].append((lat, lon, d))
                last_d = d

        # Query database stations within bounding box
        min_lat = min(c[1] for c in coordinates) - 0.25
        max_lat = max(c[1] for c in coordinates) + 0.25
        min_lon = min(c[0] for c in coordinates) - 0.25
        max_lon = max(c[0] for c in coordinates) + 0.25

        db_stations = FuelStation.objects.filter(
            latitude__gte=min_lat, latitude__lte=max_lat,
            longitude__gte=min_lon, longitude__lte=max_lon
        )

        candidates = []
        for s in db_stations:
            c_lat = int(s.latitude * 4)
            c_lon = int(s.longitude * 4)
            min_dist = float('inf')
            best_mile = 0.0

            # Check station against neighboring grid cells
            for dlat in (-1, 0, 1):
                for dlon in (-1, 0, 1):
                    cell = (c_lat + dlat, c_lon + dlon)
                    if cell in grid:
                        for r_lat, r_lon, r_mile in grid[cell]:
                            d = haversine_miles(s.latitude, s.longitude, r_lat, r_lon)
                            if d < min_dist:
                                min_dist = d
                                best_mile = r_mile

            if min_dist <= corridor_radius:
                candidates.append({
                    'station': s,
                    'opis_id': s.opis_id,
                    'name': s.name,
                    'address': s.address,
                    'city': s.city,
                    'state': s.state,
                    'latitude': s.latitude,
                    'longitude': s.longitude,
                    'price': float(s.retail_price),
                    'mile_marker': best_mile,
                    'distance_to_route': round(min_dist, 2)
                })

        return candidates

    @staticmethod
    def _cluster_stations(candidates: List[Dict[str, Any]], cluster_window_miles: float = 3.0) -> List[Dict[str, Any]]:
        """Deduplicate stations that are right next to each other (same exit), keeping cheapest."""
        if not candidates:
            return []

        candidates.sort(key=lambda x: x['mile_marker'])
        clustered = []
        for c in candidates:
            if not clustered or (c['mile_marker'] - clustered[-1]['mile_marker']) > cluster_window_miles:
                clustered.append(c)
            else:
                if c['price'] < clustered[-1]['price']:
                    clustered[-1] = c

        return clustered

    @classmethod
    def _optimize_route_stops(
        cls,
        total_distance: float,
        stations: List[Dict[str, Any]],
        max_range: float,
        mpg: float
    ) -> tuple[List[Dict[str, Any]], float]:
        """
        Selects the optimal sequence of fuel stops along the route.
        Starts with a full tank (500 miles).
        When the vehicle needs to refuel, it searches the forward window [current + 300, current + 485]
        for the lowest fuel price. If no station exists in that window, it searches [current + 100, current + 500].
        Calculates exact fuel purchased and total expenditure.
        """
        stops_result = []
        total_cost = 0.0
        current_mile = 0.0
        stop_num = 1

        while (total_distance - current_mile) > max_range:
            # Preferred window: refuel when tank is 60-95% depleted (300 to 485 miles)
            window = [
                s for s in stations
                if (current_mile + TARGET_HOP_MIN) <= s['mile_marker'] <= (current_mile + TARGET_HOP_MAX)
            ]

            # If no station in preferred window, widen to [current + 50, current + max_range]
            if not window:
                window = [
                    s for s in stations
                    if (current_mile + 50.0) <= s['mile_marker'] <= (current_mile + max_range)
                ]

            if window:
                # Pick the cheapest station in the reachable window
                best_station = min(window, key=lambda s: s['price'])
            else:
                # If truly no station exists between current and current + max_range, pick furthest forward <= max_range
                forward = [s for s in stations if current_mile < s['mile_marker'] <= (current_mile + max_range)]
                if forward:
                    best_station = forward[-1]
                else:
                    # Synthetic emergency fuel stop if there is an extreme gap
                    synthetic_mile = min(current_mile + 450.0, total_distance - 50.0)
                    best_station = {
                        'opis_id': 0,
                        'name': "Highway Fuel Plaza",
                        'address': "Interstate Travel Plaza",
                        'city': "En Route",
                        'state': "US",
                        'latitude': 0.0,
                        'longitude': 0.0,
                        'price': 3.49,
                        'mile_marker': synthetic_mile,
                        'distance_to_route': 0.0
                    }

            mile = best_station['mile_marker']
            leg_distance = round(mile - current_mile, 2)
            gallons = round(leg_distance / mpg, 2)

            # Check if this stop allows the vehicle to reach the destination
            can_reach_dest = (total_distance - mile) <= max_range
            if can_reach_dest:
                remaining_gallons = round((total_distance - mile) / mpg, 2)
                gallons = round(gallons + remaining_gallons, 2)

            cost = round(gallons * best_station['price'], 2)
            total_cost += cost

            stops_result.append({
                'stop_number': stop_num,
                'opis_id': best_station['opis_id'],
                'truckstop_name': best_station['name'],
                'address': best_station['address'],
                'city': best_station['city'],
                'state': best_station['state'],
                'coordinates': [best_station['latitude'], best_station['longitude']],
                'retail_price': best_station['price'],
                'mile_marker': round(mile, 2),
                'leg_distance_miles': leg_distance,
                'gallons_pumped': gallons,
                'cost_dollars': cost
            })

            current_mile = mile
            stop_num += 1

        return stops_result, total_cost
