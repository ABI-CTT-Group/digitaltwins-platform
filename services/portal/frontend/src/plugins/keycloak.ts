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
  console.log(keycloak)
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
  return roles.filter((r: string) => ['admin', 'researcher', 'clinician'].includes(r));
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
 * @param warningMinutes - Show warning when this many minutes remaining (default: 2)
 */
export function setupIdleTimeout(idleMinutes: number = 30, warningMinutes: number = 2): () => void {
  let idleTimer: number | undefined;
  let warningTimer: number | undefined;
  let lastActivityTime = 0;
  
  const idleTime = idleMinutes * 60 * 1000; // Convert to milliseconds
  const warningTime = Math.max(0, (idleMinutes - warningMinutes) * 60 * 1000); // Show warning 2 min before logout

  const handleUserActivity = () => {
    // Debounce: only process if at least 1 second has passed since last activity
    const now = Date.now();
    if (now - lastActivityTime < 1000) {
      return;
    }
    lastActivityTime = now;

    window.dispatchEvent(new CustomEvent('idle-reset'));

    console.log('🔄 User activity detected - resetting idle timer');

    // Clear existing timers
    if (idleTimer) {
      clearTimeout(idleTimer);
      console.log('⏱️  Cleared logout timer');
    }
    if (warningTimer) {
      clearTimeout(warningTimer);
      console.log('⏱️  Cleared warning timer');
    }

    // Show warning before logout
    warningTimer = window.setTimeout(() => {
      console.warn(`⚠️  WARNING: User will be logged out in ${warningMinutes} minutes due to inactivity`);
      window.dispatchEvent(
        new CustomEvent('idle-warning', {
          detail: { warningMinutes, idleMinutes },
        })
      );
    }, warningTime);

    // Set logout timer
    idleTimer = window.setTimeout(async () => {
      console.warn(`⛔ User idle for ${idleMinutes} minutes, logging out...`);
      await logout();
    }, idleTime);

    console.log(`✅ Idle timer set for ${idleMinutes} minutes (${idleTime}ms)`);
  };

  // Track user activity with events (using capture phase for earliest detection)
  const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
  
  events.forEach(event => {
    document.addEventListener(event, handleUserActivity, true);
    console.log(`📡 Listening for ${event} events`);
  });

  // Start timer immediately
  console.log(`🕒 Setting up idle timeout: ${idleMinutes} minutes`);
  handleUserActivity();

  // Return cleanup function
  return () => {
    if (idleTimer) clearTimeout(idleTimer);
    if (warningTimer) clearTimeout(warningTimer);
    events.forEach(event => {
      document.removeEventListener(event, handleUserActivity, true);
    });
    console.log('🧹 Idle timeout cleanup complete');
  };
}
