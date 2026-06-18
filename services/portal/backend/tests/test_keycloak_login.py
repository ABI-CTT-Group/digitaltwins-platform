"""Unit test for the CLI admin-role gate (pure function, no network)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.cli.keycloak_login import require_admin  # noqa: E402


class RequireAdminTests(unittest.TestCase):
    def test_admin_passes_and_returns_username(self):
        self.assertEqual(
            require_admin({"username": "dr.smith", "roles": ["admin", "researcher"]}),
            "dr.smith",
        )

    def test_non_admin_rejected(self):
        with self.assertRaises(PermissionError):
            require_admin({"username": "nurse", "roles": ["clinician"]})

    def test_no_roles_rejected(self):
        with self.assertRaises(PermissionError):
            require_admin({"username": "x"})


if __name__ == "__main__":
    unittest.main()
