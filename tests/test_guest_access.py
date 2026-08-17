import os
import unittest
from unittest.mock import patch

from app import app, connect_db, init_db


class GuestAccessTests(unittest.TestCase):
    def setUp(self):
        init_db()
        with connect_db() as conn:
            conn.execute("DELETE FROM predictions")
            conn.execute("DELETE FROM chat_messages")
            conn.execute("DELETE FROM users")
            conn.commit()
        self.client = app.test_client()
        app.config.update(TESTING=True)

    def test_guest_cannot_submit_prediction_without_login(self):
        response = self.client.post(
            "/predict",
            data={
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
            },
            follow_redirects=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_guest_cannot_open_chat_page_without_login(self):
        response = self.client.get("/chat", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_guest_cannot_open_yield_planner_without_login(self):
        response = self.client.get("/yield-planner", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_database_file_is_persisted_in_project_root(self):
        self.assertTrue(os.path.exists("fertilizer.db"))
        self.assertTrue(os.path.isabs(os.path.abspath("fertilizer.db")))


if __name__ == "__main__":
    unittest.main()
