import Keycloak from 'keycloak-js';
import { emitIdleWarning, emitIdleReset, emitSessionExpired } from './session_events';

// Keycloak instance
let keycloakInstance: Keycloak | null = null;

// Parameters Keycloak appends to a redirect when it answers an auth request.
const OIDC_CALLBACK_PARAMS = [
  'code',
  'state',
  'session_state',
  'error',
  'error_description',
  'error_uri',
  'iss',
  'id_token',
  'access_token',
  'token_type',
  'expires_in',
];

function deleteOidcParams(params: URLSearchParams): boolean {
  let changed = false;
  for (const key of OIDC_CALLBACK_PARAMS) {
    if (params.has(key)) {
      params.delete(key); // deletes *every* occurrence of the key
      changed = true;
    }
  }
  return changed;
}

/**
 * Strip any OIDC callback parameters from a URL.
 *
 * Keycloak appends its answer to whatever redirect URI it was given. If that URI
 * still carries the *previous* answer, the two responses pile up in one fragment
 * (`#error=login_required&state=A&...&code=xyz&state=B`) and keycloak-js reads
 * the stale `error` before the fresh `code` — a successful login is then parsed
 * as a failed one, and the user appears logged out until they reload by hand.
 *
 * This happens whenever a check-sso answer lands in the top-level URL, which is
 * exactly what a cross-origin Keycloak forces: the silent iframe cannot see the
 * SSO cookie (third-party), so keycloak-js falls back to a full-page redirect.
 */
