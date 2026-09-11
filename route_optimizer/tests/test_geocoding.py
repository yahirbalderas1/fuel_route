from django.test import TestCase
from route_optimizer.services.geocoding import (
    parse_coordinates,
    lookup_local_city,
    is_in_usa,
    geocode_location
)


class GeocodingServiceTests(TestCase):
    def test_parse_coordinates_valid(self):
        res = parse_coordinates("40.7128, -74.0060")
        self.assertIsNotNone(res)
        self.assertAlmostEqual(res['lat'], 40.7128, places=4)
        self.assertAlmostEqual(res['lon'], -74.0060, places=4)
        self.assertEqual(res['source'], 'coordinates')

    def test_parse_coordinates_outside_usa(self):
        # Paris, France
        with self.assertRaises(ValueError):
            parse_coordinates("48.8566, 2.3522")

    def test_is_in_usa(self):
        # NYC
        self.assertTrue(is_in_usa(40.7128, -74.0060))
        # LA
        self.assertTrue(is_in_usa(34.0522, -118.2437))
        # Anchorage, Alaska
        self.assertTrue(is_in_usa(61.2181, -149.9003))
        # Honolulu, Hawaii
        self.assertTrue(is_in_usa(21.3069, -157.8583))
        # London, UK (False)
        self.assertFalse(is_in_usa(51.5074, -0.1278))

    def test_lookup_local_city(self):
        res = lookup_local_city("Austin, TX")
        self.assertIsNotNone(res)
        self.assertAlmostEqual(res['lat'], 30.5, delta=1.0)
        self.assertAlmostEqual(res['lon'], -97.7, delta=1.0)

    def test_lookup_local_city_full_state(self):
        res = lookup_local_city("Dallas, Texas")
        self.assertIsNotNone(res)
        self.assertAlmostEqual(res['lat'], 32.8, delta=1.0)
        self.assertAlmostEqual(res['lon'], -96.8, delta=1.0)

    def test_geocode_location_empty(self):
        with self.assertRaises(ValueError):
            geocode_location("")
        with self.assertRaises(ValueError):
            geocode_location("   ")
