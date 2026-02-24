import Keycloak from 'keycloak-js';

// Keycloak instance
let keycloakInstance: Keycloak.Keycloak | null = null;

/**
 * Initialize Keycloak
 */
export async function initKeycloak(): Promise<Keycloak.Keycloak> {
  if (keycloakInstance) {
    return keycloakInstance;
  }

  const keycloak = new Keycloak({
    url: import.meta.env.VITE_KEYCLOAK_URL || 'https://130.216.216.243:8009/',
    realm: import.meta.env.VITE_KEYCLOAK_REALM || 'digitaltwins',
    clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'api',
  });

  try {
    const authenticated = await keycloak.init({
      onLoad: 'check-sso',
      silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
      pkceMethod: 'S256',
    });

    keycloakInstance = keycloak;
    
    if (authenticated) {
      console.log('User is authenticated');
      // Setup token refresh
      keycloak.onTokenExpired = () => {
        console.log('Token expired, refreshing...');
        keycloak.refreshToken(30);
      };
    }

    return keycloak;
  } catch (error) {
    console.error('Keycloak initialization failed:', error);
    throw error;
  }
}

/**
 * Get current Keycloak instance
 */
export function getKeycloak(): Keycloak.Keycloak | null {
  return keycloakInstance;
}

/**
 * Check if user is authenticated
 */
export function isAuthenticated(): boolean {
  return keycloakInstance?.authenticated || false;
}

/**
 * Get access token
 */
export function getAccessToken(): string | undefined {
  return keycloakInstance?.token;
}

/**
 * Get user roles
 */
export function getUserRoles(): string[] {
  if (!keycloakInstance) return [];
  
  const roles = keycloakInstance.realmAccess?.roles || [];
  // Filter to only portal roles
  return roles.filter(r => ['admin', 'researcher', 'clinician'].includes(r));
}

/**
 * Check if user has a specific role
 */
export function hasRole(role: string): boolean {
  return getUserRoles().includes(role);
}

/**
 * Get user info
 */
export function getUserInfo() {
  if (!keycloakInstance) return null;
  
  return {
    username: keycloakInstance.tokenParsed?.preferred_username,
    email: keycloakInstance.tokenParsed?.email,
    givenName: keycloakInstance.tokenParsed?.given_name,
    familyName: keycloakInstance.tokenParsed?.family_name,
    roles: getUserRoles(),
  };
}

/**
 * Logout
 */
export async function logout(): Promise<void> {
  if (keycloakInstance) {
    try {
      await keycloakInstance.logout({
        redirectUri: `${window.location.origin}/`,
      });
    } catch (error) {
      console.error('Logout failed:', error);
    }
  }
}

/**
 * Refresh token
 */
export async function refreshToken(): Promise<boolean> {
  if (!keycloakInstance) return false;
  
  try {
    const refreshed = await keycloakInstance.updateToken(30);
    return refreshed;
  } catch (error) {
    console.error('Token refresh failed:', error);
    return false;
  }
}
