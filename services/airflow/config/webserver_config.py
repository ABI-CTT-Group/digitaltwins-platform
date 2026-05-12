import logging
import os
import jwt
from flask_appbuilder.security.manager import AUTH_OAUTH
from airflow.providers.fab.auth_manager.security_manager.override import FabAirflowSecurityManagerOverride

log = logging.getLogger(__name__)

AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Viewer"
AUTH_ROLES_SYNC_AT_LOGIN = True

# Ensure session cookie is always sent back on the Keycloak callback redirect
SESSION_COOKIE_PATH = '/'
SESSION_COOKIE_SAMESITE = 'None'
SESSION_COOKIE_SECURE = True

AUTH_ROLES_MAPPING = {
    "airflow_admin":  ["Admin"],
    "airflow_op":     ["Op"],
    "airflow_user":   ["User"],
    "airflow_viewer": ["Viewer"],
}

OAUTH_PROVIDERS = [
    {
        "name": "keycloak",
        "icon": "fa-key",
        "token_key": "access_token",
        "remote_app": {
            "client_id":     os.environ["AIRFLOW_KEYCLOAK_CLIENT_ID"],
            "client_secret": os.environ["AIRFLOW_KEYCLOAK_CLIENT_SECRET"],
            # Browser-facing: user's browser hits the external URL for the Keycloak login page
            "authorize_url": (
                "https://test.digitaltwins.auckland.ac.nz/auth/realms/digitaltwins"
                "/protocol/openid-connect/auth"
            ),
            # Back-channel: server-to-server token exchange uses internal Docker hostname
            # to avoid hairpin NAT (external URL returns invalid_client from inside container)
            "access_token_url": (
                "http://keycloak:8080/auth/realms/digitaltwins"
                "/protocol/openid-connect/token"
            ),
            "jwks_uri": (
                "http://keycloak:8080/auth/realms/digitaltwins"
                "/protocol/openid-connect/certs"
            ),
            "client_kwargs": {"scope": "openid email profile roles"},
            "token_endpoint_auth_method": "client_secret_post",
            "api_base_url": (
                "http://keycloak:8080/auth/realms/digitaltwins"
                "/protocol/openid-connect/"
            ),
        },
    },
]


class KeycloakSecurityManager(FabAirflowSecurityManagerOverride):
    def get_oauth_user_info(self, provider, response):
        log.warning("OIDC: get_oauth_user_info called, provider=%s", provider)
        if provider == "keycloak":
            try:
                token = response["access_token"]
                claims = jwt.decode(
                    token,
                    options={"verify_signature": False},
                    algorithms=["RS256"],
                )
                user_info = {
                    "username":   claims.get("preferred_username"),
                    "email":      claims.get("email"),
                    "first_name": claims.get("given_name", ""),
                    "last_name":  claims.get("family_name", ""),
                    "role_keys":  claims.get("realm_access", {}).get("roles", []),
                }
                log.warning("OIDC: user_info extracted: %s", user_info)
                return user_info
            except Exception:
                log.exception("OIDC: failed to extract user info from token")
                return {}
        return {}


SECURITY_MANAGER_CLASS = KeycloakSecurityManager
