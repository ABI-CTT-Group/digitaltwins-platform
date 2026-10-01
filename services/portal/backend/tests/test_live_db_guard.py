"""The test package refuses to load when PORTAL_DB_HOST is set: tool_app.py drops and
recreates every table, which would wipe the live portal schema.

Run from `backend/`:
    python -m unittest tests.test_live_db_guard
"""
import os
import subprocess
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def import_tests(**env):
    base = {k: v for k, v in os.environ.items() if k != "PORTAL_DB_HOST"}
    return subprocess.run([sys.executable, "-c", "import tests"], cwd=BACKEND_ROOT,
                          env={**base, **env}, capture_output=True, text=True)


class LiveDbGuardTest(unittest.TestCase):
    def test_refuses_to_load_when_portal_db_host_is_set(self):
        r = import_tests(PORTAL_DB_HOST="database")

        self.assertNotEqual(r.returncode, 0)
        self.assertIn("PORTAL_DB_HOST", r.stderr)

    def test_loads_without_portal_db_host(self):
        r = import_tests()

        self.assertEqual(r.returncode, 0, r.stderr)
