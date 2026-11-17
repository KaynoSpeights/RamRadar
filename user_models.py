
from contextlib import closing
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin


def create_user(database_path, username, email, password):
    """Create a user with a securely hashed password."""

    username = username.strip().lower()
    email = email.strip().lower()

    password_hash = generate_password_hash(
        password,
        method="scrypt"
    )

    with closing(sqlite3.connect(database_path)) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(users)")
        }
        if "name" in columns:
            cursor = connection.execute(
                """
                INSERT INTO users (username, name, email, password_hash)
                VALUES (?, ?, ?, ?)
                """,
                (username, username, email, password_hash)
            )
        else:
            cursor = connection.execute(
                """
                INSERT INTO users (username, email, password_hash)
                VALUES (?, ?, ?)
                """,
                (username, email, password_hash)
            )

        connection.commit()
        return cursor.lastrowid


def get_user_by_email(database_path, email):
    """Retrieve a registered user by email."""

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row

        user = connection.execute(
            "SELECT * FROM users WHERE email = ?",
            (email.strip().lower(),)
        ).fetchone()

        return dict(user) if user else None


def get_user_by_username(database_path, username):
    """Retrieve a registered user by username."""

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row

        user = connection.execute(
            "SELECT * FROM users WHERE username = ?",
            (username.strip().lower(),)
        ).fetchone()

        return dict(user) if user else None


def verify_password(password_hash, password):
    """Verify a password against its stored hash."""

    return check_password_hash(password_hash, password)


class User(UserMixin):
    """Represents an authenticated RamRadar user."""

    def __init__(self, user_data):
        self.id = str(user_data["id"])
        self.username = user_data["username"]
        self.email = user_data["email"]


def get_user_by_id(database_path, user_id):
    """Retrieve a user using their database ID."""

    try:
        user_id = int(user_id)
    except (ValueError, TypeError):
        return None

    with closing(sqlite3.connect(database_path)) as connection:
        connection.row_factory = sqlite3.Row

        user = connection.execute(
            "SELECT id, username, email FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

        return User(dict(user)) if user else None
