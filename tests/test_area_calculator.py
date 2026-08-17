import unittest
from unittest.mock import patch

from app import app, calculate_area_from_location, calculate_polygon_area_sq_m


class AreaCalculatorTests(unittest.TestCase):
    @patch("app.requests.get")
    def test_calculate_area_from_geocoded_location(self, mock_get):
        mock_get.return_value.json.return_value = {
            "status": "OK",
            "results": [
                {
                    "formatted_address": "New York, NY, USA",
                    "geometry": {"location": {"lat": 40.7128, "lng": -74.0060}},
                }
            ],
        }
        mock_get.return_value.raise_for_status.return_value = None

        result = calculate_area_from_location("New York", radius_m=1000)

        self.assertEqual(result["location"], "New York")
        self.assertEqual(result["address"], "New York, NY, USA")
        self.assertAlmostEqual(result["area_sq_m"], 3_141_592.65, places=2)
        self.assertAlmostEqual(result["area_ha"], 314.16, places=2)
        self.assertAlmostEqual(result["area_acres"], 776.30, places=2)

    @patch("app.requests.get")
    def test_geocode_location_endpoint_returns_coordinates(self, mock_get):
        mock_get.return_value.json.return_value = {
            "status": "OK",
            "results": [
                {
                    "formatted_address": "1600 Amphitheatre Parkway, Mountain View, CA",
                    "geometry": {"location": {"lat": 37.4220, "lng": -122.0841}},
                }
            ],
        }
        mock_get.return_value.raise_for_status.return_value = None

        client = app.test_client()
        response = client.get("/geocode?q=1600+Amphitheatre+Parkway")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["success"], True)
        self.assertEqual(response.json["lat"], 37.4220)
        self.assertEqual(response.json["lng"], -122.0841)
        self.assertIn("1600 Amphitheatre Parkway", response.json["address"])

    def test_polygon_area_uses_geodesic_calculation(self):
        square = [(0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0), (0.0, 0.0)]

        area = calculate_polygon_area_sq_m(square)

        self.assertAlmostEqual(area, 12_364_000_000, delta=250_000_000)


if __name__ == "__main__":
    unittest.main()
