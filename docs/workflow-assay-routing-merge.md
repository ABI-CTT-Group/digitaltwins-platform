# main_buildout Merge Notes for Chinchien and Linkun

This document covers all conflicts resolved when merging `origin/main` into
`main_buildout` across the three submodules. It explains what each branch
contributed and why each decision was made, so the changes can be reviewed
and ported back to `main` where appropriate.

---

# Part 1: digitaltwins-api — Assay Workflow Routing

## Background

`main_buildout` and `main` diverged on `app/routers/workflow.py` in
`digitaltwins-api`. This document explains what each branch contributed
and how the conflict was resolved, so the merge can be reviewed and
the result ported back to `main` if desired.

---

## What `main` added

**Commit:** `d22b208 feat [assay]: run jupyter assay`

The `run_assay` endpoint gained tag-based dispatch: an assay's SEEK tags
now determine how it is run.

```python
tags = assay.get("assay").get("attributes").get("tags")

if "script" in tags:
    # trigger Airflow preprocessor DAG
    response = _trigger_dag(PREPROCESSOR_DAG_ID, conf)
    ...
    return {"dag_run": ..., "monitor_url": ...}
elif "notebook" in tags:
    # return a JupyterLab URL for the user to open
    monitor_url = f"http://{HOSTNAME}:8008/lab/workspaces/auto-0/tree/work/assays/assay_{assay_id}"
    return {"url": monitor_url}
else:
    raise HTTPException(400, "Assay must have 'script' or 'notebook' tag")
```

The monitor URL for Airflow used the internal `HOSTNAME:AIRFLOW_PORT`
directly.

---

## What `main_buildout` had

Two changes made independently on `main_buildout`:

### 1. User token passthrough (`user_keycloak_token`)

The calling user's Keycloak Bearer token is extracted from the request
and passed to `_trigger_dag`, which attempts to exchange it for a
user-scoped Airflow JWT (via a Keycloak token exchange plugin). This
attributes the DAG run to the actual user in Airflow rather than the
service account.

```python
user_token = bearer_credentials.credentials if bearer_credentials else None
response = _trigger_dag(PREPROCESSOR_DAG_ID, conf, user_keycloak_token=user_token)
```

Falls back silently to the service account if exchange fails.

### 2. Proxy-aware Airflow monitor URL (`AIRFLOW_PUBLIC_URL`)

The abi_portal deployment serves Airflow behind an nginx reverse proxy
at `/airflow/`. Using `HOSTNAME:PORT` produces an internal URL that
doesn't work for users. The fix reads `AIRFLOW_PUBLIC_URL` from the
environment:

```python
monitor_base_url = AIRFLOW_PUBLIC_URL.rstrip('/') if AIRFLOW_PUBLIC_URL \
    else f"http://{HOSTNAME}:{AIRFLOW_EXPOSE_PORT}"
```

`AIRFLOW_PUBLIC_URL` is set to `https://abi1.drai.auckland.ac.nz/airflow`
in `.env`.

---

## Merged result

The merged `main_buildout` combines all three contributions:

1. **Tag-based dispatch** from main — unchanged logic, `script` vs
   `notebook` vs error.
2. **User token passthrough** — applied to the `script` branch's
   `_trigger_dag` call.
3. **Proxy-aware monitor URL** — applied to the `script` branch's
   `monitor_base_url`.
4. **Notebook URL updated for JupyterHub** — `main` referenced
   JupyterLab directly on port 8008. `main_buildout` replaced JupyterLab
   with JupyterHub (proxied at `/jupyterhub/`), so the notebook URL
   now uses the `JUPYTERHUB_PUBLIC_URL` env var:

```python
jupyterhub_url = os.getenv("JUPYTERHUB_PUBLIC_URL", "").rstrip('/')
monitor_url = f"{jupyterhub_url}/hub/user-redirect/lab/tree/work/assays/assay_{assay_id}"
```

---

## Recommendation for `main`

The user token passthrough and proxy-aware monitor URL are deployment
improvements that should be safe to bring into `main` as well. The
JupyterHub URL change only applies if `main` also adopts JupyterHub
(replacing JupyterLab) — otherwise the original JupyterLab URL is
correct for that branch.

---

# Part 2: DigitalTWINS-Portal — Five Conflicts

## Context

