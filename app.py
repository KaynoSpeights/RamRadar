
import os
from pathlib import Path


from flask import Flask, render_template, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, current_user, login_required
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager
from database import init_db
from forms import RegistrationForm, LoginForm
from user_models import (
    create_user,
    get_user_by_email,
    get_user_by_username,
    get_user_by_id,
    verify_password,
    User,
)

import sqlite3


app = Flask(__name__)

# Limit repeated requests from the same IP address.
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=[],
    storage_uri="memory://"
)


# Load the secret key from an environment variable
# or from the local, Git-ignored instance folder.
secret_key_file = Path(app.instance_path) / "secret_key.txt"

if os.environ.get("SECRET_KEY"):
    app.config["SECRET_KEY"] = os.environ["SECRET_KEY"]
elif secret_key_file.exists():
    app.config["SECRET_KEY"] = secret_key_file.read_text().strip()
else:
    raise RuntimeError(
        "SECRET_KEY is not configured. Set the SECRET_KEY "
        "environment variable or create instance/secret_key.txt."
    )

# Session security settings
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("COOKIE_SECURE", "false").lower() == "true"
)


# Enable CSRF protection
csrf = CSRFProtect(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)

# Initialize the user database
init_db(app)


@login_manager.user_loader
def load_user(user_id):
    return get_user_by_id(app.config["DATABASE"], user_id)



@app.route("/")
def home():
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegistrationForm()

    if form.validate_on_submit():
        username = form.username.data.strip().lower()
        email = form.email.data.strip().lower()
        password = form.password.data

        # Check if username is already registered
        if get_user_by_username(app.config["DATABASE"], username):
            form.username.errors.append(
                "This username is already taken."
            )

        # Check if email is already registered
        if get_user_by_email(app.config["DATABASE"], email):
            form.email.errors.append(
                "An account with this email already exists."
            )

        # Create the account if there are no validation errors
        if not form.username.errors and not form.email.errors:
            try:
                create_user(
                    app.config["DATABASE"],
                    username,
                    email,
                    password
                )

                flash(
                    "Account created successfully! You can now log in.",
                    "success"
                )
                return redirect(url_for("register"))

            except sqlite3.IntegrityError:
                flash(
                    "That username or email is already registered.",
                    "error"
                )

    return render_template("register.html", form=form)




@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("home"))

    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        password = form.password.data

        user_data = get_user_by_email(
            app.config["DATABASE"],
            email
        )

        if user_data and verify_password(
            user_data["password_hash"],
            password
        ):
            login_user(User(user_data))

            flash("You have successfully logged in!", "success")
            return redirect(url_for("home"))

        flash("Invalid email or password.", "error")

    return render_template("login.html", form=form)


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have successfully logged out.", "success")
    return redirect(url_for("login"))



if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(debug=debug_mode)
