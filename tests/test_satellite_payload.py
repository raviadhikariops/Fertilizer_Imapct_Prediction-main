import unittest

from app import build_api_inputs


class SatellitePayloadTests(unittest.TestCase):
    def test_build_api_inputs_accepts_satellite_object(self):
        data = {
            "crop": "Rice",
            "soil": "Loamy",
            "fertilizer": "Organic",
            "amount": "90",
            "weather": "Sunny",
            "location": "Chitwan",
            "nitrogen": "50",
            "phosphorus": "35",
            "potassium": "25",
            "ph": "6.8",
            "temperature": "28",
            "humidity": "70",
            "rainfall": "100",
            "moisture": "40",
            "satellite_data": {
                "ndvi": "0.62",
                "evi": "0.38",
                "surface_temp": "27.5",
                "precipitation": "1.2",
            },
        }

        inputs = build_api_inputs(data)

        self.assertEqual(inputs["satellite_ndvi"], 0.62)
        self.assertEqual(inputs["satellite_evi"], 0.38)
        self.assertEqual(inputs["satellite_surface_temp"], 27.5)
        self.assertEqual(inputs["satellite_precipitation"], 1.2)


if __name__ == "__main__":
    unittest.main()