`main_buildout` diverged from `main` by approximately 30 commits. main
added a measurement import system, a major frontend refactor, a new landing
page, and assorted backend improvements. Five files had conflicts.

---

## Conflict 1: `backend/app/main.py` (imports + lifespan)

### What `main` added
- `measurement_router` added to the router import line
- Startup: `_reconcile_plugin_state()` — syncs DB plugin state with actual
  Docker container state on startup (handles unclean shutdowns)
- Startup: `_cleanup_orphan_staging()` — removes stale upload staging
  directories to bound disk usage
- Shutdown: `_shutdown_all_plugin_backends()` — batch-kills all plugin
  containers before portal-backend exits

### What `main_buildout` had
- `import httpx` + `app.state.http_client = httpx.AsyncClient()` in lifespan
  — a shared connection pool so dashboard requests reuse TCP connections
  instead of opening a new one per request
- `await app.state.http_client.aclose()` on shutdown

### Resolution
All four are kept. The httpx client is needed because `dashboard.py` reads
`request.app.state.http_client` on every request. The plugin
reconcile/cleanup/shutdown hooks are correct and safe to run alongside it.
`measurement_router` added to imports.

---

## Conflict 2: `backend/app/router/dashboard.py` (response key naming)

### What `main` changed
Returned dict key changed from `"seekId"` (camelCase) to `"seek_id"`
(snake_case) in the assay and non-assay branches of
`get_dashboard_category_children`. Also restructured to use a `temp`
variable before returning (functionally identical).

### What `main_buildout` had
Used `"seekId"` (camelCase) and returned directly.

### Resolution
Used `"seek_id"` (main's version) with the direct `return {}` pattern
(our version). Rationale: `"seek_id"` is consistent with every other key in
the same file (`seek_id`, `study_seek_id`, `investigation_seek_id`, etc.),
and main's new frontend code was written expecting `seek_id`. The `temp`
variable pattern is equivalent and was dropped in favour of the cleaner
direct return.

**Note for `main`:** if `main`'s frontend already uses `seek_id` everywhere,
no change needed. If any frontend component still reads `seekId`, it should
be updated to `seek_id`.

---

## Conflict 3: `docker-compose.yml` (frontend environment variables)

### What `main` added
```yaml
- MAX_UPLOAD_MB=${MAX_UPLOAD_MB:-20480}
- MAX_PART_SIZE_MB=${MAX_PART_SIZE_MB:-16}
```
These feed into nginx `client_max_body_size` for measurement dataset uploads.

### What `main_buildout` had
```yaml
- SSL=${SSL:-false}
```
Used by the frontend nginx config to decide whether to serve HTTP or HTTPS.

### Resolution
Both kept. They are independent env vars with no interaction.

---

## Conflict 4: `frontend/entry.sh` (nginx config generation)

### What `main` added
SSL certificate auto-detection: if `${PORTAL_BACKEND_HOST}.crt` and `.key`
exist in `/etc/nginx/certs/`, the SSL nginx template is used; otherwise HTTP.
Also added `envsubst` substitution for `MAX_UPLOAD_MB` and `MAX_PART_SIZE_MB`.

### What `main_buildout` had
A commented-out `envsubst` line — the envsubst approach had been disabled and
the nginx config was being mounted as a volume directly.

### Resolution
Took main's version in full. The cert-detection logic is more robust
than the `SSL=true/false` env var approach, and it degrades gracefully: in
the `main_buildout` deployment (nginx proxy handles SSL externally, no certs
inside the container), it correctly falls back to HTTP mode. The
`MAX_UPLOAD_MB`/`MAX_PART_SIZE_MB` substitution is harmless even if those
limits aren't enforced at the container level.

---

## Conflict 5: `frontend/src/views/dashboard/study-dashboard/index.vue` (modify/delete)

### What happened
main deleted this file as part of a large dashboard refactor that
restructured views under new paths. `main_buildout` had made minor
modifications to it.

### Resolution
Accepted the deletion. main's refactor replaced the entire
`study-dashboard/` directory with a new component structure under
`frontend/src/views/dashboard/components/`. Keeping our version would
conflict with the new routing and component hierarchy.

---

## Summary table

| File | main_buildout contribution kept | main contribution kept |
|---|---|---|
| `main.py` | httpx AsyncClient pool | measurement_router, plugin reconcile/cleanup/shutdown |
| `dashboard.py` | direct return pattern | `seek_id` key name |
| `docker-compose.yml` | `SSL` env var | `MAX_UPLOAD_MB`, `MAX_PART_SIZE_MB` |
| `entry.sh` | — (superseded) | SSL cert detection + envsubst |
| `study-dashboard/index.vue` | — | deletion accepted |

---

# Part 3: Platform — Portal compose restructured from `extends` to `include`

## Background

When merging main's `entry.sh` (which now generates `/etc/nginx/conf.d/default.conf`
from a template via `envsubst`), a structural problem surfaced in the root
`docker-compose.yml`: the portal services were wired in via `extends:` rather
than `include:` like every other service (airflow, postgres, keycloak, etc.).

