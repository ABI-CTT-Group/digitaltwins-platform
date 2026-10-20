"""The routes portal-backend serves. /api/ belongs to the platform API; the portal owns only /api/portal/.

Run from `backend/` (never inside the live container):
    python -m pytest tests/test_route_prefixes.py
"""
from tests.tool_app import BACKEND_ROOT  # noqa: F401,I001  (sets DATABASE_PATH to a scratch SQLite first)
from app.main import app

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
