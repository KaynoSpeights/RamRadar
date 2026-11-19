import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf.csrf import CSRFProtect, generate_csrf

from database import init_db
from forms import LoginForm, RegistrationForm
from user_models import (
    User,
    create_user,
    get_user_by_id,
    get_user_by_username,
    verify_password,
)


app = Flask(__name__, instance_relative_config=True)
Path(app.instance_path).mkdir(parents=True, exist_ok=True)

secret_key_file = Path(app.instance_path) / "secret_key.txt"
secret_key = os.environ.get("SECRET_KEY") or os.environ.get("RAMRADAR_SECRET_KEY")
if not secret_key:
    if secret_key_file.exists():
        secret_key = secret_key_file.read_text().strip()
    else:
        secret_key = secrets.token_hex(32)
        secret_key_file.write_text(secret_key)
        secret_key_file.chmod(0o600)

app.config.update(
    SECRET_KEY=secret_key,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=(
        os.environ.get("COOKIE_SECURE", os.environ.get("RAMRADAR_SECURE_COOKIES", "false")).lower()
        == "true"
    ),
)
init_db(app)

csrf = CSRFProtect(app)
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://",
)
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

CATEGORIES = [
    "Campus Events",
    "Pickup Games",
    "Study Sessions",
    "Social Meetups",
    "Gaming Sessions",
    "Concerts & Off-Campus Activities",
    "Career",
]


@app.template_filter("event_date")
def event_date(value):
    return datetime.fromisoformat(value).strftime("%a, %b %-d · %-I:%M %p")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def initialize_db():
    db = get_db()
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            name TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS activities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT NOT NULL,
            starts_at TEXT NOT NULL,
            location TEXT NOT NULL,
            organizer_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
            organizer_name TEXT NOT NULL,
            is_demo INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS rsvps (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            PRIMARY KEY (user_id, activity_id)
        );
        CREATE TABLE IF NOT EXISTS saved_activities (
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            activity_id INTEGER NOT NULL REFERENCES activities(id) ON DELETE CASCADE,
            created_at TEXT NOT NULL,
            PRIMARY KEY (user_id, activity_id)
        );
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    user_columns = {
        row["name"]: row for row in db.execute("PRAGMA table_info(users)").fetchall()
    }
    if "name" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN name TEXT NOT NULL DEFAULT ''")
    user_columns = {
        row["name"]: row for row in db.execute("PRAGMA table_info(users)").fetchall()
    }
    if "username" not in user_columns:
        db.execute("ALTER TABLE users ADD COLUMN username TEXT")
        for user in db.execute("SELECT id, name FROM users").fetchall():
            candidate = (user["name"] or f"ram{user['id']}").strip().lower()
            candidate = "".join(char for char in candidate if char.isalnum() or char == "_") or f"ram{user['id']}"
            username = candidate
            suffix = 1
            while db.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
                username = f"{candidate}{suffix}"
                suffix += 1
            db.execute("UPDATE users SET username = ? WHERE id = ?", (username, user["id"]))
        db.execute("CREATE UNIQUE INDEX users_username_unique ON users(username)")
    db.execute("UPDATE users SET name = username WHERE name = ''")
    user_columns = {
        row["name"]: row for row in db.execute("PRAGMA table_info(users)").fetchall()
    }
    if "email" in user_columns:
        db.commit()
        db.execute("PRAGMA foreign_keys = OFF")
        db.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE users_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                name TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO users_new (id, username, password_hash, created_at, name)
                SELECT id, username, password_hash, created_at, name FROM users;
            DROP TABLE users;
            ALTER TABLE users_new RENAME TO users;
            COMMIT;
            """
        )
        db.execute("PRAGMA foreign_keys = ON")

    feedback_columns = {
        row["name"] for row in db.execute("PRAGMA table_info(feedback)").fetchall()
    }
    if "email" in feedback_columns:
        db.commit()
        db.executescript(
            """
            BEGIN IMMEDIATE;
            CREATE TABLE feedback_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            INSERT INTO feedback_new (id, name, subject, message, created_at)
                SELECT id, name, subject, message, created_at FROM feedback;
            DROP TABLE feedback;
            ALTER TABLE feedback_new RENAME TO feedback;
            COMMIT;
            """
        )

    existing = db.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
    if existing == 0:
        now = datetime.now().replace(second=0, microsecond=0)
        demos = [
            (
                "Ram Roundup",
                "Campus Events",
                "A sample campus gathering to meet new people, enjoy music, and make the most of a day on the quad. Demo listing includes a virtual hangout option.",
                (now + timedelta(days=3)).replace(hour=15).isoformat(timespec="minutes"),
                "University Quad",
                "RamRadar demo listing",
            ),
            (
                "Open Court: Pickup Basketball",
                "Pickup Games",
                "A friendly sample meetup for a few games, good energy, and meeting fellow Rams. All skill levels welcome.",
                (now + timedelta(days=1)).replace(hour=17).isoformat(timespec="minutes"),
                "Campus Recreation Center",
                "RamRadar demo listing",
            ),
            (
                "Library Study Break",
                "Study Sessions",
                "A sample study group for sharing notes, staying focused, and taking a well-earned break together.",
                (now + timedelta(days=2)).replace(hour=18).isoformat(timespec="minutes"),
                "C.G. O'Kelly Library",
                "RamRadar demo listing",
            ),
        ]
        db.executemany(
            """INSERT INTO activities
               (title, category, description, starts_at, location, organizer_name, is_demo, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
            [(*demo, now.isoformat(timespec="minutes")) for demo in demos],
        )
    db.execute(
        """UPDATE activities
           SET title = 'Ram Roundup'
           WHERE is_demo = 1 AND title = 'Ram Roundup on the Quad'"""
    )
    db.execute(
        """UPDATE activities
           SET location = 'Student Center'
           WHERE is_demo = 1 AND title = 'Ram Roundup' AND location = 'University Quad'"""
    )
    db.commit()