---

## The problem with `extends:`

`extends:` pulls individual service definitions up into the root project's
namespace. That means the root compose must also declare any volumes those
services reference. The submodule declared:

```yaml
volumes:
  portal_workspace:
    name: digitaltwins_portal_workspace
```

But the root compose had no `portal_workspace` entry, so `docker compose build`
failed with "service portal-backend refers to undefined volume portal_workspace".

A temporary fix added `portal_workspace:` to the root compose — but this
actually created a new `digitaltwins-platform_portal_workspace` volume (the
project-prefixed name Docker uses when no `name:` override is present) rather
than reusing any pre-existing data. Since portal_workspace holds only build
staging and upload temp data (not persistent user data), this was safe.

---

## The fix: switch to `include:`

The `include:` pattern (used by all other services) treats the submodule as a
self-contained sub-project. Volumes are declared and owned entirely within the
submodule's compose. The root compose never needs to know about them.

To attach the portal's services to the shared `digitaltwins` Docker network, a
`network-override.yml` is added alongside the submodule (same pattern as
`services/airflow/network-override.yml`):

**`services/portal/network-override.yml`** — attaches all portal services to
the `digitaltwins` network and declares the network as external so the
sub-project doesn't try to create it.

The root `docker-compose.yml` changes from:

```yaml
services:
  portal-backend:
    extends:
      file: ./services/portal/DigitalTWINS-Portal/docker-compose.yml
      service: portal-backend
    networks:
      - digitaltwins
  portal-frontend:
    extends:
      ...
    networks:
      - digitaltwins
```

to:

```yaml
include:
  - path:
    - services/portal/DigitalTWINS-Portal/docker-compose.yml
    - services/portal/network-override.yml
    project_directory: services/portal/DigitalTWINS-Portal
```

The temporary `portal_workspace:` entry added to root compose volumes is
removed.

---

## Other post-merge boot fixes

Two additional issues surfaced when the rebuilt portal-frontend container
first started:

1. **Read-only `default.conf` mount** — the old `main_buildout` volume mount
   `./frontend/nginx.conf:/etc/nginx/conf.d/default.conf:ro` conflicted with
   main's `entry.sh`, which writes that file at container startup. Fix:
   remove the bind mount from `docker-compose.yml`. The templates inside the
   image (`nginx.http.conf.template`, `nginx.ssl.conf.template`) are the source
   of truth; `entry.sh` generates `default.conf` from them at runtime.

2. **Missing `BACKEND_PORT` env var** — `entry.sh` calls `envsubst` with
   `${BACKEND_PORT}` but it wasn't in the portal-frontend environment block.
   Fix: added `- BACKEND_PORT=${BACKEND_PORT:-8000}` to portal-frontend's
   `environment:` in `docker-compose.yml`.

---

# Part 4: PWA service worker hijacked the Keycloak login redirect

## Symptom

After rebuilding portal-frontend, clicking **Sign In** (or navigating to any
SSO-protected service such as `/airflow`) produced a **blank black screen**.
A hard refresh (Ctrl+Shift+R) always got through; a normal reload did not.
No JavaScript console errors, and `styles.css` for the Keycloak theme never
appeared in the Network tab. `curl` of the same Keycloak auth URL returned the
correct login HTML every time.

## Root cause

The portal is a PWA (`vite-plugin-pwa` / Workbox). Its service worker uses a
`navigateFallback` to `index.html` so client-side routes resolve to the SPA
shell. A `navigateFallbackDenylist` is supposed to exempt paths that nginx
reverse-proxies to other services so the SW doesn't hijack them.

