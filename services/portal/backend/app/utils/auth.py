from fastapi import Depends, HTTPException, status, Header
from typing import Callable
from app.client.keycloak import get_keycloak_client
import logging

logger = logging.getLogger(__name__)


async def get_current_user(authorization: str = Header(None)):
    """Dependency to extract and verify JWT token from Authorization header"""
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Extract token from "Bearer <token>" format
    scheme, _, token = authorization.partition(" ")
    
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    try:
        keycloak_client = get_keycloak_client()
        user_info = keycloak_client.get_user_info(token)
        # The raw token lets a request act as the user downstream (e.g. the tool handoff to digitaltwins-api).
        return {**user_info, "token": token}
    except Exception as e:
        logger.error(f"Authentication failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_role(required_role: str) -> Callable:
    """Factory for role-based access control dependency"""
    async def role_checker(user = Depends(get_current_user)):
        try:
            user_roles = user.get("roles", [])
            if required_role not in user_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"User does not have required role: {required_role}"
                )
            return user
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authorization check failed: {e}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Authorization check failed"
            )
    
    return role_checker


def require_any_role(*roles: str) -> Callable:
    """Dependency: the user must hold at least one of ``roles``."""
    async def role_checker(user=Depends(get_current_user)):
        if not set(user.get("roles", [])) & set(roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of the roles: {', '.join(roles)}",
            )
        return user

    return role_checker


# Pre-defined role checkers
def require_admin() -> Callable:
    """Check for admin role"""
    return require_role("admin")


def require_researcher() -> Callable:
    """Check for researcher role"""
    return require_role("researcher")


def require_clinician() -> Callable:
    """Check for clinician role"""
    return require_role("clinician")
