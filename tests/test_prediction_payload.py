import unittest
from unittest.mock import patch

from app import local_yield_plan, prediction_payload


class PredictionPayloadTests(unittest.TestCase):
    def test_prediction_payload_preserves_location_and_reports_market_price(self):
        inputs = prediction_payload(
            {
                "crop": "Wheat",
                "soil": "Loamy",
                "weather": "Sunny",
                "fertilizer": "Urea",
                "amount": "80",
                "nitrogen": "60",
                "phosphorus": "40",
                "potassium": "30",
                "ph": "6.5",
                "temperature": "24",
                "humidity": "65",
                "rainfall": "120",
                "moisture": "45",
                "location": "Punjab",
            }
        )

        self.assertEqual(inputs["location"], "Punjab")

        plan = local_yield_plan(inputs)

        self.assertIn("market_price", plan)
        self.assertIn("₹", plan["market_price"])

    def test_prediction_payload_uses_live_weather_when_fields_are_empty(self):
        class FakeResponse:
            def __init__(self, payload):
                self._payload = payload

            def raise_for_status(self):
                return None

            def json(self):
                return self._payload

        with patch("app.requests.get") as mock_get:
            mock_get.side_effect = [
                FakeResponse([
                    {"name": "Kathmandu", "lat": 27.7, "lon": 85.3, "state": "Bagmati"}
                ]),
                FakeResponse({
                    "main": {"temp": 28.4, "humidity": 73},
                    "weather": [{"main": "Clouds"}],
                    "rain": {"1h": 0.5},
                }),
            ]
            inputs = prediction_payload(
                {
                    "crop": "Wheat",
                    "soil": "Loamy",
                    "weather": "",
                    "fertilizer": "Urea",
                    "amount": "80",
                    "nitrogen": "60",
                    "phosphorus": "40",
                    "potassium": "30",
                    "ph": "6.5",
                    "temperature": "",
                    "humidity": "",
                    "rainfall": "",
                    "moisture": "45",
                    "location": "Kathmandu",
                }
            )

        self.assertEqual(inputs["weather"], "Clouds")
        self.assertEqual(inputs["temperature"], 28.4)
        self.assertEqual(inputs["humidity"], 73)
        self.assertEqual(inputs["rainfall"], 0.5)


if __name__ == "__main__":
    unittest.main()
