"""
Tests for choosing the portal database from the environment: SQLite unless
PORTAL_DB_HOST is set, then Postgres built from the PORTAL_DB_* variables.

Run from `backend/`:
    python -m unittest tests.test_db_config
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_PATH", str(BACKEND_ROOT / "tmp" / "test_plugin_registry.db"))
(BACKEND_ROOT / "tmp").mkdir(parents=True, exist_ok=True)

from sqlalchemy.engine import make_url  # noqa: E402

from app.models.db_model import database_url  # noqa: E402


class DatabaseUrlTest(unittest.TestCase):
    def test_sqlite_when_portal_db_host_unset(self):
        with mock.patch.dict(os.environ, {"DATABASE_PATH": "/data/x.db"}, clear=True):
            url = database_url()
        self.assertEqual(url.drivername, "sqlite")
        self.assertEqual(url.database, "/data/x.db")

    def test_postgres_when_portal_db_host_set(self):
        env = {
            "PORTAL_DB_HOST": "database",
            "PORTAL_DB_PORT": "5432",
            "PORTAL_DB_NAME": "digitaltwins",
            "PORTAL_DB_USER": "portal",
            "PORTAL_DB_PASSWORD": "p@ss:/w#rd",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            url = database_url()
        self.assertEqual(url.drivername, "postgresql+psycopg2")
        self.assertEqual((url.host, url.port, url.database, url.username), ("database", 5432, "digitaltwins", "portal"))
        # Special characters must survive rendering to a connection string and back.
        rendered = url.render_as_string(hide_password=False)
        self.assertEqual(make_url(rendered).password, "p@ss:/w#rd")


if __name__ == "__main__":
    unittest.main()
