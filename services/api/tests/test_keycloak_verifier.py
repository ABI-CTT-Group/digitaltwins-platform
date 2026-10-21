"""The shared Keycloak access-token verifier (digitaltwins.core.keycloak_verifier).

A stand-in Keycloak realm (discovery document and key set) is served on the loopback, so the
verifier's real fetch path runs, offline, under `make test-api`.
"""
import base64
import datetime
import hashlib
import hmac
import ipaddress
import json
import logging
import ssl
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from digitaltwins.core.keycloak_verifier import (
    InvalidToken,
    KeycloakUnavailable,
    KeycloakVerifier,
    from_env,
)

REALM = "digitaltwins"
ISSUER = "http://public.example/auth/realms/digitaltwins"
ALLOWED = {"portal-frontend", "api"}


def _rsa_key():
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _jwk(key, kid):
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key()))
    return {**jwk, "kid": kid, "use": "sig", "alg": "RS256"}


class FakeRealm:
    """Serves a realm's discovery document and key set; counts key-set fetches."""

    def __init__(self, tls_cert=None):
        self.keys = {}  # kid -> private key, all published
        self.certs_hits = 0
        realm = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                prefix = f"/auth/realms/{REALM}"
                if self.path == f"{prefix}/.well-known/openid-configuration":
                    # Keycloak advertises its public hostname, not the address we reach it on.
                    body = {"issuer": ISSUER, "jwks_uri": f"{ISSUER}/protocol/openid-connect/certs"}
                elif self.path == f"{prefix}/protocol/openid-connect/certs":
                    realm.certs_hits += 1
                    # Keycloak also publishes an encryption key; the verifier must skip it.
                    enc = {"kid": "enc", "kty": "RSA", "use": "enc", "alg": "RSA-OAEP",
                           "n": "AQAB", "e": "AQAB"}
                    body = {"keys": [_jwk(k, kid) for kid, k in realm.keys.items()] + [enc]}
                else:
                    self.send_error(404)
                    return
                data = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        scheme = "http"
        if tls_cert:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(*tls_cert)
            self.server.socket = context.wrap_socket(self.server.socket, server_side=True)
            scheme = "https"
        self.base_url = f"{scheme}://127.0.0.1:{self.server.server_address[1]}/auth"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def realm():
    r = FakeRealm()
    r.keys["k1"] = _rsa_key()
    yield r
    r.stop()


def _token(realm, kid="k1", key=None, **overrides):
    now = int(time.time())
    claims = {"iss": ISSUER, "azp": "portal-frontend", "typ": "Bearer", "sub": "u1",
              "preferred_username": "alice", "iat": now, "exp": now + 300}
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key or realm.keys[kid], algorithm="RS256", headers={"kid": kid})


def _verifier(realm, **kwargs):
    return KeycloakVerifier(realm.base_url, REALM, ALLOWED, **kwargs)


# ── Accepted ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("client", sorted(ALLOWED))
def test_a_valid_access_token_returns_its_claims(realm, client):
    claims = _verifier(realm).verify(_token(realm, azp=client))
    assert claims["preferred_username"] == "alice"
    assert claims["azp"] == client


def test_the_issuer_comes_from_keycloaks_discovery_document(realm):
    # The discovery issuer is the public URL, not the base URL the verifier fetched it from.
    _verifier(realm).verify(_token(realm))
    with pytest.raises(InvalidToken):
        _verifier(realm).verify(_token(realm, iss=f"{realm.base_url}/realms/{REALM}"))


# ── Rejected ───────────────────────────────────────────────────────────


@pytest.mark.parametrize("overrides", [
    {"iss": "http://other.example/auth/realms/digitaltwins"},
    {"azp": "grafana"},
    {"azp": None},
    {"typ": "ID"},
    {"typ": None},
    {"exp": int(time.time()) - 60},
    {"iat": None},
], ids=["wrong-issuer", "other-client", "no-azp", "id-token", "no-typ", "expired", "no-iat"])
def test_tokens_that_are_not_ours_are_rejected(realm, overrides):
    with pytest.raises(InvalidToken):
        _verifier(realm).verify(_token(realm, **overrides))


def test_a_token_signed_by_another_key_is_rejected(realm):
    with pytest.raises(InvalidToken):
        _verifier(realm).verify(_token(realm, key=_rsa_key()))


