"""Keycloak login for the CLI: device-authorization grant (preferred — browser
SSO, no password in the terminal) with a password-grant fallback, plus the admin
role gate.

HTTP uses stdlib ``urllib`` (no third-party deps like ``requests``, which isn't
installed in the backend image). ``require_admin`` is a pure function and stays
importable for unit tests without the keycloak client.
"""
from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, List, Optional

# Role that counts as admin for the import CLI.
_ADMIN_ROLE = "admin"


def require_admin(user_info: Dict) -> str:
    """Return the username if the authenticated user has the admin role, else
    raise PermissionError. ``user_info`` is the dict from
    ``KeycloakClient.get_user_info`` (``{"username", "roles", ...}``)."""
    roles: List[str] = user_info.get("roles") or []
    if _ADMIN_ROLE not in roles:
        username = user_info.get("username") or "<unknown>"
        raise PermissionError(
            f"User '{username}' lacks the '{_ADMIN_ROLE}' role required to import datasets "
            f"(roles: {roles or 'none'})."
        )
    return user_info.get("username") or "<unknown>"


def _kc():
    """Lazy keycloak client (reuses the backend's config + token verification)."""
    from app.client.keycloak import get_keycloak_client
    return get_keycloak_client()


def _endpoints(kc) -> Dict[str, str]:
    base = f"{kc.server_url.rstrip('/')}/realms/{kc.realm_name}/protocol/openid-connect"
    return {"device": f"{base}/auth/device", "token": f"{base}/token"}


def _ssl_context(kc) -> Optional[ssl.SSLContext]:
    verify = kc.ca_cert if kc.ca_cert else kc.verify_ssl
    if verify is False:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx
    if isinstance(verify, str) and verify:  # CA cert file path
        return ssl.create_default_context(cafile=verify)
    return None  # default verification (ignored for http://)


def _post_form(url: str, data: Dict[str, str], ctx, timeout: int = 30):
    """POST application/x-www-form-urlencoded; return (status_code, json_body)."""
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        # Keycloak returns 400 + a JSON {error: ...} for pending/slow_down/etc.
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


def device_login(timeout: int = 600) -> Dict:
    """OAuth2 device-authorization grant. Prints a URL + code for the operator to
    log in via browser SSO, polls for the token, and returns the verified
    ``user_info`` dict. Raises RuntimeError on unsupported flow, TimeoutError on
    timeout."""
    kc = _kc()
    eps = _endpoints(kc)
    ctx = _ssl_context(kc)

    data = {"client_id": kc.client_id, "scope": "openid email profile roles"}
    if kc.client_secret:
        data["client_secret"] = kc.client_secret

    status, dev = _post_form(eps["device"], data, ctx)
    if status != 200:
        raise RuntimeError(
            f"Device authorization not available ({status}: {dev}). "
            "Enable the device flow on the Keycloak client, or use --password."
        )

    interval = int(dev.get("interval", 5))
    device_code = dev["device_code"]
    verify_uri = dev.get("verification_uri_complete") or dev.get("verification_uri")

    print("\n  To authorise this import, open the link below and sign in:")
    print(f"    {verify_uri}")
    if not dev.get("verification_uri_complete"):
        print(f"    and enter code: {dev.get('user_code')}")
    print("  Waiting for sign-in…")

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(interval)
        status, poll = _post_form(
            eps["token"],
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
                "client_id": kc.client_id,
                **({"client_secret": kc.client_secret} if kc.client_secret else {}),
            },
            ctx,
        )
        if status == 200:
            return kc.get_user_info(poll["access_token"])
        err = poll.get("error")
        if err == "authorization_pending":
            continue
        if err == "slow_down":
            interval += 5
            continue
        raise RuntimeError(f"Login failed: {err or poll}")

    raise TimeoutError("Timed out waiting for sign-in.")


def password_login(username: Optional[str] = None) -> Dict:
    """Resource-owner password grant fallback. Prompts for credentials if not
    supplied and returns the verified ``user_info`` dict."""
    import getpass  # lazy

    kc = _kc()
    if not username:
        username = input("Username: ").strip()
    password = getpass.getpass("Password: ")
    token_response = kc.authenticate_with_credentials(username, password)
    return kc.get_user_info(token_response["access_token"])


def login(use_password: bool = False, username: Optional[str] = None):
    """Authenticate + enforce admin. Returns ``(admin_username, user_info)``.

    Tries the device flow first (unless ``use_password``), falling back to the
    password grant if the device flow isn't available. Raises PermissionError if
    the user isn't an admin."""
    if use_password:
        user_info = password_login(username)
    else:
        try:
            user_info = device_login()
        except RuntimeError as e:
            print(f"  Device login unavailable ({e}); falling back to password.")
            user_info = password_login(username)
    return require_admin(user_info), user_info
