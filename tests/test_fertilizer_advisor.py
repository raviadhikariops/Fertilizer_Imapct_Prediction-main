import unittest
from unittest.mock import patch

from app import fertilizer_recommendation_with_ai_and_ml, fertilizer_recommendation_with_ml


class FertilizerAdvisorTests(unittest.TestCase):
    def test_includes_random_forest_and_decision_tree_predictions(self):
        inputs = {
            "temperature": 25,
            "humidity": 55,
            "moisture": 45,
            "N": 35,
            "P": 28,
            "K": 20,
            "soil": "Loamy",
            "crop": "Maize",
        }
        model_predictions = {
            "baseline": "Urea",
            "random_forest": "Urea",
            "decision_tree": "DAP",
            "ensemble": "Urea",
        }

        with patch("app.ml_models.get_fertilizer_recommendation_models", return_value=model_predictions):
            result = fertilizer_recommendation_with_ml(inputs)

        self.assertEqual(result["fertilizer"], "Urea")
        self.assertEqual(result["model_predictions"]["random_forest"], "Urea")
        self.assertEqual(result["model_predictions"]["decision_tree"], "DAP")

    def test_combines_ai_and_ml_recommendations(self):
        inputs = {
            "temperature": 25,
            "humidity": 55,
            "moisture": 45,
            "N": 35,
            "P": 28,
            "K": 20,
            "soil": "Loamy",
            "crop": "Maize",
        }
        ml_plan = {
            "fertilizer": "Urea",
            "confidence": 82.0,
            "focus": "nitrogen correction",
            "timing": "Split across the vegetative phase",
            "nutrient_gaps": {"Nitrogen": 10.0, "Phosphorus": 2.0, "Potassium": 4.0},
            "summary": "Urea recommended by the ML model.",
        }

        with patch("app.fertilizer_recommendation_with_ml", return_value=ml_plan), patch(
            "app.ai_completion", return_value=("Use split nitrogen applications and monitor leaf color.", "Groq")
        ):
            result = fertilizer_recommendation_with_ai_and_ml(inputs)

        self.assertEqual(result["fertilizer"], "Urea")
        self.assertEqual(result["advisor_summary"], "Urea is recommended with nitrogen correction and timing of Split across the vegetative phase.")
        self.assertEqual(result["ml_summary"], ml_plan["summary"])
        self.assertEqual(result["ai_summary"], "Use split nitrogen applications and monitor leaf color.")
        self.assertEqual(result["ai_provider"], "Groq")


if __name__ == "__main__":
    unittest.main()
