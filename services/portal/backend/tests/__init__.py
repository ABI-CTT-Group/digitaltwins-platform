import os

# Tests drop and recreate tables (tests/tool_app.py); with PORTAL_DB_HOST set they would hit the live portal schema.
if os.getenv("PORTAL_DB_HOST"):
    raise RuntimeError("PORTAL_DB_HOST is set: refusing to run tests against a live database. Unset it to test on SQLite.")
