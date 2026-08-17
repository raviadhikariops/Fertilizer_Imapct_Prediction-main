import os
import unittest

from backend.ml_models import CROP_DISEASE_LIST, get_disease_details


class CropDiseaseTreatmentTests(unittest.TestCase):
    def test_returns_treatment_for_detected_disease(self):
        details = get_disease_details("apple", 0)
        self.assertEqual(details["disease"], "Apple scab")
        self.assertIsInstance(details["treatment"], list)
        self.assertTrue(any("fungicide" in step.lower() for step in details["treatment"]))
        self.assertTrue(details["fertilizer"])

    def test_returns_health_message_for_healthy_prediction(self):
        details = get_disease_details("apple", 3)
        self.assertEqual(details["disease"], "Healthy")
        self.assertIsInstance(details["treatment"], list)
        self.assertTrue(any("no treatment" in step.lower() or "keep monitoring" in step.lower() for step in details["treatment"]))
        self.assertTrue(details["fertilizer"])

    def test_supported_disease_crops_match_available_models(self):
        model_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "DL_models"))
        expected = []
        for filename in os.listdir(model_dir):
            if filename.endswith("_model.h5"):
                expected.append(filename[: -len("_model.h5")])
        self.assertEqual(sorted(CROP_DISEASE_LIST), sorted(expected))


if __name__ == "__main__":
    unittest.main()
