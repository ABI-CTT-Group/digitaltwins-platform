"""Test app for the /api/tools router: SQLite tables, fake Keycloak tokens.

Import this before any ``app.*`` module: it points DATABASE_PATH at a fresh
SQLite file. Tokens: ``admin``, ``admin2``, ``researcher`` and ``viewer`` (valid,
no portal role), optionally suffixed ``#<n>``; anything else is rejected like an
expired token.
"""
import os
import sys
import tempfile
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DATABASE_PATH", str(Path(tempfile.mkdtemp()) / "tools_test.db"))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.models.db_model import Base, engine  # noqa: E402
from app.router import workflow_tool_plugin  # noqa: E402
from app.utils import auth  # noqa: E402

ROLES = {"admin": ["admin"], "admin2": ["admin"], "researcher": ["researcher"], "viewer": []}


class FakeKeycloak:
    """A token is ``<user>`` or ``<user>#<n>`` (a later token of the same user)."""

    def get_user_info(self, token):
        user = token.split("#")[0]
        if user not in ROLES:
            raise ValueError("Signature has expired")
        return {"username": user, "roles": ROLES[user]}


def make_client():
    auth.get_keycloak_client = lambda: FakeKeycloak()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app = FastAPI()
    app.include_router(workflow_tool_plugin.router)
    return TestClient(app)


def make_workflow_client():
    """The /api/workflow router on the same SQLite tables and fake Keycloak."""
    from app.router import workflow_router  # imported late: it builds MinIO / FHIR clients at import

    auth.get_keycloak_client = lambda: FakeKeycloak()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    app = FastAPI()
    app.include_router(workflow_router.router)
    return TestClient(app)


def bearer(token):
    return {"Authorization": f"Bearer {token}"}
