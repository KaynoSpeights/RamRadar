import re
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import app as ramradar


class RamRadarAppTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        ramradar.app.config.update(
            TESTING=True,
            SECRET_KEY="test-secret",
            DATABASE=str(Path(self.temp_dir.name) / "ramradar-test.sqlite3"),
        )
        self.client = ramradar.app.test_client()

    def tearDown(self):
        self.client = None
        self.temp_dir.cleanup()

    def token(self, path="/"):
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        match = re.search(rb'name="csrf_token"[^>]*value="([^"]+)"', response.data)
        self.assertIsNotNone(match)
        return match.group(1).decode()

    def register(self):
        token = self.token("/register")
        response = self.client.post(
            "/register",
            data={
                "csrf_token": token,
                "username": "testram",
                "password": "safe-password-1234",
                "confirm_password": "safe-password-1234",
            },
        )
        self.assertEqual(response.status_code, 302)
        token = self.token("/login")
        response = self.client.post(
            "/login",
            data={
                "csrf_token": token,
                "username": "testram",
                "password": "safe-password-1234",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_home_and_demo_activities_render(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Find your people.", response.data)
        self.assertIn(b"Demo listing", response.data)
        self.assertEqual(response.data.count(b'class="activity-card"'), 3)
        self.assertIn(b"Ram Roundup", response.data)
        self.assertNotIn(b"Ram Roundup on the Quad", response.data)
        self.assertIn(b"Student Center", response.data)
        self.assertNotIn(b"University Quad", response.data)
        self.assertIn(b'<svg class="arrow-up-right"', response.data)
        self.assertNotIn("↗".encode(), response.data)
        self.assertIn(b'class="play-glyph">', response.data)
        self.assertIn(b'class="tile-icon mobile-star-symbol">', response.data)
        self.assertIn(b'class="community-spark spark-one mobile-star-symbol"', response.data)
        self.assertIn(b'class="cta-decoration cta-decoration-one mobile-star-symbol"', response.data)
        pickup_card = re.search(
            rb'<article class="activity-card" data-category="Pickup Games">(.*?)</article>',
            response.data,
            re.DOTALL,
        )
        self.assertIsNotNone(pickup_card)
        self.assertIn("✳".encode(), pickup_card.group(1))
        self.assertNotIn(b'<svg class="arrow-up-right"', pickup_card.group(1))
        for category in ramradar.CATEGORIES:
            with self.subTest(category=category):
                response = self.client.get(
                    "/activities",
                    query_string={"category": category},
                )
                self.assertEqual(response.status_code, 200)
                self.assertIn(b'<svg class="arrow-up-right"', response.data)

    def test_registration_activity_creation_rsvp_save_and_filters(self):
        self.register()
        response = self.client.get("/")
        self.assertIn(b"Welcome, testram", response.data)
        self.assertIn(b'href="/activities/create">Create activity</a>', response.data)
        self.assertIn(b'href="/saved">Saved activities</a>', response.data)
        self.assertIn(b">Sign out</button>", response.data)
        self.assertNotIn("↗".encode(), response.data)
        self.assertIn(b'class="arrow-up-right"', response.data)

        token = self.token("/activities/create")
        starts_at = (datetime.now() + timedelta(days=2)).replace(second=0, microsecond=0)
        response = self.client.post(
            "/activities/create",
            data={
                "csrf_token": token,
                "title": "Test meetup",
                "category": "Social Meetups",
                "description": "A student-created test listing.",
                "starts_at": starts_at.isoformat(timespec="minutes"),
                "location": "Student Center",
            },
        )
        self.assertEqual(response.status_code, 302)
        activity_id = int(response.location.rsplit("/", 1)[1])
        self.assertEqual(self.client.get(f"/activities/{activity_id}").status_code, 200)

        response = self.client.post(
            f"/activities/{activity_id}/rsvp",
            data={"csrf_token": token, "action": "join"},
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            f"/activities/{activity_id}/save",
            data={"csrf_token": token, "next": "https://example.com"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.location.startswith("/activities/"))
        self.assertIn(b"Test meetup", self.client.get("/saved").data)
        self.assertIn(b"Test meetup", self.client.get("/community").data)
        self.assertIn(
            b"Test meetup",
            self.client.get("/activities?category=Social+Meetups&location=Student+Center").data,
        )
        self.assertIn(b"Test meetup", self.client.get("/activities?when=week").data)

        career_token = self.token("/activities/create")
        career_starts_at = (datetime.now() + timedelta(days=4)).replace(second=0, microsecond=0)
        response = self.client.post(
            "/activities/create",
            data={
                "csrf_token": career_token,
                "title": "Career networking workshop",
                "category": "Career",
                "description": "A student-created career opportunity.",
                "starts_at": career_starts_at.isoformat(timespec="minutes"),
                "location": "Career Center",
            },
        )
        self.assertEqual(response.status_code, 302)
        home = self.client.get("/")
        self.assertIn(b"Career networking workshop", home.data)
        self.assertIn(b'data-category="Career"', home.data)
        self.assertIn(
            b"Career networking workshop",
            self.client.get("/activities").data,
        )
        self.assertIn(
            b"Career networking workshop",
            self.client.get("/activities?category=Career").data,
        )

    def test_feedback_privacy_and_csrf_validation(self):
        token = self.token("/")
        self.assertNotIn(b'name="email"', self.client.get("/").data)
        response = self.client.post(
            "/feedback",
            data={
                "csrf_token": token,
                "name": "Test Ram",
                "subject": "Suggestion",
                "message": "A test suggestion",
            },
        )
        self.assertEqual(response.status_code, 302)
        with sqlite3.connect(ramradar.app.config["DATABASE"]) as connection:
            feedback_columns = {
                row[1] for row in connection.execute("PRAGMA table_info(feedback)")
            }
            feedback = connection.execute(
                "SELECT name, subject, message FROM feedback"
            ).fetchone()
        self.assertNotIn("email", feedback_columns)
        self.assertEqual(feedback, ("Test Ram", "Suggestion", "A test suggestion"))
        self.assertEqual(self.client.get("/privacy").status_code, 200)
        self.assertEqual(
            self.client.post(
                "/feedback",
                data={"name": "Test", "subject": "Other", "message": "No token"},
            ).status_code,
            400,
        )

    def test_sign_in_and_unknown_activity(self):
        self.register()
        token = self.token("/")
        self.client.post("/logout", data={"csrf_token": token})
        token = self.token("/login?next=https://example.com")
        response = self.client.post(
            "/login?next=https://example.com",
            data={"csrf_token": token, "username": "TESTRAM", "password": "safe-password-1234"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/")
        self.assertEqual(self.client.get("/activities/999999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