function stripOidcParams(rawUrl: string): string {
  const url = new URL(rawUrl);

  const query = new URLSearchParams(url.search);
  if (deleteOidcParams(query)) {
    url.search = query.toString();
  }

  // Only rewrite the fragment if it actually held OIDC params — otherwise a
  // plain anchor (`#section`) would be mangled into `section=` by the round-trip.
  const fragment = new URLSearchParams(url.hash.replace(/^#/, ''));
  if (deleteOidcParams(fragment)) {
    url.hash = fragment.toString();
  }

  return url.toString();
}

/**
 * Initialize Keycloak.
 *
 * `onLoad: 'check-sso'` is what makes the session survive a page refresh.
 * keycloak-js holds tokens in memory only, so a reload wipes them; check-sso
 * silently asks Keycloak "do I still have an SSO session?" via a hidden iframe
 * pointed at `silent-check-sso.html`. Without it, init() returns
 * `authenticated: false` on every reload and the router guard bounces the user
 * to Home even though their Keycloak session is still perfectly alive.
 */
export async function initKeycloak(): Promise<Keycloak> {
  if (keycloakInstance) {
    return keycloakInstance;
  }
  const keycloak = new Keycloak({
    url: import.meta.env.VITE_KEYCLOAK_URL,
    realm: import.meta.env.VITE_KEYCLOAK_REALM,
    clientId: import.meta.env.VITE_KEYCLOAK_CLIENT_ID,
  });

  try {
    const authenticated = await keycloak.init({
      onLoad: 'check-sso',
      silentCheckSsoRedirectUri: `${window.location.origin}/silent-check-sso.html`,
      pkceMethod: 'S256',
      // The login-status iframe polls Keycloak on a timer and needs a secure
      // context; we detect session loss from refresh failures instead, which
      // works identically over HTTP and HTTPS.
      checkLoginIframe: false,
    });

    keycloakInstance = keycloak;

    // Leave no callback residue in the address bar. keycloak-js has already read
    // whatever it needed out of the URL by now, and anything left behind would be
    // inherited by the next redirect URI we build. Runs before the router is
    // installed (see main.ts), so vue-router reads the cleaned URL.
    const cleanedUrl = stripOidcParams(window.location.href);
    if (cleanedUrl !== window.location.href) {
      window.history.replaceState(window.history.state, '', cleanedUrl);
    }

    if (authenticated) {
      // The access token is short-lived (5 min) by design; renew it silently so
      // the user never notices. Session *lifetime* is Keycloak's call, not
      // ours — when the refresh token is finally rejected (absolute session
      // lifespan reached, or session revoked), we surface it to the UI instead
      // of silently throwing the user back to Home.
      keycloak.onTokenExpired = async () => {
        // Don't renew for a user who has already gone idle. Refreshing on a
        // timer regardless of activity would keep resetting Keycloak's own
        // server-side idle clock, defeating it entirely — the idle timeout
        // would then exist only in client-side JS, which is not an enforcement
        // boundary. Letting the token lapse lets the server expire the session.
        if (isIdleWarningActive()) return;

        try {
          await keycloak.updateToken(30);
        } catch (err) {
          console.error('Token refresh failed — session cannot be renewed', err);
          emitSessionExpired();
        }
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
export function getKeycloak(): Keycloak | null {
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
  const token = keycloakInstance?.token;
  return token;
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
 * Send the user to the Keycloak login page, returning them to wherever they
 * currently are once they are back — not to Home.
 *
 * The return address is scrubbed: handing Keycloak a URI that still carries an
 * earlier callback's params is what makes a successful login parse as a failure
 * (see `stripOidcParams`).
 */
export async function login(): Promise<void> {
  await keycloakInstance?.login({ redirectUri: stripOidcParams(window.location.href) });
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

// ===================== Idle timeout =====================
//
// Mirrors the realm's `ssoSessionIdleTimeout` (1800s). Two independent clocks
// run: this one, driven by DOM activity, and Keycloak's, driven by token
// refreshes. They agree because `onTokenExpired` above stops renewing once the
// warning is showing.

let idleTimer: number | undefined;
let warningTimer: number | undefined;
let warningActive = false;
let resumeIdleTimers: (() => void) | null = null;

function isIdleWarningActive(): boolean {
  return warningActive;
}

/**
 * Called when the user explicitly chooses to stay signed in. Renews the token
 * (which also resets Keycloak's server-side idle clock) and restarts the local
 * timers.
 */
export async function resumeSession(): Promise<void> {
  warningActive = false;
  resumeIdleTimers?.();

  try {
    // -1 forces a refresh regardless of remaining token validity, so the server
    // sees activity now rather than up to 5 minutes from now.
    await keycloakInstance?.updateToken(-1);
  } catch (err) {
    console.error('Could not renew session on resume', err);
    emitSessionExpired();
  }
}

/**
 * Sign the user out after a period of inactivity, warning them first.
 *
 * The warning is *sticky*: once it appears, ordinary mouse movement no longer
 * silently resets the clock. Otherwise the dialog would flicker away the moment
 * the user brushed the mouse, and they would never get the chance to actually
 * decide. It takes an explicit `resumeSession()` to keep the session alive.
 *
 * @param idleMinutes - Minutes of inactivity before auto-logout
 * @param warningMinutes - Show the warning this many minutes before logout
 */
export function setupIdleTimeout(idleMinutes: number = 30, warningMinutes: number = 2): () => void {
  let lastActivityTime = 0;

  const idleMs = idleMinutes * 60 * 1000;
  const warningMs = Math.max(0, (idleMinutes - warningMinutes) * 60 * 1000);

  const clearTimers = () => {
    if (idleTimer) clearTimeout(idleTimer);
    if (warningTimer) clearTimeout(warningTimer);
  };

  const armTimers = () => {
    clearTimers();

    warningTimer = window.setTimeout(() => {
      warningActive = true;
      emitIdleWarning({ secondsRemaining: warningMinutes * 60 });
    }, warningMs);

    idleTimer = window.setTimeout(async () => {
      warningActive = false;
      await logout();
    }, idleMs);
  };

  const handleUserActivity = () => {
    // Once warned, only an explicit choice counts — see the note above.
    if (warningActive) return;

    // Debounce: at most one re-arm per second.
    const now = Date.now();
    if (now - lastActivityTime < 1000) return;
    lastActivityTime = now;

    emitIdleReset();
    armTimers();
  };

  const events = ['mousedown', 'mousemove', 'keypress', 'scroll', 'touchstart', 'click'];
  events.forEach(event => document.addEventListener(event, handleUserActivity, true));

  resumeIdleTimers = armTimers;
  armTimers();

  return () => {
    clearTimers();
    resumeIdleTimers = null;
    warningActive = false;
    events.forEach(event => document.removeEventListener(event, handleUserActivity, true));
  };
}
