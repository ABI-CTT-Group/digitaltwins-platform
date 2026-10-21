"""
IAM by Keycloak
"""
import logging
import requests
import os

from fastapi import APIRouter
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from dotenv import load_dotenv

from digitaltwins.core import keycloak_verifier

logger = logging.getLogger(__name__)

router = APIRouter()

load_dotenv()
# Keycloak configs
KEYCLOAK_BASE_URL = os.getenv("KEYCLOAK_BASE_URL")
KEYCLOAK_REALM = os.getenv("KEYCLOAK_REALM")
KEYCLOAK_CLIENT_ID = os.getenv("KEYCLOAK_CLIENT_ID")
KEYCLOAK_CLIENT_SECRET = os.getenv("KEYCLOAK_CLIENT_SECRET")

keycloak_realm_url = f"{KEYCLOAK_BASE_URL}/realms/{KEYCLOAK_REALM}"
keycloak_token_url = f"{keycloak_realm_url}/protocol/openid-connect/token"

# Clients whose access tokens the API accepts: the portal ("portal-frontend") and the API's own
# client ("api": Basic auth, /login, the CLI and scripts). Tokens are verified locally rather than
# introspected: portal tokens don't name "api" in their audience, so Keycloak refuses to introspect
# them for the api client. docs/decisions/2026-10-21-one-keycloak-token-verifier.md
ALLOWED_CLIENTS = frozenset({"portal-frontend", "api"})

_verifier = None


def get_verifier() -> keycloak_verifier.KeycloakVerifier:
    global _verifier
    if _verifier is None:
        _verifier = keycloak_verifier.from_env(ALLOWED_CLIENTS)
    return _verifier


def verify_access_token(token: str) -> dict:
    """The token's claims, else 401 (not a valid token for the API) or 503 (Keycloak unreachable)."""
    try:
        return get_verifier().verify(token)
    except keycloak_verifier.KeycloakUnavailable as exc:
        logger.error("Keycloak unavailable: %s", exc)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Keycloak is unavailable")
    except keycloak_verifier.InvalidToken as exc:
        logger.info("Rejected access token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def auth_basic(credentials: HTTPBasicCredentials = Depends(HTTPBasic())):
    result = get_token(credentials)
    if not result.get("access_token"):
        print(f"[auth] Basic auth failed, Keycloak response: {result}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result
        )
    else:
        claims = verify_access_token(result["access_token"])
        return {"username": credentials.username, "token": result["access_token"], "claims": claims}


def auth_bearer(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    token = credentials.credentials
    payload = verify_access_token(token)
    username = payload.get("preferred_username") or payload.get("username") or "unknown"
    return {"username": username, "token": token, "claims": payload}


def validate_credentials(
        basic_credentials: HTTPBasicCredentials = Depends(HTTPBasic(auto_error=False)),
        bearer_credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))
):
    if basic_credentials:
        username = auth_basic(basic_credentials)
        return username
    elif bearer_credentials:
        username = auth_bearer(bearer_credentials)
        return username
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication method",
            headers={"WWW-Authenticate": "Basic or Bearer"},
        )


# Keycloak realm roles allowed to upload, approve, delete and write FHIR annotations.
UPLOAD_ROLES = {"admin", "researcher"}


def require_upload_role(credentials: dict = Depends(validate_credentials)) -> dict:
    """Authenticated caller whose token carries an upload realm role, else 403."""
    roles = set(credentials.get("claims", {}).get("realm_access", {}).get("roles", []))
    if not roles & UPLOAD_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires one of the realm roles: {', '.join(sorted(UPLOAD_ROLES))}",
        )
    return credentials


@router.post("/login", tags=["auth"])
def login(credentials: HTTPBasicCredentials = Depends(HTTPBasic())):
    # validate_credentials(credentials)
    result = get_token(basic_credentials=credentials)
    return result


@router.post("/token", tags=["auth"])
def get_token(
        basic_credentials: HTTPBasicCredentials = Depends(HTTPBasic(auto_error=False)),
        bearer_credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer(auto_error=False))
):
    if basic_credentials:
        payload = {
            "client_id": KEYCLOAK_CLIENT_ID,
            "client_secret": KEYCLOAK_CLIENT_SECRET,
            "grant_type": "password",
            "username": basic_credentials.username,
            "password": basic_credentials.password
        }
    elif bearer_credentials:
        payload = {
            "client_id": KEYCLOAK_CLIENT_ID,
            "client_secret": KEYCLOAK_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": bearer_credentials.credentials
        }
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication method",
            headers={"WWW-Authenticate": "Basic, Bearer"},
        )

    try:
        response = requests.post(keycloak_token_url, data=payload, timeout=10)
    except requests.RequestException as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Unable to reach Keycloak token endpoint: {exc}",
        ) from exc

    if response.status_code != 200:
        try:
            error_detail = response.json()
        except ValueError:
            error_detail = response.text
        print(f"[auth] Keycloak token error ({response.status_code}): {error_detail}")
        raise HTTPException(status_code=response.status_code, detail=error_detail)

    try:
        return response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Keycloak returned a non-JSON token response.",
        ) from exc


@router.get("/verify_token", tags=["auth"])
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(HTTPBearer())):
    result = auth_bearer(credentials)
    return {"active": bool(result.get("username"))}


def has_admin_role(credentials: dict) -> bool:
    """Whether the caller's token carries the ``admin`` realm role."""
    return "admin" in credentials.get("claims", {}).get("realm_access", {}).get("roles", [])


def require_admin_role(credentials: dict = Depends(validate_credentials)) -> dict:
    """Authenticated caller whose token carries the ``admin`` realm role, else 403."""
    if not has_admin_role(credentials):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Requires the realm role: admin")
    return credentials
