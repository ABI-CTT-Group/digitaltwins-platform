import os
import tempfile

# Tests drop and recreate tables (tests/tool_app.py); with PORTAL_DB_HOST set they would hit the live portal schema.
if os.getenv("PORTAL_DB_HOST"):
    raise RuntimeError("PORTAL_DB_HOST is set: refusing to run tests against a live database. Unset it to test on SQLite.")

# The engine binds at import of app.models.db_model, so point it at a throwaway file before any test module
# imports the app; never inherit DATABASE_PATH (it may name the real registry, e.g. ./plugin_registry.db).
os.environ["DATABASE_PATH"] = os.path.join(tempfile.mkdtemp(prefix="portal-tests-"), "plugin_registry.db")
