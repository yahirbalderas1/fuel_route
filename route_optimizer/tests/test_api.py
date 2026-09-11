import json
from django.test import TestCase, Client
from django.urls import reverse


class ApiRouteTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_api_route_get_valid(self):
        url = reverse('api_route_plan')
        response = self.client.get(url, {'start': 'Austin, TX', 'finish': 'Dallas, TX'})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertIn('summary', data)
        self.assertIn('total_distance_miles', data['summary'])
        self.assertIn('total_fuel_cost_dollars', data['summary'])
        self.assertIn('fuel_stops', data)
        self.assertIn('route_geometry', data)
        self.assertEqual(data['route_geometry']['type'], 'LineString')

    def test_api_route_post_json(self):
        url = reverse('api_route_plan')
        payload = {
            'start': 'Philadelphia, PA',
            'finish': 'Boston, MA'
        }
        response = self.client.post(
            url,
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'success')
        self.assertTrue(data['summary']['total_distance_miles'] > 200)

    def test_api_route_missing_params(self):
        url = reverse('api_route_plan')
        response = self.client.get(url, {'start': 'Austin, TX'})
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['status'], 'error')
        self.assertIn('Missing required parameters', data['message'])

    def test_api_route_outside_usa(self):
        url = reverse('api_route_plan')
        # Coordinates in London, UK
        response = self.client.get(url, {'start': 'Austin, TX', 'finish': '51.5074, -0.1278'})
        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertEqual(data['status'], 'error')

    def test_map_view_home(self):
        url = reverse('home_map')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fuel Route Optimizer")
        self.assertContains(response, "map")

    def test_map_view_with_route(self):
        url = reverse('map_view')
        response = self.client.get(url, {'start': 'Austin, TX', 'finish': 'Dallas, TX'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Fuel Route Optimizer")
