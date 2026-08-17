import unittest
from unittest.mock import patch

from app import crop_recommendation_with_ai_and_ml


class CropAdvisorTests(unittest.TestCase):
    def test_combines_ml_ranking_with_ai_note(self):
        inputs = {
            "N": 60,
            "P": 40,
            "K": 35,
            "temperature": 24,
            "humidity": 70,
            "ph": 6.6,
            "rainfall": 180,
            "location": "Punjab",
        }
        ml_results = [
            {"crop": "Maize", "score": 91.2, "why": "Closest match", "profile": {}},
            {"crop": "Rice", "score": 88.5, "why": "Also suitable", "profile": {}},
        ]

        with patch("app.ml_models.get_crop_recommendation_ml", return_value=ml_results), patch(
            "app.crop_recommendations", return_value=ml_results
        ), patch(
            "app.ai_completion", return_value=("Prioritize maize for this field and watch water stress.", "Gemini")
        ):
            result = crop_recommendation_with_ai_and_ml(inputs)

        self.assertEqual(result["results"][0]["crop"], "Maize")
        self.assertEqual(result["location"], "Punjab")
        self.assertTrue(result["results"][0]["market_price"].startswith("₹"))
        self.assertEqual(result["ai_summary"], "Prioritize maize for this field and watch water stress.")
        self.assertEqual(result["ai_provider"], "Gemini")


if __name__ == "__main__":
    unittest.main()
