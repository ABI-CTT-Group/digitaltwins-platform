"""The routes the builder serves. /api/ belongs to the platform API; the builder owns only /api/builder/.

Run from `services/api/` (never inside the live container):
    python -m pytest tests/builder_tests/test_route_prefixes.py
"""
from builder_tests.tool_app import BACKEND_ROOT  # noqa: F401,I001  (sets DATABASE_PATH to a scratch SQLite first)
from builder.main import app

# Unused login/debug routes and disabled stubs, removed rather than moved (see
# docs/decisions/2026-10-20-api-prefix-and-portal-builder-split.md).
REMOVED = {
    "/api/test", "/api/login", "/api/refresh", "/api/auth/test", "/api/auth/keycloak-status",
    "/api/auth/login-keycloak", "/api/report_viewer/report_detail",
}


def _paths():
    return {route.path for route in app.routes}


def test_removed_routes_are_gone():
    assert not REMOVED & _paths()


def test_every_route_is_under_api_builder():
    # The gateway routes /api/builder/ here and the rest of /api/ to the platform API. Besides
    # those, the builder serves only its health checks and FastAPI's docs.
    own = {"/", "/health", "/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"}
    stray = sorted(p for p in _paths() - own if not p.startswith("/api/builder/"))
    assert stray == []
