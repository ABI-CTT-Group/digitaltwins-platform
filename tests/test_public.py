"""Checks that need no account: each service answers through the gateway."""

import pytest


def test_portal_serves_its_page(client):
    response = client.get("/")
    assert response.status_code == 200
    assert '<div id="app">' in response.text


def test_api_is_healthy(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_keycloak_issuer_matches_the_public_url(client, base_url):
    # A mismatch means PLATFORM_PROTOCOL/PLATFORM_DOMAIN don't match how users reach the
    # platform, and every token would then fail verification.
    response = client.get("/auth/realms/digitaltwins/.well-known/openid-configuration")
    assert response.status_code == 200
    assert response.json()["issuer"] == f"{base_url}/auth/realms/digitaltwins"


def test_airflow_components_are_healthy(client):
    # Airflow answers 200 even when a component is down, so check each one.
    response = client.get("/airflow/api/v2/monitor/health")
    assert response.status_code == 200
    statuses = {name: part.get("status") for name, part in response.json().items()}
    assert statuses and all(status == "healthy" for status in statuses.values()), statuses


@pytest.mark.parametrize("path", ["/jupyter/hub/api/health", "/seek/", "/fhir/metadata"])
def test_service_answers(client, path):
    assert client.get(path).status_code == 200


def test_builder_requires_sign_in(client):
    # Reaches the builder through portal-frontend's nginx; 401 shows both hops and auth work.
    assert client.get("/api/builder/workflow/").status_code == 401
