"""Post-deploy smoke tests: read-only checks of a running platform through its gateway. See README.md."""

import os

import httpx
import pytest


@pytest.fixture(scope="session")
def base_url():
    """The platform's public URL, as users reach it (scheme and domain, no trailing slash)."""
    return os.environ.get("SMOKE_URL", "http://localhost").rstrip("/")


@pytest.fixture(scope="session")
def client(base_url):
    with httpx.Client(base_url=base_url, timeout=30) as http:
        yield http


@pytest.fixture(scope="session")
def credentials():
    username, password = os.environ.get("SMOKE_USERNAME"), os.environ.get("SMOKE_PASSWORD")
    if not (username and password):
        pytest.skip("set SMOKE_USERNAME and SMOKE_PASSWORD to run the signed-in checks")
    return username, password


@pytest.fixture(scope="session")
def token(client, credentials):
    """An access token from the API's sign-in, which runs Keycloak's password grant."""
    response = client.post("/api/login", auth=credentials)
    assert response.status_code == 200, f"sign-in failed: HTTP {response.status_code}"
    return response.json()["access_token"]
