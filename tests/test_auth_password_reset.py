import unittest
from unittest.mock import patch

from werkzeug.security import generate_password_hash

from app import app, connect_db, init_db, store_prediction


class PasswordResetFlowTests(unittest.TestCase):
    def setUp(self):
        init_db()
        with connect_db() as conn:
            conn.execute("DELETE FROM password_reset_otps")
            conn.execute("DELETE FROM users")
            conn.execute(
                "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                ("Test Farmer", "farmer@example.com", generate_password_hash("secret123"), "2024-01-01T00:00:00"),
            )
            conn.commit()
        self.client = app.test_client()
        app.config.update(TESTING=True)

    def test_root_redirects_to_login_for_unauthenticated_users(self):
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].startswith("/login?next=/"))

    def test_authenticated_user_can_view_planner(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 1

        response = self.client.get("/", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Plan your next harvest", response.data)

    def test_about_page_is_public_for_unauthenticated_users(self):
        response = self.client.get("/about", follow_redirects=False)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"About", response.data)

    def test_protected_pages_redirect_to_login_for_unauthenticated_users(self):
        response = self.client.get("/crop-recommendation", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].startswith("/login?next=/crop-recommendation"))

    def test_history_page_shows_advisor_and_disease_entries(self):
        with connect_db() as conn:
            user = conn.execute("SELECT id FROM users WHERE email = ?", ("farmer@example.com",)).fetchone()
            user_id = user["id"]

        store_prediction(
            {
                "soil": "Loamy",
                "weather": "Sunny",
                "fertilizer": "Urea",
                "amount": 80.0,
                "crop": "Wheat",
                "location": "Punjab",
                "N": 60.0,
                "P": 40.0,
                "K": 30.0,
                "ph": 6.5,
                "temperature": 24.0,
                "humidity": 65.0,
                "rainfall": 120.0,
                "moisture": 45.0,
            },
            {"yield_range": "4.2 - 5.1 t/ha", "risk_level": "Low", "confidence": 88.0},
            {"fertilizer": "Urea"},
            [{"crop": "Wheat", "score": 0.92}],
            "Crop advisor summary",
            user_id,
            prediction_type="crop",
            description="Crop advisor recommendation",
            predicted_yield="Top match: Wheat",
            risk_level="Low",
            confidence=88.0,
        )

        store_prediction(
            {
                "soil": "Loamy",
                "weather": "Sunny",
                "fertilizer": "Urea",
                "amount": 80.0,
                "crop": "Tomato",
                "location": "Punjab",
                "N": 60.0,
                "P": 40.0,
                "K": 30.0,
                "ph": 6.5,
                "temperature": 24.0,
                "humidity": 65.0,
                "rainfall": 120.0,
                "moisture": 45.0,
            },
            {"yield_range": "4.2 - 5.1 t/ha", "risk_level": "Medium", "confidence": 77.0},
            {"fertilizer": "Organic"},
            [{"crop": "Tomato", "score": 0.85}],
            "Disease detection summary",
            user_id,
            prediction_type="disease",
            description="Disease detection result",
            predicted_yield="Leaf spot detected",
            risk_level="Medium",
            confidence=77.0,
        )

        with self.client.session_transaction() as session:
            session["user_id"] = user_id

        response = self.client.get("/all_responses")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Crop Advisor", response.data)
        self.assertIn(b"Disease Detection", response.data)

    @patch("app.ai_enrichment", side_effect=AssertionError("AI enrichment should not run for the fast planner path"))
    def test_predict_uses_local_plan_without_ai_enrichment(self, mock_ai_enrichment):
        with self.client.session_transaction() as session:
            session["user_id"] = 1

        response = self.client.post(
            "/predict",
            data={
                "crop": "Maize",
                "soil": "Loamy",
                "fertilizer": "Urea",
                "amount": "80",
                "weather": "Sunny",
                "location": "Punjab",
                "nitrogen": "120",
                "phosphorus": "40",
                "potassium": "30",
                "ph": "6.5",
                "temperature": "28",
                "humidity": "65",
                "rainfall": "100",
                "moisture": "45",
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.headers["Location"].startswith("/prediction/"))
        mock_ai_enrichment.assert_not_called()

    @patch("app.send_password_reset_email")
    def test_forgot_password_generates_otp_and_allows_reset(self, mock_send_email):
        response = self.client.post(
            "/forgot_password",
            data={"email": "farmer@example.com"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"OTP", response.data)
        mock_send_email.assert_called_once()

        with connect_db() as conn:
            row = conn.execute(
                "SELECT otp_hash, email FROM password_reset_otps WHERE email = ?",
                ("farmer@example.com",),
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row["email"], "farmer@example.com")

        otp = response.get_data(as_text=True)
        self.assertIn("OTP sent to your email", otp)

        # Extract the OTP code from the rendered page for the test.
        import re

        match = re.search(r"OTP: (\d{6})", otp)
        self.assertIsNotNone(match)
        otp_code = match.group(1)

        reset_response = self.client.post(
            "/reset_password",
            data={
                "email": "farmer@example.com",
                "otp": otp_code,
                "new_password": "newpass123",
            },
            follow_redirects=True,
        )
        self.assertEqual(reset_response.status_code, 200)
        self.assertIn(b"Password updated", reset_response.data)


if __name__ == "__main__":
    unittest.main()
