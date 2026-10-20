"""The test package refuses to load when BUILDER_DB_HOST is set: tool_app.py drops and
recreates every table, which would wipe the live portal schema.

Run from `services/builder/`:
    python -m pytest tests/test_live_db_guard.py
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def import_tests(**env):
    base = {k: v for k, v in os.environ.items() if k != "BUILDER_DB_HOST"}
    return subprocess.run([sys.executable, "-c", "import tests"], cwd=BACKEND_ROOT,
                          env={**base, **env}, capture_output=True, text=True)


class LiveDbGuardTest(unittest.TestCase):
    def test_refuses_to_load_when_portal_db_host_is_set(self):
        r = import_tests(BUILDER_DB_HOST="database")

        self.assertNotEqual(r.returncode, 0)
        self.assertIn("BUILDER_DB_HOST", r.stderr)

    def test_loads_without_portal_db_host(self):
        r = import_tests()

        self.assertEqual(r.returncode, 0, r.stderr)

    def test_sqlite_engine_never_binds_to_the_working_dir_registry(self):
        # Test modules that import app.main before tool_app.py sets DATABASE_PATH used to bind
        # the engine to ./plugin_registry.db, which the suite's drop_all() then wiped.
        registry = BACKEND_ROOT / "plugin_registry.db"
        base = {k: v for k, v in os.environ.items() if k not in ("BUILDER_DB_HOST", "DATABASE_PATH")}
        for env in (base, {**base, "DATABASE_PATH": str(registry)}):
            r = subprocess.run(
                [sys.executable, "-c",
                 "import tests, app.models.db_model as m; print(m.engine.url.database)"],
                cwd=BACKEND_ROOT, env=env, capture_output=True, text=True)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotEqual((BACKEND_ROOT / r.stdout.strip()).resolve(), registry.resolve())
