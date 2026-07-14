/**
 * Session lifecycle events.
 *
 * The end of a session is surfaced as a window event rather than a hard
 * `window.location` redirect, so the UI can warn the user first and let them
 * keep (or save) their work. Keycloak is the sole authority on whether the
 * session is still valid — nothing here decides that, it only reports it.
 */

export const SESSION_IDLE_WARNING = 'session:idle-warning';
export const SESSION_IDLE_RESET = 'session:idle-reset';
export const SESSION_EXPIRED = 'session:expired';

export interface IdleWarningDetail {
  /** Seconds left before the user is signed out for inactivity. */
  secondsRemaining: number;
}

export function emitIdleWarning(detail: IdleWarningDetail): void {
  window.dispatchEvent(new CustomEvent<IdleWarningDetail>(SESSION_IDLE_WARNING, { detail }));
}

export function emitIdleReset(): void {
  window.dispatchEvent(new CustomEvent(SESSION_IDLE_RESET));
}

/**
 * The session is over and cannot be renewed — the refresh token was rejected,
 * which is how both "absolute session lifetime reached" and "session revoked"
 * reach the browser. The user must sign in again.
 */
export function emitSessionExpired(): void {
  window.dispatchEvent(new CustomEvent(SESSION_EXPIRED));
}
