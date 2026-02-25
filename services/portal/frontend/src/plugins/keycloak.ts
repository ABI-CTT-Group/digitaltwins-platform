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
    clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID || 'portal-frontend',
  });

  try {
    const authenticated = await keycloak.init({
      onLoad: 'check-sso',
      silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
      pkceMethod: 'S256',
      checkLoginIframe: false, // Disable to avoid insecure context error on HTTP deployments
    });

    keycloakInstance = keycloak;
    
    if (authenticated) {
      console.log('User is authenticated');
      
      // OPTION A: No auto-refresh (current setting)
      // Token will expire naturally without auto-refresh
      // User will need to re-authenticate when token expires
      keycloak.onTokenExpired = () => {
        console.log('Token expired - user will need to re-authenticate');
        window.location.href = '/';
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

/**
 * Setup idle timeout - logs out user after specified minutes of inactivity
 * @param idleMinutes - Minutes of inactivity before auto-logout (default: 30)
 */
export function setupIdleTimeout(idleMinutes: number = 5): () => void {
  let idleTimer: number | undefined;
  const idleTime = idleMinutes * 60 * 1000; // Convert to milliseconds

  const resetTimer = () => {
    if (idleTimer) clearTimeout(idleTimer);
    
    idleTimer = window.setTimeout(async () => {
      console.log(`User idle for ${idleMinutes} minutes, logging out...`);
      await logout();
    }, idleTime);
  };

  // Track user activity
  const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
  events.forEach(event => {
    document.addEventListener(event, resetTimer, true);
  });

  // Start timer
  resetTimer();

  // Return cleanup function
  return () => {
    if (idleTimer) clearTimeout(idleTimer);
    events.forEach(event => {
      document.removeEventListener(event, resetTimer, true);
    });
  };
}
