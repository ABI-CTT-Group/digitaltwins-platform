// Outbound links to sibling platform services that the portal does NOT own.
//
// These are RELATIVE paths on purpose. Each service is mounted under a fixed prefix on
// the platform's edge gateway (SEEK at /seek via RAILS_RELATIVE_URL_ROOT, JupyterHub at
// /jupyter via c.JupyterHub.base_url). A relative URL resolves against whatever origin
// the browser already has, so the same bundle works on localhost, on a real host, and
// after an HTTP→HTTPS switch with no rebuild — which is the whole point of routing
// everything through the gateway. An absolute URL baked in here would pin the host.
//
// The leading slash matters: `/seek` is an absolute-path reference resolved against the
// ORIGIN only (→ http://<host>/seek from any page), NOT against the current path. A bare
// `seek` would resolve relative to the current route (→ http://<host>/<route>/seek).
//
// This is the single source of truth: import from here, do not re-hardcode the strings.
// They previously lived in three places (the catalogue card, the home card, the footer)
// and drifted — two carried a stale absolute IP fallback, one was empty.
//
// Trade-off: a bare `vite dev` server with no gateway in front cannot resolve these, so
// the links 404 in standalone frontend-only dev. That matches how the portal is actually
// run (integration happens inside the full stack) and how these links behaved before.

export const SEEK_URL = '/seek';
export const JUPYTER_BASE_URL = '/jupyter';
