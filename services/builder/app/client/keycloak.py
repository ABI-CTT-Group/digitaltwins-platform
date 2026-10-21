import os
import json
from typing import Optional, Dict, List
from keycloak import KeycloakOpenID
from jose import jwt, JWTError
import logging
import urllib3

logger = logging.getLogger(__name__)


class KeycloakClient:
    """Keycloak authentication and authorization client"""

    def __init__(self):
        # Server-side calls (the realm public key) prefer Keycloak's internal
        # address; KEYCLOAK_PUBLIC_URL is the public one, which may not resolve
        # to Keycloak from inside this container (e.g. http://localhost/auth).
        # The trailing slash keeps a context path such as /auth when python-keycloak urljoins its paths.
        self.server_url = (os.getenv('KEYCLOAK_BASE_URL') or os.getenv('KEYCLOAK_PUBLIC_URL') or '').rstrip('/') + '/'
        self.realm_name = os.getenv('KEYCLOAK_REALM', 'digitaltwins')
        self.client_id = os.getenv('KEYCLOAK_CLIENT_ID', 'api')
        self.verify_ssl = os.getenv('KEYCLOAK_VERIFY_SSL', 'false').lower() == 'true'
        self.ca_cert = os.getenv('KEYCLOAK_CA_CERT', '').strip()
        verify_value = self.ca_cert if self.ca_cert else self.verify_ssl

        if verify_value is False:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        logger.info(
            "Initializing Keycloak client with server: %s (verify=%s, ca_cert=%s)",
            self.server_url,
            verify_value,
            "set" if self.ca_cert else "empty",
        )
        
        # Initialize OpenID client for token validation
        oidc_kwargs = {
            'server_url': self.server_url,
            'client_id': self.client_id,
            'realm_name': self.realm_name,
            'verify': verify_value,
        }
        self.oidc = KeycloakOpenID(**oidc_kwargs)
        if hasattr(self.oidc, "connection") and hasattr(self.oidc.connection, "verify"):
            self.oidc.connection.verify = verify_value
        
        # Cache for public key
        self._public_key = None

    def get_public_key(self) -> str:
        """Get Keycloak public key for JWT verification"""
        if self._public_key is None:
            try:
                self._public_key = self.oidc.public_key()
            except Exception as e:
                logger.error(f"Failed to get public key from Keycloak: {e}")
                raise
        return self._public_key

    def verify_token(self, token: str) -> Dict:
        """Verify and decode JWT token from Keycloak"""
        try:
            # Get the public key
            public_key = self.get_public_key()
            
            # Format public key
            public_key_pem = f"-----BEGIN PUBLIC KEY-----\n{public_key}\n-----END PUBLIC KEY-----"
            
            # Decode and verify token
            payload = jwt.decode(
                token,
                public_key_pem,
                algorithms=["RS256"],
                audience=self.client_id,
                options={"verify_aud": False}  # Allow for now, can be strict later
            )
            return payload
        except JWTError as e:
            logger.error(f"Token verification failed: {e}")
            raise

    def get_user_roles(self, access_token: str) -> List[str]:
        """Extract roles from JWT token"""
        try:
            payload = self.verify_token(access_token)
            
            # Extract roles from realm_access.roles
            roles = payload.get('realm_access', {}).get('roles', [])
            
            # Filter to only include portal roles (admin, researcher, clinician)
            portal_roles = [r for r in roles if r in ['admin', 'researcher', 'clinician']]
            
            return portal_roles
        except Exception as e:
            logger.error(f"Failed to extract roles from token: {e}")
            return []

    def get_user_info(self, access_token: str) -> Dict:
        """Get user information from token"""
        try:
            payload = self.verify_token(access_token)
            return {
                "username": payload.get('preferred_username'),
                "email": payload.get('email'),
                "given_name": payload.get('given_name'),
                "family_name": payload.get('family_name'),
                "roles": self.get_user_roles(access_token)
            }
        except Exception as e:
            logger.error(f"Failed to get user info: {e}")
            raise

    def has_role(self, access_token: str, required_role: str) -> bool:
        """Check if user has a specific role"""
        roles = self.get_user_roles(access_token)
        return required_role in roles

    def get_token_info(self, access_token: str) -> Dict:
        """Get full token information"""
        try:
            payload = self.verify_token(access_token)
            return payload
        except Exception as e:
            logger.error(f"Failed to get token info: {e}")
            raise


# Global instance
_keycloak_client: Optional[KeycloakClient] = None


def get_keycloak_client() -> KeycloakClient:
    """Get or create Keycloak client instance"""
    global _keycloak_client
    if _keycloak_client is None:
        _keycloak_client = KeycloakClient()
    return _keycloak_client
