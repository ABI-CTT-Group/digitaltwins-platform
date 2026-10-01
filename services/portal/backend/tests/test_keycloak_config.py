"""portal-backend reaches Keycloak server-side over the internal address when it has one.

PORTAL_KEYCLOAK_BASE_URL is the public (browser) address; inside the container
it may not resolve to Keycloak at all (e.g. http://localhost/auth), which made
every token check fail with 401.

Run from `backend/`:
    python -m unittest tests.test_keycloak_config
"""
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.client.keycloak import KeycloakClient  # noqa: E402

PUBLIC = "http://localhost/auth"
INTERNAL = "http://keycloak:8080/auth"


class KeycloakServerUrlTest(unittest.TestCase):
    def _server_url(self, **env):
        with mock.patch.dict(os.environ, {"KEYCLOAK_CLIENT_SECRET": "", **env}, clear=False):
            for name in ("KEYCLOAK_BASE_URL", "PORTAL_KEYCLOAK_BASE_URL"):
                if name not in env:
                    os.environ.pop(name, None)
            return KeycloakClient().server_url

    def test_the_internal_address_is_preferred(self):
        self.assertEqual(self._server_url(KEYCLOAK_BASE_URL=INTERNAL, PORTAL_KEYCLOAK_BASE_URL=PUBLIC), INTERNAL + "/")

    def test_the_public_address_is_the_fallback(self):
        self.assertEqual(self._server_url(PORTAL_KEYCLOAK_BASE_URL=PUBLIC), PUBLIC + "/")
        self.assertEqual(self._server_url(KEYCLOAK_BASE_URL="", PORTAL_KEYCLOAK_BASE_URL=PUBLIC + "/"), PUBLIC + "/")

    def test_a_context_path_survives_url_joining(self):
        # python-keycloak urljoins "realms/<realm>"; without a trailing slash the
        # /auth context path is dropped and Keycloak answers 404.
        from urllib.parse import urljoin
        base = self._server_url(KEYCLOAK_BASE_URL=INTERNAL)
        self.assertEqual(urljoin(base, "realms/digitaltwins"), INTERNAL + "/realms/digitaltwins")


if __name__ == "__main__":
    unittest.main()
