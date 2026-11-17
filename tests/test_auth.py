
import os
import sqlite3
import sys
import tempfile
import unittest
from html.parser import HTMLParser

# Allow tests to import the project from the root folder.
sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
)

from app import app, limiter
from user_models import (
    create_user,
    get_user_by_email,
    verify_password,
)


class CSRFParser(HTMLParser):
    """Extract a CSRF token from an HTML form."""

    def __init__(self):
        super().__init__()
        self.token = None

    def handle_starttag(self, tag, attrs):
        if tag == "input":
            attributes = dict(attrs)
            if attributes.get("name") == "csrf_token":
                self.token = attributes.get("value")


class AuthenticationTests(unittest.TestCase):

    def setUp(self):
        # Save original application settings.
        self.original_config = app.config.copy()

        # Create a disposable database for each test.
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database = os.path.join(
            self.temp_dir.name, "test_ramradar.db"
        )

        with sqlite3.connect(self.database) as connection:
            connection.execute("""
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

        app.config.update(
            TESTING=True,
            DATABASE=self.database,
            WTF_CSRF_ENABLED=True,
            SESSION_COOKIE_SECURE=False
        )

        self.client = app.test_client()
        limiter.reset()

    def tearDown(self):
        app.config.update(self.original_config)

        # Close any remaining SQLite connections before cleanup.
        import gc
        gc.collect()

        self.temp_dir.cleanup()

    def csrf_token(self, page):
        response = self.client.get(page)
        self.assertEqual(response.status_code, 200)

        parser = CSRFParser()
        parser.feed(response.get_data(as_text=True))

        self.assertIsNotNone(parser.token)
        return parser.token

    def create_test_account(self):
        create_user(
            self.database,
            "teststudent",
            "student@example.com",
            "SecurePassword2026!"
        )

    def test_homepage(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_registration_page(self):
        response = self.client.get("/register")
        self.assertEqual(response.status_code, 200)

    def test_login_page(self):
        response = self.client.get("/login")
        self.assertEqual(response.status_code, 200)

    def test_registration_requires_csrf(self):
        response = self.client.post("/register", data={
            "username": "teststudent",
            "email": "student@example.com",
            "password": "SecurePassword2026!",
            "confirm_password": "SecurePassword2026!"
        })
        self.assertEqual(response.status_code, 400)

    def test_login_requires_csrf(self):
        response = self.client.post("/login", data={
            "email": "student@example.com",
            "password": "SecurePassword2026!"
        })
        self.assertEqual(response.status_code, 400)

    def test_logout_rejects_get(self):
        response = self.client.get("/logout")
        self.assertEqual(response.status_code, 405)

    def test_registration_and_password_hashing(self):
        token = self.csrf_token("/register")

        response = self.client.post("/register", data={
            "username": "teststudent",
            "email": "student@example.com",
            "password": "SecurePassword2026!",
            "confirm_password": "SecurePassword2026!",
            "csrf_token": token
        })

        self.assertEqual(response.status_code, 302)

        user = get_user_by_email(
            self.database, "student@example.com"
        )

        self.assertIsNotNone(user)
        self.assertNotEqual(
            user["password_hash"], "SecurePassword2026!"
        )
        self.assertTrue(
            user["password_hash"].startswith("scrypt:")
        )
        self.assertTrue(
            verify_password(
                user["password_hash"], "SecurePassword2026!"
            )
        )

    def test_duplicate_registration(self):
        self.create_test_account()

        token = self.csrf_token("/register")
        response = self.client.post("/register", data={
            "username": "teststudent",
            "email": "student@example.com",
            "password": "SecurePassword2026!",
            "confirm_password": "SecurePassword2026!",
            "csrf_token": token
        })

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"already taken", response.data)

        with sqlite3.connect(self.database) as connection:
            count = connection.execute(
                "SELECT COUNT(*) FROM users"
            ).fetchone()[0]

        self.assertEqual(count, 1)

    def test_invalid_password(self):
        self.create_test_account()

        token = self.csrf_token("/login")
        response = self.client.post("/login", data={
            "email": "student@example.com",
            "password": "WrongPassword123!",
            "csrf_token": token
        }, follow_redirects=True)

        self.assertIn(
            b"Invalid email or password", response.data
        )

        with self.client.session_transaction() as session:
            self.assertNotIn("_user_id", session)

    def test_successful_login_and_logout(self):
        self.create_test_account()

        token = self.csrf_token("/login")
        response = self.client.post("/login", data={
            "email": "student@example.com",
            "password": "SecurePassword2026!",
            "csrf_token": token
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome, teststudent", response.data)

        # Ensure logout requires a CSRF token.
        response = self.client.post("/logout")
        self.assertEqual(response.status_code, 400)

        # A valid token should permit logout.
        token = self.csrf_token("/")
        response = self.client.post("/logout", data={
            "csrf_token": token
        }, follow_redirects=True)

        self.assertEqual(response.status_code, 200)

        with self.client.session_transaction() as session:
            self.assertNotIn("_user_id", session)


    def test_login_rate_limiting(self):
        """Block excessive login attempts from one IP."""
        limiter.reset()

        token = self.csrf_token("/login")
        responses = []

        for attempt in range(6):
            response = self.client.post(
                "/login",
                data={
                    "email": "rate.test@example.com",
                    "password": "WrongPassword123!",
                    "csrf_token": token
                },
                environ_overrides={
                    "REMOTE_ADDR": "192.0.2.50"
                }
            )
            responses.append(response.status_code)

        self.assertEqual(
            responses,
            [200, 200, 200, 200, 200, 429]
        )



if __name__ == "__main__":
    unittest.main()
