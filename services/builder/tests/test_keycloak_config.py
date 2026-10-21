"""The builder reaches Keycloak server-side over the internal address when it has one.

KEYCLOAK_PUBLIC_URL is the public (browser) address; inside the container
it may not resolve to Keycloak at all (e.g. http://localhost/auth), which made
every token check fail with 401.

Run from `services/builder/`:
    python -m pytest tests/test_keycloak_config.py
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

import yaml

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.client.keycloak import KeycloakClient  # noqa: E402

PUBLIC = "http://localhost/auth"
INTERNAL = "http://keycloak:8080/auth"


class KeycloakServerUrlTest(unittest.TestCase):
    def _client(self, **env):
        with mock.patch.dict(os.environ, env, clear=False):
            for name in ("KEYCLOAK_BASE_URL", "KEYCLOAK_PUBLIC_URL"):
                if name not in env:
                    os.environ.pop(name, None)
            return KeycloakClient()

    def test_the_internal_address_is_preferred(self):
        self.assertEqual(self._client(KEYCLOAK_BASE_URL=INTERNAL, KEYCLOAK_PUBLIC_URL=PUBLIC).server_url, INTERNAL)

    def test_the_public_address_is_the_fallback(self):
        self.assertEqual(self._client(KEYCLOAK_PUBLIC_URL=PUBLIC).server_url, PUBLIC)
        self.assertEqual(self._client(KEYCLOAK_BASE_URL="", KEYCLOAK_PUBLIC_URL=PUBLIC + "/").server_url, PUBLIC)

    def test_keys_are_fetched_under_the_context_path(self):
        verifier = self._client(KEYCLOAK_BASE_URL=INTERNAL).verifier
        self.assertEqual(verifier._certs_url, INTERNAL + "/realms/digitaltwins/protocol/openid-connect/certs")


class ComposeDefaultsTest(unittest.TestCase):
    def setUp(self):
        compose = yaml.safe_load((BACKEND_ROOT / "docker-compose.yml").read_text())
        self.env = dict(item.split("=", 1) for item in compose["services"]["builder"]["environment"])

    def test_keycloaks_tls_is_verified_by_default(self):
        self.assertEqual(self.env["KEYCLOAK_VERIFY_SSL"], "${KEYCLOAK_VERIFY_SSL:-true}")

    def test_the_public_url_default_has_the_auth_context_path(self):
        self.assertEqual(self.env["KEYCLOAK_PUBLIC_URL"], "${KEYCLOAK_PUBLIC_URL:-http://localhost/auth}")


if __name__ == "__main__":
    unittest.main()
