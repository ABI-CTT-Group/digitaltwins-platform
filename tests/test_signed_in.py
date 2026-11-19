"""Checks as a signed-in user. They skip unless SMOKE_USERNAME and SMOKE_PASSWORD are set."""


def bearer(token):
    return {"Authorization": f"Bearer {token}"}


def test_sign_in_returns_a_token(client, credentials):
    response = client.post("/api/login", auth=credentials)
    assert response.status_code == 200
    assert response.json().get("access_token")


def test_api_accepts_the_token(client, token):
    response = client.get("/api/verify_token", headers=bearer(token))
    assert response.status_code == 200
    assert response.json() == {"active": True}


def test_dashboard_lists_programmes(client, token):
    response = client.get("/api/dashboard/programmes", headers=bearer(token))
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_builder_lists_workflows(client, token):
    response = client.get("/api/builder/workflow/", headers=bearer(token))
    assert response.status_code == 200
    assert isinstance(response.json(), list)
