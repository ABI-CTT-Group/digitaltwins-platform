"""The test package refuses to load when PORTAL_DB_HOST is set: tool_app.py drops and
recreates every table, which would wipe the live portal schema.

Run from `services/api/`:
    python -m pytest tests/builder_tests/test_live_db_guard.py
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
TESTS_DIR = BACKEND_ROOT / "tests"  # where `builder_tests` imports from; BACKEND_ROOT holds `builder`


def import_tests(**env):
    base = {k: v for k, v in os.environ.items() if k != "PORTAL_DB_HOST"}
    return subprocess.run([sys.executable, "-c", "import builder_tests"], cwd=TESTS_DIR,
                          env={**base, "PYTHONPATH": str(BACKEND_ROOT), **env}, capture_output=True, text=True)


class LiveDbGuardTest(unittest.TestCase):
    def test_refuses_to_load_when_portal_db_host_is_set(self):
        r = import_tests(PORTAL_DB_HOST="database")

        self.assertNotEqual(r.returncode, 0)
        self.assertIn("PORTAL_DB_HOST", r.stderr)

    def test_loads_without_portal_db_host(self):
        r = import_tests()

        self.assertEqual(r.returncode, 0, r.stderr)

    def test_sqlite_engine_never_binds_to_the_working_dir_registry(self):
        # Test modules that import builder.main before tool_app.py sets DATABASE_PATH used to bind
        # the engine to ./plugin_registry.db, which the suite's drop_all() then wiped.
        registry = TESTS_DIR / "plugin_registry.db"
        base = {k: v for k, v in os.environ.items() if k not in ("PORTAL_DB_HOST", "DATABASE_PATH")}
        base["PYTHONPATH"] = str(BACKEND_ROOT)
        for env in (base, {**base, "DATABASE_PATH": str(registry)}):
            r = subprocess.run(
                [sys.executable, "-c",
                 "import builder_tests, builder.models.db_model as m; print(m.engine.url.database)"],
                cwd=TESTS_DIR, env=env, capture_output=True, text=True)

            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotEqual((TESTS_DIR / r.stdout.strip()).resolve(), registry.resolve())
