import os
import sqlite3
from contextlib import closing


def init_db(app):
    os.makedirs(app.instance_path, exist_ok=True)

    database_path = os.path.join(app.instance_path, "ramradar.db")

    with closing(sqlite3.connect(database_path)) as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        connection.commit()

    app.config["DATABASE"] = database_path
