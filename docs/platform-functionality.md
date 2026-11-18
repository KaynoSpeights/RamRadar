# RamRadar platform prototype

## Run locally

Install the packages in `requirements.txt`, then run `python app.py` from the project directory. SQLite is initialized automatically on the first request, and the local database is written to the ignored `instance/` directory.

Set `SECRET_KEY` (or `RAMRADAR_SECRET_KEY`) to a persistent, randomly generated secret before deployment. For HTTPS deployments, set `COOKIE_SECURE=true` (or `RAMRADAR_SECURE_COOKIES=true`) so session cookies are sent only over secure connections. For local development, the app writes a random key to the ignored `instance/secret_key.txt` file.

## Implemented

- Responsive homepage with category navigation, client-side search, mobile navigation, and reduced-motion support.
- Server-filtered activity search by keyword, category, time window, and location.
- Activity detail and creation pages.
- Account registration and sign-in using scrypt password hashes, request validation, CSRF protection, Flask-Login sessions, and login rate limiting.
- Session-based RSVP, saved activities, and a member community page for reviewing those plans.
- Feedback form with SQLite storage.
- Privacy policy page describing the current prototype.
- CSRF tokens for state-changing form submissions.

The initial activity cards are seeded demonstration content, not confirmed WSSU events. Student-created listings are shown under their organizer's name. RamRadar does not currently verify WSSU affiliation or organizations.

Account creation and sign-in use a unique username and password. The site does not collect contact details for accounts or feedback. Existing data from earlier versions is migrated without its contact-detail fields.

## Current limitations

This prototype does not send messages or push notifications, offer group messaging, provide personalized recommendations, support account deletion/export, or administer event changes and cancellations. Feedback is stored in the local database. SQLite is suitable for the local prototype but should be reviewed before a multi-instance deployment.

## Tests

Run the Flask route and database tests with:

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```

The existing JavaScript interaction checks are documented in `search-and-filters.md`; they require Node.js and the listed test dependencies.
