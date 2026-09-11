from django.test import TestCase
from route_optimizer.models import FuelStation
from route_optimizer.services.fuel_optimizer import FuelOptimizerService


class FuelOptimizerServiceTests(TestCase):
    def setUp(self):
        # Create a line of mock stations every 200 miles along a simulated highway
        self.stations = []
        for i in range(1, 10):
            mile = i * 200.0
            st = FuelStation.objects.create(
                opis_id=1000 + i,
                name=f"Truck Stop #{i}",
                address=f"I-80 Exit {i*20}",
                city=f"City {i}",
                state="NE",
                retail_price=3.00 + (i % 3) * 0.20,  # variation in price
                latitude=40.0 + (i * 0.1),
                longitude=-100.0 + (i * 0.5)
            )
            self.stations.append(st)

    def test_short_trip_under_500_miles(self):
        # 350 mile trip
        route_data = {
            'total_distance_miles': 350.0,
            'total_duration_hours': 5.5,
            'coordinates': [[-100.0, 40.0], [-97.0, 40.5]],
            'cumulative_distances': [0.0, 350.0]
        }
        res = FuelOptimizerService.optimize(route_data, max_range=500.0, mpg=10.0)
        self.assertEqual(res['fuel_stops_count'], 0)
        self.assertEqual(len(res['fuel_stops']), 0)
        self.assertEqual(res['total_fuel_gallons'], 35.0)
        self.assertTrue(res['total_fuel_cost_dollars'] > 0)

    def test_long_trip_refueling_constraints(self):
        # 1,800 mile trip
        # Simulate stations along the route with mile markers
        clustered_stations = [
            {
                'opis_id': 101, 'name': "Stop A", 'address': "Exit 1", 'city': "Town A", 'state': "IL",
                'latitude': 41.0, 'longitude': -88.0, 'price': 3.20, 'mile_marker': 400.0, 'distance_to_route': 1.0
            },
            {
                'opis_id': 102, 'name': "Stop B", 'address': "Exit 2", 'city': "Town B", 'state': "IA",
                'latitude': 41.2, 'longitude': -92.0, 'price': 3.10, 'mile_marker': 750.0, 'distance_to_route': 0.8
            },
            {
                'opis_id': 103, 'name': "Stop C", 'address': "Exit 3", 'city': "Town C", 'state': "NE",
                'latitude': 41.1, 'longitude': -97.0, 'price': 2.95, 'mile_marker': 1150.0, 'distance_to_route': 1.2
            },
            {
                'opis_id': 104, 'name': "Stop D", 'address': "Exit 4", 'city': "Town D", 'state': "WY",
                'latitude': 41.3, 'longitude': -104.0, 'price': 3.30, 'mile_marker': 1550.0, 'distance_to_route': 0.5
            },
        ]

        total_distance = 1800.0
        stops, total_cost = FuelOptimizerService._optimize_route_stops(
            total_distance=total_distance,
            stations=clustered_stations,
            max_range=500.0,
            mpg=10.0
        )

        self.assertTrue(len(stops) >= 3)

        # Check vehicle range constraint: no leg can exceed 500 miles!
        prev_mile = 0.0
        sum_gallons = 0.0
        for s in stops:
            leg_distance = s['mile_marker'] - prev_mile
            self.assertTrue(leg_distance <= 500.0, f"Leg distance {leg_distance} exceeded 500 miles")
            sum_gallons += s['gallons_pumped']
            prev_mile = s['mile_marker']

        # Final leg to destination must also be <= 500 miles
        final_leg = total_distance - prev_mile
        self.assertTrue(final_leg <= 500.0)

        # Total gallons pumped across all stops must equal 180.0 (1800 mi / 10 mpg)
        self.assertAlmostEqual(sum_gallons, 180.0, places=1)
        self.assertTrue(total_cost > 0)

    def test_cluster_stations_deduplication(self):
        # Two stations within 2 miles of each other, one is cheaper
        candidates = [
            {'name': 'Expensive Exit 10', 'mile_marker': 150.0, 'price': 3.60},
            {'name': 'Cheap Exit 10', 'mile_marker': 151.0, 'price': 3.10},
            {'name': 'Next Exit 20', 'mile_marker': 220.0, 'price': 3.40},
        ]
        clustered = FuelOptimizerService._cluster_stations(candidates, cluster_window_miles=3.0)
        self.assertEqual(len(clustered), 2)
        self.assertEqual(clustered[0]['name'], 'Cheap Exit 10')
        self.assertEqual(clustered[0]['price'], 3.10)
