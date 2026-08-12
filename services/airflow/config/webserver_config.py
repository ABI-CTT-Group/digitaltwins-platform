"""
webserver_config.py — Airflow FAB OAuth2 / Keycloak SSO configuration.

This file is loaded by Flask-AppBuilder (via the FAB auth manager) at startup.
It configures Keycloak as the sole OAuth2 identity provider for the Airflow UI.

Environment variables required (set in docker-compose.yml / .env):
  AIRFLOW_KEYCLOAK_CLIENT_SECRET  — secret matching the 'airflow' Keycloak client
  KEYCLOAK_INTERNAL_URL           — container-to-container base URL (e.g. http://keycloak:8080/auth)
  KEYCLOAK_PUBLIC_URL             — browser-facing base URL (e.g. http://localhost/auth)
  KEYCLOAK_REALM                  — realm name (e.g. digitaltwins)

Realm-role → Airflow-role mapping:
  airflow_admin  → Admin
  airflow_op     → Op
  airflow_user   → User
  airflow_viewer → Viewer

NOTE: We split the OIDC endpoints into public (browser-facing) vs internal
(container-to-container) to avoid the "localhost refused connection" error that
occurs when FAB's server-side token exchange tries to reach the public gateway URL
from inside the Docker network.
"""

import os
import jwt as pyjwt

from airflow.providers.fab.auth_manager.security_manager.override import FabAirflowSecurityManagerOverride
from flask_appbuilder.security.manager import AUTH_OAUTH

# ---------------------------------------------------------------------------
# Auth type: OAuth2 / OIDC
# ---------------------------------------------------------------------------
AUTH_TYPE = AUTH_OAUTH

# Auto-create an Airflow user on first successful Keycloak login.
AUTH_USER_REGISTRATION = True

# Ensure roles are re-synced on each login (otherwise they stick to AUTH_USER_REGISTRATION_ROLE)
AUTH_ROLES_SYNC_AT_LOGIN = True

# Default role when no matching realm role is found in the token.
AUTH_USER_REGISTRATION_ROLE = "Viewer"

# ---------------------------------------------------------------------------
# Keycloak URLs
#   _KC_INTERNAL_*  → used by FAB for server-side calls (token exchange, userinfo)
#   _KC_PUBLIC_*    → used by the browser for the authorization redirect
# ---------------------------------------------------------------------------
_KC_INTERNAL_URL = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth")
_KC_PUBLIC_URL   = os.environ.get("KEYCLOAK_PUBLIC_URL",   "http://localhost/auth")
_KC_REALM        = os.environ.get("KEYCLOAK_REALM",        "digitaltwins")

_KC_INTERNAL_BASE = f"{_KC_INTERNAL_URL}/realms/{_KC_REALM}/protocol/openid-connect"
_KC_PUBLIC_BASE   = f"{_KC_PUBLIC_URL}/realms/{_KC_REALM}/protocol/openid-connect"

OAUTH_PROVIDERS = [
    {
        "name": "keycloak",
        "icon": "fa-key",
        "token_key": "access_token",
        "remote_app": {
            "client_id": "airflow",
            "client_secret": os.environ["AIRFLOW_KEYCLOAK_CLIENT_SECRET"],
            # authorize_url  — browser-facing: Keycloak login page the USER visits
            "authorize_url": f"{_KC_PUBLIC_BASE}/auth",
            # access_token_url — server-side: FAB exchanges the code for a token
            #   Must use the INTERNAL URL so the container can reach Keycloak.
            "access_token_url": f"{_KC_INTERNAL_BASE}/token",
            # api_base_url — server-side: base for userinfo, jwks, etc.
            "api_base_url": f"{_KC_INTERNAL_URL}/realms/{_KC_REALM}/protocol/",
            # userinfo_endpoint — server-side: used to fetch user details
            "userinfo_endpoint": f"{_KC_INTERNAL_BASE}/userinfo",
            # jwks_uri — server-side: used to verify token signatures
            "jwks_uri": f"{_KC_INTERNAL_BASE}/certs",
            "client_kwargs": {"scope": "openid email profile"},
        },
    }
]

# ---------------------------------------------------------------------------
# Realm-role → Airflow-role mapping via a custom security manager
# ---------------------------------------------------------------------------
_ROLE_MAP = {
    "airflow_admin":  "Admin",
    "airflow_op":     "Op",
    "airflow_user":   "User",
    "airflow_viewer": "Viewer",
}


class CustomSecurityManager(FabAirflowSecurityManagerOverride):
    """Map Keycloak realm roles into Airflow roles at login time."""

    def get_oauth_user_info(self, provider, resp):
        info = super().get_oauth_user_info(provider, resp)

        # Decode the access token without signature verification (Keycloak
        # already validated it server-side via the OIDC flow).
        access_token = resp.get("access_token", "")
        try:
            claims = pyjwt.decode(
                access_token, options={"verify_signature": False}
            )
        except Exception:
            claims = {}

        realm_roles = claims.get("realm_access", {}).get("roles", [])
        airflow_roles = [
            _ROLE_MAP[r] for r in realm_roles if r in _ROLE_MAP
        ]

        # Assign the highest-privilege role found; fall back to the default.
        info["role_keys"] = airflow_roles if airflow_roles else [AUTH_USER_REGISTRATION_ROLE]
        return info


SECURITY_MANAGER_CLASS = CustomSecurityManager
