"""Keycloak access-token verification, shared by the platform API (and its CLI) and the builder.

A token is accepted only if it is an RS256 access token (``typ`` Bearer) signed by one of the
realm's keys, unexpired, from the realm's issuer, and issued to one of the caller's allowed
clients (``azp``). The issuer and keys are fetched from Keycloak over ``base_url``, the
internal address, and cached. An unknown key id refetches them at most once per cooldown, so
bad tokens cannot make a service hammer Keycloak.

This file is copied verbatim to services/builder/app/client/keycloak_verifier.py (the two
services share no code); a builder test fails if the copies differ, so edit both together.
It needs nothing beyond the standard library and PyJWT.
docs/decisions/2026-10-21-one-keycloak-token-verifier.md
"""
import json
import logging
import os
import ssl
import threading
import time
import urllib.request

import jwt

logger = logging.getLogger(__name__)

ALGORITHMS = ["RS256"]
REFETCH_COOLDOWN = 60  # seconds
_TIMEOUT = 10  # seconds


class InvalidToken(Exception):
    """The token is not a valid access token for this service."""


class KeycloakUnavailable(Exception):
    """Keycloak could not be reached, and no issuer and keys are cached."""


class KeycloakVerifier:
    def __init__(self, base_url, realm, allowed_clients, ssl_context=None, refetch_cooldown=REFETCH_COOLDOWN):
        realm_url = f"{base_url.rstrip('/')}/realms/{realm}"
        self._discovery_url = f"{realm_url}/.well-known/openid-configuration"
        # Not the discovery document's jwks_uri: that uses Keycloak's public hostname.
        self._certs_url = f"{realm_url}/protocol/openid-connect/certs"
        self._allowed_clients = frozenset(allowed_clients)
        self._ssl_context = ssl_context
        self._cooldown = refetch_cooldown
        self._issuer = None
        self._keys = {}
        self._fetched_at = None
        self._lock = threading.Lock()

    def verify(self, token):
        """Return the token's claims, or raise InvalidToken or KeycloakUnavailable."""
        try:
            kid = jwt.get_unverified_header(token).get("kid")
        except jwt.PyJWTError as exc:
            raise InvalidToken(f"malformed token: {exc}") from exc
        issuer, key = self._issuer_and_key(kid)
        try:
            claims = jwt.decode(
                token, key, algorithms=ALGORITHMS, issuer=issuer,
                options={"require": ["exp", "iat", "iss", "azp", "typ"], "verify_aud": False},
            )
        except jwt.PyJWTError as exc:
            raise InvalidToken(str(exc)) from exc
        if claims["azp"] not in self._allowed_clients:
            raise InvalidToken(f"token issued to client {claims['azp']!r}, which is not accepted here")
        if claims["typ"] != "Bearer":
            raise InvalidToken(f"not an access token (typ {claims['typ']!r})")
        return claims

    def _issuer_and_key(self, kid):
        with self._lock:
            if kid not in self._keys and self._may_fetch():
                self._fetch()
            key = self._keys.get(kid)
        if key is None:
            raise InvalidToken(f"unknown signing key {kid!r}")
        return self._issuer, key

    def _may_fetch(self):
        return self._fetched_at is None or time.monotonic() - self._fetched_at >= self._cooldown

    def _fetch(self):
        try:
            issuer = self._get_json(self._discovery_url)["issuer"]
            keys = {
                k["kid"]: jwt.PyJWK(k, algorithm="RS256").key
                for k in self._get_json(self._certs_url)["keys"]
                if k.get("use", "sig") == "sig" and k.get("kty") == "RSA" and "kid" in k
            }
        except (OSError, ValueError, KeyError, jwt.PyJWTError) as exc:
            if self._issuer is None:
                raise KeycloakUnavailable(f"cannot fetch the realm's issuer and keys: {exc}") from exc
            logger.warning("Keeping cached Keycloak keys; refetch failed: %s", exc)
        else:
            self._issuer, self._keys = issuer, keys
        self._fetched_at = time.monotonic()

    def _get_json(self, url):
        with urllib.request.urlopen(url, timeout=_TIMEOUT, context=self._ssl_context) as resp:
            return json.loads(resp.read().decode())


def from_env(allowed_clients, base_url=None):
    """A verifier for KEYCLOAK_BASE_URL (or ``base_url``) and KEYCLOAK_REALM.

    Keycloak's TLS certificate is verified unless KEYCLOAK_VERIFY_SSL is ``false``;
    KEYCLOAK_CA_CERT names a CA bundle to trust instead of the system's.
    """
    return KeycloakVerifier(
        base_url or os.environ["KEYCLOAK_BASE_URL"],
        os.getenv("KEYCLOAK_REALM", "digitaltwins"),
        allowed_clients,
        ssl_context=_ssl_context_from_env(),
    )


def _ssl_context_from_env():
    ca_cert = os.getenv("KEYCLOAK_CA_CERT", "").strip()
    if ca_cert:
        return ssl.create_default_context(cafile=ca_cert)
    context = ssl.create_default_context()
    if os.getenv("KEYCLOAK_VERIFY_SSL", "true").strip().lower() == "false":
        logger.warning("KEYCLOAK_VERIFY_SSL=false: Keycloak's TLS certificate is not verified")
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    return context
