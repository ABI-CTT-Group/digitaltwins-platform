"""Keycloak login for the import CLI: device-authorization grant (browser SSO, no
password in the terminal) with a password-grant fallback, plus the upload-role gate.

Ported from the portal backend's ``cli/keycloak_login``; configured with the
API's ``KEYCLOAK_*`` env vars. Tokens are verified with the same shared verifier
and clients as the API's Bearer auth.
"""
import getpass
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Optional, Tuple

from digitaltwins.core import keycloak_verifier

# Same realm roles as the API's require_upload_role.
UPLOAD_ROLES = {"admin", "researcher"}
# Same clients as the API's Bearer auth (app/routers/auth.py).
ALLOWED_CLIENTS = frozenset({"portal-frontend", "api"})

_verifier = None


def _realm_url() -> str:
    return f"{os.getenv('KEYCLOAK_BASE_URL', '').rstrip('/')}/realms/{os.getenv('KEYCLOAK_REALM', '')}"


def _client_fields() -> Dict[str, str]:
    fields = {"client_id": os.getenv("KEYCLOAK_CLIENT_ID", "api")}
    if os.getenv("KEYCLOAK_CLIENT_SECRET"):
        fields["client_secret"] = os.getenv("KEYCLOAK_CLIENT_SECRET")
    return fields


def _post_form(url: str, data: Dict[str, str]):
    """POST application/x-www-form-urlencoded; return (status_code, json_body)."""
    req = urllib.request.Request(
        url, data=urllib.parse.urlencode(data).encode(), method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        # Keycloak returns 400 + {error: ...} for authorization_pending / slow_down.
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except ValueError:
            return e.code, {}


def verify_token(token: str) -> Dict:
    """Verify ``token`` with the shared Keycloak verifier; return its claims.

    Raises ``keycloak_verifier.InvalidToken`` or ``KeycloakUnavailable``.
    """
    global _verifier
    if _verifier is None:
        _verifier = keycloak_verifier.from_env(ALLOWED_CLIENTS)
    return _verifier.verify(token)


def require_upload_role(claims: Dict) -> str:
    """Return the username if the token carries an upload role, else raise PermissionError."""
    username = claims.get("preferred_username") or "<unknown>"
    roles = set(claims.get("realm_access", {}).get("roles", []))
    if not roles & UPLOAD_ROLES:
        raise PermissionError(
            f"User '{username}' lacks an upload role ({' or '.join(sorted(UPLOAD_ROLES))}); "
            f"has: {sorted(roles) or 'none'}."
        )
    return username


def device_login(timeout: int = 600) -> Tuple[str, Optional[str]]:
    """OAuth2 device-authorization grant: print a sign-in link, poll, return (access, refresh) tokens."""
    endpoint = f"{_realm_url()}/protocol/openid-connect"
    status, dev = _post_form(f"{endpoint}/auth/device", {**_client_fields(), "scope": "openid profile roles"})
    if status != 200:
        raise RuntimeError(f"Device authorization not available ({status}: {dev}).")

    interval = int(dev.get("interval", 5))
    print("\n  To authorise this import, open the link below and sign in:")
    print(f"    {dev.get('verification_uri_complete') or dev.get('verification_uri')}")
    if not dev.get("verification_uri_complete"):
        print(f"    and enter code: {dev.get('user_code')}")
    print("  Waiting for sign-in…")

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(interval)
        status, poll = _post_form(f"{endpoint}/token", {
            **_client_fields(),
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": dev["device_code"],
        })
        if status == 200:
            return poll["access_token"], poll.get("refresh_token")
        error = poll.get("error")
        if error == "authorization_pending":
            continue
        if error == "slow_down":
            interval += 5
            continue
        raise RuntimeError(f"Login failed: {error or poll}")
    raise TimeoutError("Timed out waiting for sign-in.")


def password_login(username: Optional[str] = None) -> Tuple[str, Optional[str]]:
    """Resource-owner password grant (prompts for credentials); return (access, refresh) tokens."""
    username = username or input("Username: ").strip()
    status, body = _post_form(f"{_realm_url()}/protocol/openid-connect/token", {
        **_client_fields(), "grant_type": "password", "username": username,
        "password": getpass.getpass("Password: "), "scope": "openid",
    })
    if status != 200:
        raise PermissionError(f"Login failed for '{username}': {body.get('error_description') or body}")
    return body["access_token"], body.get("refresh_token")


def refresh(refresh_token: str) -> str:
    """Exchange the sign-in's refresh token for a fresh access token.

    Access tokens are short-lived; the import re-fetches one just before the commit
    (tools and workflows register in SEEK with it). Raises PermissionError once the
    sign-in itself has expired.
    """
    status, body = _post_form(f"{_realm_url()}/protocol/openid-connect/token", {
        **_client_fields(), "grant_type": "refresh_token", "refresh_token": refresh_token,
    })
    if status != 200:
        raise PermissionError(f"Sign-in expired ({body.get('error') or status}); run the import again.")
    return body["access_token"]


def is_admin(token: str) -> bool:
    """Whether ``token`` carries the ``admin`` realm role (an admin's script workflow import deploys its DAG)."""
    return "admin" in verify_token(token).get("realm_access", {}).get("roles", [])


def login(use_password: bool = False, username: Optional[str] = None) -> Tuple[str, str, Optional[str]]:
    """Authenticate (device flow first, unless ``use_password``) and enforce the upload role.

    Returns ``(username, access_token, refresh_token)``; ``refresh`` turns the refresh
    token into the fresh access token that tool and workflow imports register in SEEK with.
    """
    if use_password:
        token, refresh_token = password_login(username)
    else:
        try:
            token, refresh_token = device_login()
        except RuntimeError as e:
            print(f"  Device login unavailable ({e}); falling back to password.")
            token, refresh_token = password_login(username)
    return require_upload_role(verify_token(token)), token, refresh_token