The denylist contained `/^\/realms(\/|$)/` — written for a Keycloak mounted at
the **root** (`/realms/...`). But this deployment mounts Keycloak under
`/auth` (`KC_HTTP_RELATIVE_PATH=/auth`, so the login URL is
`/auth/realms/...`). The `/realms` pattern never matched `/auth/realms`, so the
service worker intercepted the browser's redirect to the Keycloak login page and
served the cached SPA shell instead. The shell mounts Vue at an unknown
`/auth/...` route and renders nothing → black screen.

This explained every symptom: hard refresh bypasses the SW (works); the
Keycloak page never loads so its CSS is never requested; and `curl` has no
service worker so it always sees the real page.

## Fix

Extend the denylist in
`services/portal/DigitalTWINS-Portal/frontend/vite.config.ts` to cover `/auth`
and every other reverse-proxied service, not just the bare `/realms`:

```js
navigateFallbackDenylist: [
  /^\/api(\/|$)/,
  /^\/plugin(\/|$)/,
  /^\/tools(\/|$)/,
  /^\/minio-console(\/|$)/,
  /^\/auth(\/|$)/,        // Keycloak (mounted under /auth in this deployment)
  /^\/realms(\/|$)/,
  /^\/airflow(\/|$)/,
  /^\/jupyterhub(\/|$)/,
  /^\/seek(\/|$)/,
  /^\/grafana(\/|$)/,
  /^\/dtapi(\/|$)/,
  /silent-check-sso\.html$/,
  /\/[^/?]+\.[^/]+$/,
],
```

Requires a portal-frontend image rebuild (the SW is baked at build time).
Because `skipWaiting`/`clientsClaim` are set, the new SW takes over on next
load — but browsers already running the old SW must evict it once
(DevTools → Application → Clear site data, then full browser restart).

## Recommendation for `main`

If `main` ever serves Keycloak (or Airflow/JupyterHub/SEEK/Grafana) behind the
portal's nginx under a sub-path, this denylist must list those sub-paths.
The bare `/realms` entry is only correct when Keycloak is at the domain root.
Safest to keep all reverse-proxied prefixes in the denylist regardless.

---

# Part 5: nginx templates bind-mounted so config edits don't need a rebuild

## Background

Chinchien's `entry.sh` design `COPY`s `nginx.http.conf.template` and
`nginx.ssl.conf.template` into the image (Dockerfile), then at container
startup picks one (based on cert presence) and runs `envsubst` to produce
`/etc/nginx/conf.d/default.conf`.

The templates are the source of truth — but because they live *inside* the
image, **any routing change requires rebuilding the portal-frontend image**.
A `docker compose restart` alone has no effect: the container still holds the
old baked-in template. For a deployment where nginx routing is tweaked
relatively often (adding a proxied service, adjusting a location block), a full
image rebuild per edit is heavy.

## The change

Bind-mount the two host templates over their in-image paths, in the **root**
`docker-compose.yml` (the platform repo), on the `portal-frontend` service:

```yaml
  portal-frontend:
    extends:
      file: ./services/portal/DigitalTWINS-Portal/docker-compose.yml
      service: portal-frontend
    ...
    volumes:
      - ./services/portal/DigitalTWINS-Portal/frontend/nginx.ssl.conf.template:/etc/nginx/conf.d/nginx.ssl.conf.template:ro
      - ./services/portal/DigitalTWINS-Portal/frontend/nginx.http.conf.template:/etc/nginx/conf.d/nginx.http.conf.template:ro
```

`entry.sh` now reads the host copy. The new workflow is:

> edit the template → `docker compose restart portal-frontend` → entry.sh
> re-runs `envsubst` → new routing live. **No image rebuild.**

## Why this is non-invasive

- **Chinchien's submodule is untouched** — `entry.sh` and the Dockerfile are
  unchanged. The mount lives entirely in the platform repo's root compose.
- The image still bakes in working defaults, so it runs standalone (e.g. local
  dev without the platform compose) exactly as before.
- The mount is read-only (`:ro`); nginx never writes to the templates.

## Trade-off

A template typo now surfaces at **restart** (nginx fails to come up) instead of
at build time. Mitigate with `docker exec <container> nginx -t` against the
generated `default.conf`, or just watch `docker compose logs portal-frontend`
after the restart.

## Recommendation for `main`

This is purely a deployment-ergonomics improvement and is safe for `main` too.
It changes nothing about how the image is built or how `entry.sh` behaves —
it only lets operators iterate on nginx routing without a rebuild cycle.
