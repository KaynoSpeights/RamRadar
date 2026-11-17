import os
import secrets
import sqlite3
from datetime import datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    abort,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash


app = Flask(__name__, instance_relative_config=True)
app.config.update(
    SECRET_KEY=os.environ.get("RAMRADAR_SECRET_KEY") or secrets.token_hex(32),
    DATABASE=os.path.join(app.instance_path, "ramradar.sqlite3"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("RAMRADAR_SECURE_COOKIES", "").lower() == "true",
)
Path(app.instance_path).mkdir(parents=True, exist_ok=True)

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
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
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
            email TEXT NOT NULL,
            subject TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )
    existing = db.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
    if existing == 0:
        now = datetime.now().replace(second=0, microsecond=0)
        demos = [
            (
                "Ram Roundup on the Quad",
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
    db.commit()


@app.before_request
def prepare_request():
    initialize_db()
    if request.method == "POST":
        submitted = request.form.get("csrf_token", "")
        expected = session.get("_csrf_token", "")
        if not expected or not secrets.compare_digest(submitted, expected):
            abort(400, description="The form expired. Please reload the page and try again.")


@app.teardown_appcontext
def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


@app.context_processor
def inject_globals():
    user = None
    user_id = session.get("user_id")
    if user_id:
        user = get_db().execute(
            "SELECT id, name, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if user is None:
            session.pop("user_id", None)
    if "_csrf_token" not in session:
        session["_csrf_token"] = secrets.token_urlsafe(32)
    return {"current_user": user, "csrf_token": session["_csrf_token"]}


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Sign in to continue.", "info")
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


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
        sql += " AND a.starts_at >= ? AND a.starts_at < ?"
        params.extend(
            [now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(timespec="minutes"),
             (now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).isoformat(timespec="minutes")]
        )
    elif when == "week":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)
        sql += " AND a.starts_at >= ? AND a.starts_at < ?"
        params.extend([start.isoformat(timespec="minutes"), end.isoformat(timespec="minutes")])
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
    return value.startswith("/") and not value.startswith("//") and "\\" not in value


@app.route("/")
def home():
    activities = activity_rows(user_id=session.get("user_id"), limit=3)
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
    activities = activity_rows(query, category, session.get("user_id"), when=when, location=location)
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
    activity = activity_rows(user_id=session.get("user_id"))
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
                    "SELECT name FROM users WHERE id = ?", (session["user_id"],)
                ).fetchone()
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
                        session["user_id"],
                        user["name"],
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
            (session["user_id"], activity_id),
        )
        flash("Your RSVP was removed.", "info")
    else:
        db.execute(
            "INSERT OR IGNORE INTO rsvps (user_id, activity_id, created_at) VALUES (?, ?, ?)",
            (session["user_id"], activity_id, datetime.now().isoformat(timespec="minutes")),
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
        (session["user_id"], activity_id),
    ).fetchone()
    if saved:
        db.execute(
            "DELETE FROM saved_activities WHERE user_id = ? AND activity_id = ?",
            (session["user_id"], activity_id),
        )
        flash("Removed from your saved activities.", "info")
    else:
        db.execute(
            "INSERT INTO saved_activities (user_id, activity_id, created_at) VALUES (?, ?, ?)",
            (session["user_id"], activity_id, datetime.now().isoformat(timespec="minutes")),
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
    user_id = session["user_id"]
    activities = member_activities("saved_activities", user_id)
    return render_template("activities.html", activities=activities, categories=CATEGORIES,
                           query="", selected_category="", page_title="Saved activities")


@app.route("/community")
@login_required
def community():
    user_id = session["user_id"]
    attending = member_activities("rsvps", user_id)
    saved = member_activities("saved_activities", user_id)
    return render_template("community.html", attending=attending, saved=saved)


@app.route("/register", methods=["GET", "POST"])
def register():
    if session.get("user_id"):
        return redirect(url_for("home"))
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not name or not email or len(password) < 8:
            flash("Enter your name and email, and choose a password with at least 8 characters.", "error")
        else:
            db = get_db()
            try:
                cursor = db.execute(
                    "INSERT INTO users (name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                    (name, email, generate_password_hash(password), datetime.now().isoformat(timespec="minutes")),
                )
                db.commit()
            except sqlite3.IntegrityError:
                flash("An account already uses that email address.", "error")
            else:
                session.clear()
                session["user_id"] = cursor.lastrowid
                flash("Welcome to RamRadar!", "success")
                return redirect(url_for("home"))
    return render_template("auth.html", mode="register")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("home"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Email or password was not recognized.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            flash("You're signed in.", "success")
            destination = request.args.get("next", "")
            return redirect(destination if safe_local_path(destination) else url_for("home"))
    return render_template("auth.html", mode="login")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    flash("You have been signed out.", "info")
    return redirect(url_for("home"))


@app.route("/feedback", methods=["POST"])
def submit_feedback():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip()
    subject = request.form.get("subject", "").strip()
    message = request.form.get("message", "").strip()
    allowed_subjects = {"Suggestion", "Question", "Report a problem", "Other"}
    if not name or not email or subject not in allowed_subjects or not message:
        flash("Please complete the feedback form with a valid subject.", "error")
    else:
        get_db().execute(
            "INSERT INTO feedback (name, email, subject, message, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, email, subject, message, datetime.now().isoformat(timespec="minutes")),
        )
        get_db().commit()
        flash("Thanks for helping make campus connections better.", "success")
    return redirect(url_for("home", _anchor="contact"))


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


if __name__ == "__main__":
    app.run(debug=True)
