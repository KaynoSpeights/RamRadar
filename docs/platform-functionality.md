# RamRadar platform prototype

## Run locally

Install the packages in `requirements.txt`, then run `python app.py` from the project directory. SQLite is initialized automatically on the first request, and the local database is written to the ignored `instance/` directory.

Set `RAMRADAR_SECRET_KEY` to a persistent, randomly generated secret before deployment. For HTTPS deployments, set `RAMRADAR_SECURE_COOKIES=true` so session cookies are sent only over secure connections. Without a configured secret, the development server generates a temporary key at startup, so sessions do not survive a restart.

## Implemented

- Responsive homepage with category navigation, client-side search, mobile navigation, and reduced-motion support.
- Server-filtered activity search by keyword, category, time window, and location.
- Activity detail and creation pages.
- Account registration and sign-in using password hashes.
- Session-based RSVP, saved activities, and a member community page for reviewing those plans.
- Feedback form with SQLite storage.
- Privacy policy page describing the current prototype.
- CSRF tokens for state-changing form submissions.

The initial activity cards are seeded demonstration content, not confirmed WSSU events. Student-created listings are shown under their organizer's name. RamRadar does not currently verify WSSU affiliation or organizations.

## Current limitations

This prototype does not send email or push notifications, offer group messaging, provide personalized recommendations, support account deletion/export, or administer event changes and cancellations. Feedback is stored in the local database; it is not emailed. SQLite is suitable for the local prototype but should be reviewed before a multi-instance deployment.

## Tests

Run the Flask route and database tests with:

```sh
python -m unittest discover -s tests -p 'test_*.py' -v
```

The existing JavaScript interaction checks are documented in `search-and-filters.md`; they require Node.js and the listed test dependencies.