def test_unsigned_and_hmac_tokens_are_rejected(realm):
    claims = {"iss": ISSUER, "azp": "api", "typ": "Bearer", "iat": int(time.time()), "exp": int(time.time()) + 300}
    unsigned = jwt.encode(claims, None, algorithm="none", headers={"kid": "k1"})
    public_pem = realm.keys["k1"].public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    # Algorithm confusion: HS256 keyed with the RSA public key (PyJWT refuses to build one, so by hand).
    signing_input = b".".join(base64.urlsafe_b64encode(json.dumps(part).encode()).rstrip(b"=")
                              for part in ({"alg": "HS256", "typ": "JWT", "kid": "k1"}, claims))
    mac = hmac.new(public_pem, signing_input, hashlib.sha256).digest()
    confused = (signing_input + b"." + base64.urlsafe_b64encode(mac).rstrip(b"=")).decode()
    for token in (unsigned, confused, "not-a-jwt"):
        with pytest.raises(InvalidToken):
            _verifier(realm).verify(token)


# ── Keys ───────────────────────────────────────────────────────────────


def test_a_rotated_key_is_picked_up_with_one_fetch(realm):
    verifier = _verifier(realm, refetch_cooldown=0)
    verifier.verify(_token(realm))
    realm.keys["k2"] = _rsa_key()

    verifier.verify(_token(realm, kid="k2"))

    assert realm.certs_hits == 2


def test_known_keys_never_trigger_a_fetch(realm):
    verifier = _verifier(realm)
    verifier.verify(_token(realm))
    for token in (_token(realm), _token(realm, exp=int(time.time()) - 60), _token(realm, azp="grafana")):
        try:
            verifier.verify(token)
        except InvalidToken:
            pass
    assert realm.certs_hits == 1


def test_unknown_keys_fetch_at_most_once_per_cooldown(realm):
    verifier = _verifier(realm, refetch_cooldown=60)
    verifier.verify(_token(realm))
    stranger = _rsa_key()
    for _ in range(5):
        with pytest.raises(InvalidToken):
            verifier.verify(_token(realm, kid="unknown", key=stranger))
    assert realm.certs_hits == 1


# ── Keycloak unreachable ───────────────────────────────────────────────


def test_keycloak_down_with_nothing_cached_is_unavailable(realm):
    verifier = _verifier(realm)
    token = _token(realm)
    realm.stop()
    with pytest.raises(KeycloakUnavailable):
        verifier.verify(token)


def test_keycloak_down_with_keys_cached_still_verifies(realm):
    verifier = _verifier(realm, refetch_cooldown=0)
    verifier.verify(_token(realm))
    token = _token(realm)
    realm.stop()
    assert verifier.verify(token)["azp"] == "portal-frontend"
    with pytest.raises(InvalidToken):  # an unknown key while Keycloak is down is still just invalid
        verifier.verify(_token(realm, kid="unknown", key=_rsa_key()))


# ── Configuration from the environment ─────────────────────────────────


@pytest.fixture
def tls_realm(tmp_path):
    key = _rsa_key()
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=1)).not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), True)
            .sign(key, hashes.SHA256()))
    cert_file, key_file = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert_file.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    r = FakeRealm(tls_cert=(str(cert_file), str(key_file)))
    r.keys["k1"] = _rsa_key()
    r.ca_file = str(cert_file)
    yield r
    r.stop()


def _env(monkeypatch, realm, **extra):
    monkeypatch.setenv("KEYCLOAK_BASE_URL", realm.base_url)
    monkeypatch.setenv("KEYCLOAK_REALM", REALM)
    for name in ("KEYCLOAK_VERIFY_SSL", "KEYCLOAK_CA_CERT"):
        monkeypatch.delenv(name, raising=False)
    for name, value in extra.items():
        monkeypatch.setenv(name, value)


def test_from_env_reads_the_base_url_and_realm(monkeypatch, realm):
    _env(monkeypatch, realm)
    assert from_env(ALLOWED).verify(_token(realm))["sub"] == "u1"


def test_from_env_accepts_an_explicit_base_url(monkeypatch, realm):
    _env(monkeypatch, realm, KEYCLOAK_BASE_URL="http://127.0.0.1:9/unreachable")
    assert from_env(ALLOWED, base_url=realm.base_url).verify(_token(realm))["sub"] == "u1"


def test_tls_is_verified_by_default(monkeypatch, tls_realm):
    _env(monkeypatch, tls_realm)
    with pytest.raises(KeycloakUnavailable):
        from_env(ALLOWED).verify(_token(tls_realm))


def test_a_ca_bundle_makes_a_private_certificate_trusted(monkeypatch, tls_realm):
    _env(monkeypatch, tls_realm, KEYCLOAK_CA_CERT=tls_realm.ca_file)
    assert from_env(ALLOWED).verify(_token(tls_realm))["sub"] == "u1"


def test_verification_can_be_turned_off_with_a_warning(monkeypatch, tls_realm, caplog):
    _env(monkeypatch, tls_realm, KEYCLOAK_VERIFY_SSL="false")
    with caplog.at_level(logging.WARNING):
        assert from_env(ALLOWED).verify(_token(tls_realm))["sub"] == "u1"
    assert "KEYCLOAK_VERIFY_SSL" in caplog.text
