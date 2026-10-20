"""The builder allows its own public origin, read from PLATFORM_DOMAIN and SSL.

Run from `services/builder/`:
    python -m pytest tests/test_cors.py
"""
from unittest import mock

from fastapi.testclient import TestClient

from tests.tool_app import BACKEND_ROOT  # noqa: F401,I001  (sets DATABASE_PATH to a scratch SQLite first)
from app.main import app


def _allowed(origin, **env):
    with mock.patch.dict("os.environ", env):
        r = TestClient(app).options("/health", headers={"Origin": origin})
    return r.headers.get("access-control-allow-origin")


def test_the_platform_domain_is_an_allowed_origin():
    assert _allowed("https://platform.example", PLATFORM_DOMAIN="platform.example", SSL="true") == \
        "https://platform.example"


def test_another_origin_is_not():
    assert _allowed("https://elsewhere.example", PLATFORM_DOMAIN="platform.example", SSL="true") is None
