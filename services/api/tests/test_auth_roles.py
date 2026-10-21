"""The API's Keycloak auth: realm role admin|researcher required, via Bearer or Basic.

Tokens are checked by the shared verifier against a stand-in realm on the loopback
(see test_keycloak_verifier.py).
"""
import base64
import sys
import time
from pathlib import Path

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routers import auth
from digitaltwins.core.keycloak_verifier import KeycloakVerifier
from test_keycloak_verifier import ISSUER, REALM, FakeRealm, _rsa_key

_REALM = None


def _token(roles=None, expires_in=300, azp="portal-frontend", **extra):
    now = int(time.time())
    claims = {"iss": ISSUER, "azp": azp, "typ": "Bearer", "preferred_username": "alice",
              "iat": now, "exp": now + expires_in, **extra}
    if roles is not None:
        claims["realm_access"] = {"roles": roles}
    return jwt.encode(claims, _REALM.keys["k1"], algorithm="RS256", headers={"kid": "k1"})


@pytest.fixture
def realm(monkeypatch):
    global _REALM
    _REALM = FakeRealm()
    _REALM.keys["k1"] = _rsa_key()
    monkeypatch.setattr(auth, "get_verifier", lambda: KeycloakVerifier(_REALM.base_url, REALM, auth.ALLOWED_CLIENTS))
    yield _REALM
    _REALM.stop()


@pytest.fixture
def client(realm):
    app = FastAPI()

    @app.get("/protected")
    def protected(creds=Depends(auth.require_upload_role)):
        return {"username": creds["username"]}

    @app.get("/admin-only")
    def admin_only(creds=Depends(auth.require_admin_role)):
        return {"username": creds["username"]}

    return TestClient(app)


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize("role", ["admin", "researcher"])
def test_bearer_with_upload_role_is_allowed(client, role):
    r = client.get("/protected", headers=_bearer(_token(["offline_access", role])))
    assert r.status_code == 200
    assert r.json() == {"username": "alice"}


def test_bearer_without_upload_role_is_forbidden(client):
    r = client.get("/protected", headers=_bearer(_token(["offline_access", "viewer"])))
    assert r.status_code == 403


def test_token_without_realm_access_is_forbidden(client):
    assert client.get("/protected", headers=_bearer(_token())).status_code == 403


def test_expired_token_is_unauthorized(client):
    r = client.get("/protected", headers=_bearer(_token(["admin"], expires_in=-60)))
    assert r.status_code == 401


def test_a_token_from_another_client_is_unauthorized(client):
    r = client.get("/protected", headers=_bearer(_token(["admin"], azp="grafana")))
    assert r.status_code == 401


@pytest.mark.parametrize("client_id", sorted(auth.ALLOWED_CLIENTS))
def test_the_portal_and_api_clients_are_accepted(client, client_id):
    assert client.get("/protected", headers=_bearer(_token(["admin"], azp=client_id))).status_code == 200


def test_a_rejected_token_gets_a_generic_401(client):
    r = client.get("/protected", headers=_bearer(_token(["admin"], azp="grafana")))
    assert r.json()["detail"] == "Invalid or expired token"
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_keycloak_unreachable_is_503(client, realm):
    token = _token(["admin"])
    realm.stop()
    assert client.get("/protected", headers=_bearer(token)).status_code == 503


def test_missing_credentials_is_unauthorized(client):
    assert client.get("/protected").status_code == 401


def _basic(user="alice", password="<REDACTED>"):
    raw = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {raw}"}


def test_basic_auth_uses_roles_from_the_issued_token(client, monkeypatch):
    monkeypatch.setattr(auth, "get_token", lambda *a, **k: {"access_token": _token(["researcher"], azp="api")})
    assert client.get("/protected", headers=_basic()).status_code == 200


def test_basic_auth_without_upload_role_is_forbidden(client, monkeypatch):
    monkeypatch.setattr(auth, "get_token", lambda *a, **k: {"access_token": _token(["viewer"])})
    assert client.get("/protected", headers=_basic()).status_code == 403


def test_admin_role_is_allowed_where_admin_is_required(client):
    r = client.get("/admin-only", headers=_bearer(_token(["offline_access", "admin"])))
    assert r.status_code == 200


@pytest.mark.parametrize("roles", [["researcher"], ["viewer"], []])
def test_other_roles_are_forbidden_where_admin_is_required(client, roles):
    r = client.get("/admin-only", headers=_bearer(_token(["offline_access", *roles])))
    assert r.status_code == 403
    assert "admin" in r.json()["detail"]


def test_credentials_never_reach_the_log(client, monkeypatch, capsys, caplog):
    monkeypatch.setattr(auth, "get_token", lambda *a, **k: {"access_token": _token(["researcher"])})
    token = _token(["admin"])

    client.get("/protected", headers=_basic(password="hunter-two-marker"))
    client.get("/protected", headers=_bearer(token))

    out = capsys.readouterr()
    logged = out.out + out.err + caplog.text
    assert "hunter-two-marker" not in logged
    assert token not in logged
