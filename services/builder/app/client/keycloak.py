import os
from typing import Optional, Dict, List
import logging

from app.client import keycloak_verifier

logger = logging.getLogger(__name__)

# Clients whose access tokens the builder accepts: the portal ("portal-frontend"), and the API's own
# client ("api"), whose tokens the platform API relays when its caller signed in with Basic auth.
# docs/decisions/2026-10-21-one-keycloak-token-verifier.md
ALLOWED_CLIENTS = frozenset({"portal-frontend", "api"})
# The realm roles the builder's routes check.
PORTAL_ROLES = ("admin", "researcher", "clinician")


class KeycloakClient:
    """Keycloak token checks: the shared verifier (keycloak_verifier.py) and the builder's user object."""

    def __init__(self):
        # Keys and the issuer are fetched over Keycloak's internal address when there is one;
        # KEYCLOAK_PUBLIC_URL is the public one, which may not resolve to Keycloak from inside
        # this container (e.g. http://localhost/auth).
        self.server_url = (os.getenv('KEYCLOAK_BASE_URL') or os.getenv('KEYCLOAK_PUBLIC_URL') or '').rstrip('/')
        self.verifier = keycloak_verifier.from_env(ALLOWED_CLIENTS, base_url=self.server_url)
        logger.info("Verifying Keycloak tokens against %s", self.server_url)

    def verify_token(self, token: str) -> Dict:
        """The token's claims; raises keycloak_verifier.InvalidToken or KeycloakUnavailable."""
        return self.verifier.verify(token)

    @staticmethod
    def portal_roles(payload: Dict) -> List[str]:
        """The token's realm roles that the builder checks (admin, researcher, clinician)."""
        return [r for r in payload.get('realm_access', {}).get('roles', []) if r in PORTAL_ROLES]

    def get_user_roles(self, access_token: str) -> List[str]:
        """Extract roles from JWT token"""
        return self.portal_roles(self.verify_token(access_token))

    def get_user_info(self, access_token: str) -> Dict:
        """Get user information from token"""
        payload = self.verify_token(access_token)
        return {
            "username": payload.get('preferred_username'),
            "email": payload.get('email'),
            "given_name": payload.get('given_name'),
            "family_name": payload.get('family_name'),
            "roles": self.portal_roles(payload),
        }

    def has_role(self, access_token: str, required_role: str) -> bool:
        """Check if user has a specific role"""
        return required_role in self.get_user_roles(access_token)

    def get_token_info(self, access_token: str) -> Dict:
        """Get full token information"""
        return self.verify_token(access_token)


# Global instance
_keycloak_client: Optional[KeycloakClient] = None


def get_keycloak_client() -> KeycloakClient:
    """Get or create Keycloak client instance"""
    global _keycloak_client
    if _keycloak_client is None:
        _keycloak_client = KeycloakClient()
    return _keycloak_client
