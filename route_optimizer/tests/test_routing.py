from django.test import TestCase
from route_optimizer.services.routing import haversine_miles, RoutingService


class RoutingServiceTests(TestCase):
    def test_haversine_distance(self):
        # Distance between NYC (40.7128, -74.0060) and Philadelphia (39.9526, -75.1652) is ~80-85 miles straight line
        dist = haversine_miles(40.7128, -74.0060, 39.9526, -75.1652)
        self.assertTrue(75.0 <= dist <= 90.0)

    def test_haversine_zero(self):
        dist = haversine_miles(35.0, -90.0, 35.0, -90.0)
        self.assertEqual(dist, 0.0)

    def test_compute_cumulative_distances(self):
        coords = [
            [-74.0060, 40.7128],
            [-74.5000, 40.5000],
            [-75.1652, 39.9526]
        ]
        cum_dist = RoutingService._compute_cumulative_distances(coords, 95.0)
        self.assertEqual(len(cum_dist), 3)
        self.assertEqual(cum_dist[0], 0.0)
        self.assertAlmostEqual(cum_dist[-1], 95.0, places=1)
        self.assertTrue(cum_dist[1] > 0.0 and cum_dist[1] < cum_dist[2])

    def test_fallback_interpolation(self):
        start = {'lat': 40.7128, 'lon': -74.0060}
        finish = {'lat': 34.0522, 'lon': -118.2437}
        res = RoutingService._fallback_interpolated_route(start, finish, "Mock timeout")
        self.assertTrue(res['success'])
        self.assertTrue(res['total_distance_miles'] > 2000)
        self.assertTrue(len(res['coordinates']) >= 50)
        self.assertEqual(res['coordinates'][0], [start['lon'], start['lat']])
        self.assertEqual(res['coordinates'][-1], [finish['lon'], finish['lat']])