@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(app.config["DATABASE"], user_id)


@app.before_request
def prepare_request():
    initialize_db()


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.context_processor
def inject_globals():
    return {"csrf_token": generate_csrf()}


def current_user_id():
    return int(current_user.get_id()) if current_user.is_authenticated else None


def activity_rows(query="", category="", user_id=None, limit=None, when="", location=""):
    sql = """
        SELECT a.*,
               (SELECT COUNT(*) FROM rsvps r WHERE r.activity_id = a.id) AS attendee_count,
               EXISTS(SELECT 1 FROM rsvps r WHERE r.activity_id = a.id AND r.user_id = ?) AS is_attending,
               EXISTS(SELECT 1 FROM saved_activities s WHERE s.activity_id = a.id AND s.user_id = ?) AS is_saved
        FROM activities a
        WHERE (a.title LIKE ? OR a.description LIKE ? OR a.location LIKE ? OR a.category LIKE ?)
    """
    term = f"%{query.strip()}%"
    params = [user_id, user_id, term, term, term, term]
    if category:
        sql += " AND a.category = ?"
        params.append(category)
    if location:
        sql += " AND a.location LIKE ?"
        params.append(f"%{location.strip()}%")
    now = datetime.now()
    if when == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        sql += " AND a.starts_at >= ? AND a.starts_at < ?"
        params.extend([start.isoformat(timespec="minutes"), (start + timedelta(days=1)).isoformat(timespec="minutes")])
    elif when == "week":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        sql += " AND a.starts_at >= ? AND a.starts_at < ?"
        params.extend([start.isoformat(timespec="minutes"), (start + timedelta(days=7)).isoformat(timespec="minutes")])
    sql += " ORDER BY a.starts_at ASC"
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return get_db().execute(sql, params).fetchall()


def member_activities(table, user_id):
    if table not in {"rsvps", "saved_activities"}:
        raise ValueError("Unsupported activity relationship")
    return get_db().execute(
        f"""SELECT a.*,
                   (SELECT COUNT(*) FROM rsvps r WHERE r.activity_id = a.id) AS attendee_count,
                   EXISTS(SELECT 1 FROM rsvps r WHERE r.activity_id = a.id AND r.user_id = ?) AS is_attending,
                   EXISTS(SELECT 1 FROM saved_activities s WHERE s.activity_id = a.id AND s.user_id = ?) AS is_saved
            FROM activities a
            JOIN {table} member_activity ON member_activity.activity_id = a.id
            WHERE member_activity.user_id = ?
            ORDER BY a.starts_at ASC""",
        (user_id, user_id, user_id),
    ).fetchall()


def safe_local_path(value):
    parsed = urlsplit(value)
    return value.startswith("/") and not value.startswith("//") and not parsed.netloc and not parsed.scheme and "\\" not in value


@app.route("/")
def home():
    activities = activity_rows(user_id=current_user_id())
    return render_template("index.html", activities=activities, categories=CATEGORIES)


@app.route("/activities")
def explore_activities():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    when = request.args.get("when", "").strip()
    location = request.args.get("location", "").strip()
    if category and category not in CATEGORIES:
        category = ""
    if when not in {"today", "week"}:
        when = ""
    activities = activity_rows(query, category, current_user_id(), when=when, location=location)
    return render_template(
        "activities.html",
        activities=activities,
        categories=CATEGORIES,
        query=query,
        selected_category=category,
        selected_when=when,
        selected_location=location,
    )


@app.route("/activities/<int:activity_id>")
def activity_detail(activity_id):
    activity = activity_rows(user_id=current_user_id())
    selected = next((item for item in activity if item["id"] == activity_id), None)
    if selected is None:
        abort(404)
    return render_template("activity_detail.html", activity=selected)


