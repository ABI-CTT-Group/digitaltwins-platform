"""get_current_user: one check of the token by the shared verifier, then the builder's user object.

Run from `services/builder/`:
    python -m pytest tests/test_keycloak_auth.py
"""
import os
import sys
from pathlib import Path
from unittest import mock

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.client import keycloak  # noqa: E402
from app.client.keycloak_verifier import InvalidToken, KeycloakUnavailable  # noqa: E402
from app.utils import auth  # noqa: E402

CLAIMS = {"preferred_username": "alice", "email": "a@example.org",
          "realm_access": {"roles": ["offline_access", "researcher", "airflow_admin"]}}


class StubVerifier:
    def __init__(self, outcome):
        self.outcome, self.calls = outcome, 0

    def verify(self, token):
        self.calls += 1
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


@pytest.fixture
def verifier(monkeypatch):
    def install(outcome):
        with mock.patch.dict(os.environ, {"KEYCLOAK_BASE_URL": "http://keycloak.invalid/auth"}):
            client = keycloak.KeycloakClient()
        client.verifier = StubVerifier(outcome)
        monkeypatch.setattr(auth, "get_keycloak_client", lambda: client)
        return client.verifier
    return install


@pytest.fixture
def api():
    app = FastAPI()

    @app.get("/me")
    def me(user=Depends(auth.get_current_user)):
        return user

    return TestClient(app)


def test_a_valid_token_gives_the_user_with_the_builders_roles(api, verifier):
    stub = verifier(CLAIMS)
    r = api.get("/me", headers={"Authorization": "Bearer t0k"})
    assert r.status_code == 200
    assert r.json()["username"] == "alice"
    assert r.json()["roles"] == ["researcher"]
    assert r.json()["token"] == "t0k"
    assert stub.calls == 1


def test_an_invalid_token_gets_a_generic_401(api, verifier):
    verifier(InvalidToken("token issued to client 'grafana', which is not accepted here"))
    r = api.get("/me", headers={"Authorization": "Bearer t0k"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid or expired token"
    assert r.headers["WWW-Authenticate"] == "Bearer"


def test_keycloak_unreachable_is_503(api, verifier):
    verifier(KeycloakUnavailable("connection refused"))
    assert api.get("/me", headers={"Authorization": "Bearer t0k"}).status_code == 503


def test_the_builder_accepts_the_portal_and_api_clients():
    assert keycloak.ALLOWED_CLIENTS == {"portal-frontend", "api"}
