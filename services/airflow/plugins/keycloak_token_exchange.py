"""
Airflow plugin: Keycloak → Airflow token exchange endpoint.

Uses fastapi_root_middlewares so the endpoint is intercepted before
Airflow's SPA catch-all route handles it.

Endpoint:
    POST /airflow/keycloak/exchange          (external, via nginx)
    Authorization: Bearer <keycloak_access_token>

    → 200 {"access_token": "<airflow_jwt>"}
    → 401 if token is missing or invalid
    → 404 if the user hasn't logged into Airflow via Keycloak yet

Notes:
- The Airflow 3 api-server process does NOT run the Flask/FAB web app,
  so cached_app() is unavailable. We query the FAB user table directly
  via SQLAlchemy and mint a JWT using PyJWT with the user's integer ID
  as the 'sub' claim — matching what flask_jwt_extended produces.
"""

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from airflow.plugins_manager import AirflowPlugin

log = logging.getLogger(__name__)


def _get_fab_user(username: str):
    """
    Look up a FAB user by username via SQLAlchemy.
    Returns the user's integer ID or None.
    Works in the api-server process where the Flask app is not running.
    """
    # Try the Airflow FAB provider model first, fall back to raw FAB model.
    FabUser = None
    for model_path in [
        "airflow.providers.fab.auth_manager.models",
        "flask_appbuilder.security.sqla.models",
    ]:
        try:
            import importlib
            mod = importlib.import_module(model_path)
            FabUser = mod.User
            log.debug("Loaded FabUser from %s", model_path)
            break
        except Exception as e:
            log.debug("Could not import User from %s: %s", model_path, e)

    if FabUser is None:
        log.error("Could not import FAB User model from any known path")
        return None

    try:
        from sqlalchemy import select
        from airflow import settings
        with settings.Session() as session:
            result = session.execute(
                select(FabUser).where(FabUser.username == username)
            ).scalar_one_or_none()
            if result is not None:
                uid = result.id
                log.debug("Found user '%s' with id=%s", username, uid)
                return uid
            log.warning("User '%s' not found in FAB database", username)
            return None
    except Exception as e:
        log.error("DB query failed for user '%s': %s: %s", username, type(e).__name__, e, exc_info=True)
        return None


def _create_airflow_token(user_id: int, username: str) -> str:
    """
    Mint an Airflow 3 compatible JWT using PyJWT.

    Format reverse-engineered from a real /auth/token response:
      sub = str(user_id)   — string, not int
      aud = "apache-airflow"  — required; Airflow rejects tokens without it
      iss = []
    """
    secret = os.environ.get("AIRFLOW__API_AUTH__JWT_SECRET")
    if not secret:
        raise RuntimeError("AIRFLOW__API_AUTH__JWT_SECRET not set")

    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iss": [],
        "aud": "apache-airflow",
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(hours=24)).timestamp()),
        "iat": int(now.timestamp()),
    }
    token = jwt.encode(payload, secret, algorithm="HS512")
    log.info("Issued Airflow token for user '%s' (id=%s)", username, user_id)
    return token


class KeycloakExchangeMiddleware(BaseHTTPMiddleware):
    """
    Intercepts POST /keycloak/exchange before Airflow's SPA catch-all
    route handles it. Path match uses endswith() so it works regardless
    of the /airflow base-path prefix.
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path.endswith("/keycloak/exchange"):
            if request.method != "POST":
                return JSONResponse({"detail": "Method Not Allowed"}, status_code=405)
            return await self._handle(request)
        return await call_next(request)

    async def _handle(self, request: Request):
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return JSONResponse(
                {"detail": "Bearer token required. Expected: Authorization: Bearer <keycloak_token>"},
                status_code=401,
            )

        keycloak_token = auth[7:]

        try:
            claims = jwt.decode(
                keycloak_token,
                options={"verify_signature": False},
                algorithms=["RS256"],
            )
        except Exception:
            log.exception("Failed to decode Keycloak token")
            return JSONResponse({"detail": "Invalid token"}, status_code=401)

        username = claims.get("preferred_username")
        if not username:
            return JSONResponse(
                {"detail": "Token missing preferred_username claim"}, status_code=401
            )

        user_id = _get_fab_user(username)
        if user_id is None:
            return JSONResponse(
                {
                    "detail": (
                        f"User '{username}' not found in Airflow. "
                        "Please log into the Airflow UI via Keycloak at least once "
                        "to provision your account."
                    )
                },
                status_code=404,
            )

        try:
            token = _create_airflow_token(user_id, username)
            return JSONResponse({"access_token": token})
        except Exception:
            log.exception("Token creation failed for user '%s'", username)
            return JSONResponse({"detail": "Token creation failed"}, status_code=500)


class KeycloakTokenExchangePlugin(AirflowPlugin):
    name = "keycloak_token_exchange"
    fastapi_root_middlewares = [
        {
            "name": "keycloak_exchange_middleware",
            "middleware": KeycloakExchangeMiddleware,
        }
    ]