@app.route("/activities/create", methods=["GET", "POST"])
@login_required
def create_activity():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        category = request.form.get("category", "").strip()
        description = request.form.get("description", "").strip()
        starts_at = request.form.get("starts_at", "").strip()
        location = request.form.get("location", "").strip()
        if not all((title, category, description, starts_at, location)):
            flash("Please complete every field.", "error")
        elif category not in CATEGORIES:
            flash("Choose a category from the list.", "error")
        else:
            try:
                date = datetime.fromisoformat(starts_at)
            except ValueError:
                flash("Enter a valid date and time.", "error")
            else:
                user = get_db().execute(
                    "SELECT name, username FROM users WHERE id = ?", (current_user_id(),)
                ).fetchone()
                organizer = user["name"] or user["username"]
                db = get_db()
                cursor = db.execute(
                    """INSERT INTO activities
                       (title, category, description, starts_at, location, organizer_id, organizer_name, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        title,
                        category,
                        description,
                        date.isoformat(timespec="minutes"),
                        location,
                        current_user_id(),
                        organizer,
                        datetime.now().isoformat(timespec="minutes"),
                    ),
                )
                db.commit()
                flash("Your activity is now listed.", "success")
                return redirect(url_for("activity_detail", activity_id=cursor.lastrowid))
    return render_template("create_activity.html", categories=CATEGORIES)


@app.route("/activities/<int:activity_id>/rsvp", methods=["POST"])
@login_required
def update_rsvp(activity_id):
    db = get_db()
    if db.execute("SELECT 1 FROM activities WHERE id = ?", (activity_id,)).fetchone() is None:
        abort(404)
    if request.form.get("action") == "leave":
        db.execute(
            "DELETE FROM rsvps WHERE user_id = ? AND activity_id = ?",
            (current_user_id(), activity_id),
        )
        flash("Your RSVP was removed.", "info")
    else:
        db.execute(
            "INSERT OR IGNORE INTO rsvps (user_id, activity_id, created_at) VALUES (?, ?, ?)",
            (current_user_id(), activity_id, datetime.now().isoformat(timespec="minutes")),
        )
        flash("You're on the list. See you there!", "success")
    db.commit()
    destination = request.form.get("next", "")
    return redirect(
        destination if safe_local_path(destination) else url_for("activity_detail", activity_id=activity_id)
    )


@app.route("/activities/<int:activity_id>/save", methods=["POST"])
@login_required
def toggle_saved(activity_id):
    db = get_db()
    if db.execute("SELECT 1 FROM activities WHERE id = ?", (activity_id,)).fetchone() is None:
        abort(404)
    saved = db.execute(
        "SELECT 1 FROM saved_activities WHERE user_id = ? AND activity_id = ?",
        (current_user_id(), activity_id),
    ).fetchone()
    if saved:
        db.execute(
            "DELETE FROM saved_activities WHERE user_id = ? AND activity_id = ?",
            (current_user_id(), activity_id),
        )
        flash("Removed from your saved activities.", "info")
    else:
        db.execute(
            "INSERT INTO saved_activities (user_id, activity_id, created_at) VALUES (?, ?, ?)",
            (current_user_id(), activity_id, datetime.now().isoformat(timespec="minutes")),
        )
        flash("Activity saved for later.", "success")
    db.commit()
    destination = request.form.get("next", "")
    return redirect(
        destination if safe_local_path(destination) else url_for("activity_detail", activity_id=activity_id)
    )


@app.route("/saved")
@login_required
def saved_activities():
    activities = member_activities("saved_activities", current_user_id())
    return render_template(
        "activities.html",
        activities=activities,
        categories=CATEGORIES,
        query="",
        selected_category="",
        page_title="Saved activities",
    )


@app.route("/community")
@login_required
def community():
    user_id = current_user_id()
    return render_template(
        "community.html",
        attending=member_activities("rsvps", user_id),
        saved=member_activities("saved_activities", user_id),
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data.strip().lower()
        if get_user_by_username(app.config["DATABASE"], username):
            form.username.errors.append("This username is already taken.")
        if not form.username.errors:
            try:
                user_id = create_user(app.config["DATABASE"], username, form.password.data)
                db = get_db()
                db.execute("UPDATE users SET name = ? WHERE id = ?", (username, user_id))
                db.commit()
                flash("Account created successfully! You can now log in.", "success")
                return redirect(url_for("register"))
            except sqlite3.IntegrityError:
                form.username.errors.append("This username is already taken.")
    return render_template("auth.html", mode="register", form=form)


@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip().lower()
        user_data = get_user_by_username(app.config["DATABASE"], username)
        if user_data and verify_password(user_data["password_hash"], form.password.data):
            login_user(User(user_data))
            flash("You have successfully logged in!", "success")
            destination = request.args.get("next", "")
            return redirect(destination if safe_local_path(destination) else url_for("home"))
        flash("Invalid username or password.", "error")
    return render_template("auth.html", mode="login", form=form)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have successfully logged out.", "success")
    return redirect(url_for("home"))


@app.route("/feedback", methods=["POST"])
def submit_feedback():
    name = request.form.get("name", "").strip()
    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()
    allowed_subjects = {"Suggestion", "Question", "Report a problem", "Other"}
    if not name or subject not in allowed_subjects or not message:
        flash("Please complete the feedback form with a valid subject.", "error")
    else:
        get_db().execute(
            "INSERT INTO feedback (name, subject, message, created_at) VALUES (?, ?, ?, ?)",
            (name, subject, message, datetime.now().isoformat(timespec="minutes")),
        )
        get_db().commit()
        flash("Thanks for helping make campus connections better.", "success")
    return redirect(url_for("home", _anchor="contact"))


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode)
