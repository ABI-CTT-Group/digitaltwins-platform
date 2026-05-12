# Airflow 3 — Keycloak SSO & Platform Integration

**Date:** May 2026  
**Airflow version:** 3.0.6  
**Status:** Deployed to `test.digitaltwins.auckland.ac.nz`

---

## Overview

This document describes all modifications made to integrate Airflow 3 with:

1. **Keycloak SSO** — users log into the Airflow UI with their Keycloak credentials
2. **nginx reverse proxy** — Airflow is served at `/airflow/` on port 443, no separate port required
3. **Platform token exchange** — the `digitaltwins-api` can trigger DAG runs attributed to the requesting user rather than a shared service account

---

## 1. nginx Reverse Proxy

**File:** `buildout/dev/nginx.conf`

Airflow is proxied at `/airflow/` within the existing port 443 server block alongside all other platform services.

```nginx
location /airflow/ {
    # NO trailing slash on proxy_pass.
    # This is critical: nginx must forward the full /airflow/... path to
    # airflow-apiserver. Airflow knows it lives at /airflow/ via BASE_URL
    # and handles its own prefix (base href, static assets, API routes).
    # Adding a trailing slash here strips the prefix and breaks everything.
    proxy_pass http://airflow-apiserver:8080;

    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Forwarded-Host  $host;
    proxy_set_header X-Forwarded-Port  $server_port;

    proxy_http_version 1.1;
    proxy_set_header Upgrade    $http_upgrade;
    proxy_set_header Connection "upgrade";

    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
    proxy_buffering off;
}
```

**Why no trailing slash?**  
Airflow 3 is a React SPA served by FastAPI/Starlette. It uses `<base href="/airflow/">` injected at build time via the `BASE_URL` setting. If nginx strips the `/airflow/` prefix before forwarding, all asset paths break (the SPA requests `./static/assets/index.js` which resolves relative to the base href). With no trailing slash, Airflow receives the full path and handles everything itself.

---

## 2. Airflow docker-compose Environment Variables

**File:** `services/airflow/docker-compose.yml`

Key variables added or changed from the default:

```yaml
# Airflow knows it is publicly served at this URL.
# This sets <base href="/airflow/"> in the SPA and configures the REST API root path.
AIRFLOW__API__BASE_URL: https://test.digitaltwins.auckland.ac.nz/airflow

# Proxy fix — tells Starlette/uvicorn to trust X-Forwarded-* headers from nginx
AIRFLOW__API__ENABLE_PROXY_FIX: 'true'
AIRFLOW__API__PROXY_FIX_X_FOR: '1'
AIRFLOW__API__PROXY_FIX_X_PROTO: '1'
AIRFLOW__API__PROXY_FIX_X_HOST: '1'
AIRFLOW__API__PROXY_FIX_X_PORT: '1'
AIRFLOW__API__PROXY_FIX_X_PREFIX: '1'

# Two distinct secret keys (both must be identical across all Airflow processes:
# api-server, scheduler, workers, triggerer)
AIRFLOW__API_AUTH__JWT_SECRET: ${AIRFLOW__API_AUTH__JWT_SECRET}   # signs API JWTs (HS512)
AIRFLOW__API__SECRET_KEY: ${AIRFLOW__API__SECRET_KEY}             # Flask session signing

# Keycloak OIDC client credentials
AIRFLOW_KEYCLOAK_CLIENT_ID: ${AIRFLOW_KEYCLOAK_CLIENT_ID}
AIRFLOW_KEYCLOAK_CLIENT_SECRET: ${AIRFLOW_KEYCLOAK_CLIENT_SECRET}
```

**Important:** `AIRFLOW__API_AUTH__JWT_SECRET` and `AIRFLOW__API__SECRET_KEY` are different keys for different purposes. Airflow 3 uses **HS512** (not HS256) to sign API JWTs, verified against `AIRFLOW__API_AUTH__JWT_SECRET`.

---

## 3. Keycloak SSO — webserver_config.py

**File:** `services/airflow/config/webserver_config.py`

This file configures FAB (Flask-AppBuilder) to authenticate users via Keycloak OAuth2/OIDC.

```python
AUTH_TYPE = AUTH_OAUTH
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Viewer"   # see note below
AUTH_ROLES_SYNC_AT_LOGIN = True

AUTH_ROLES_MAPPING = {
    "airflow_admin":  ["Admin"],
    "airflow_op":     ["Op"],
    "airflow_user":   ["User"],
    "airflow_viewer": ["Viewer"],
}
```

**Role mapping:** Users get Airflow roles based on their Keycloak realm roles. Assign `airflow_admin`, `airflow_op`, `airflow_user`, or `airflow_viewer` in Keycloak to control what each user can do in Airflow.

**`AUTH_USER_REGISTRATION_ROLE = "Viewer"`:** Any Keycloak user who logs in gets at least Viewer access, even without an explicit Airflow role in Keycloak. To restrict Airflow access to only users with explicit roles, change this to `"Public"` (which has no permissions). This was tested and confirmed working — users without Airflow roles see a 403 screen.

**Hairpin NAT fix:** The OIDC `authorize_url` uses the external Keycloak URL (browser-facing), but `access_token_url` and `jwks_uri` use the internal Docker hostname `http://keycloak:8080`. This is essential — from inside Docker, the server cannot reach itself via the public IP (hairpin NAT), so the external URL returns `invalid_client` for back-channel token exchange.

```python
"authorize_url":    "https://test.digitaltwins.auckland.ac.nz/auth/realms/digitaltwins/...",
"access_token_url": "http://keycloak:8080/auth/realms/digitaltwins/...",  # internal
"jwks_uri":         "http://keycloak:8080/auth/realms/digitaltwins/...",  # internal
```

**Custom security manager:** `KeycloakSecurityManager` extends FAB's security manager to extract user info (username, email, name, roles) from the Keycloak JWT claims rather than making a separate userinfo endpoint call.

---

## 4. Keycloak Token Exchange Plugin

**File:** `services/airflow/plugins/keycloak_token_exchange.py`

This plugin adds an endpoint that allows the platform API to exchange a user's Keycloak token for an Airflow JWT, so DAG runs can be triggered under the user's identity rather than the service account.

**Endpoint:** `POST https://test.digitaltwins.auckland.ac.nz/airflow/keycloak/exchange`  
**Auth:** `Authorization: Bearer <keycloak_access_token>`  
**Response:** `{"access_token": "<airflow_jwt>"}`

### Design decisions and lessons learned

**Why `fastapi_root_middlewares` and not `fastapi_apps`?**  
Airflow 3 adds a SPA catch-all route that intercepts any unmatched paths. Sub-apps registered via `fastapi_apps` are mounted *after* this catch-all in the route table and are never reached — all requests return 405 Method Not Allowed. Middleware runs *before* routing, so it intercepts the request first. This is the correct mechanism for adding new endpoints in Airflow 3 plugins.

**Why not Flask blueprints?**  
Airflow 3 runs Flask (FAB web UI) and FastAPI (REST API) in the same process via Starlette. Starlette only routes specific known paths to Flask — arbitrary new Flask blueprints are unreachable from outside.

**User lookup:** The Airflow 3 `api-server` process does not run the Flask/FAB web app, so `cached_app()` and `get_auth_manager()` are unavailable. Users are looked up directly from the FAB database using SQLAlchemy via `airflow.settings.Session`.

**JWT format:** Tokens must match what Airflow's `/auth/token` endpoint produces exactly:
```python
{
    "sub": str(user_id),      # string, not int — FAB user's integer primary key
    "iss": [],
    "aud": "apache-airflow",  # required — Airflow rejects tokens without this
    "nbf": <timestamp>,
    "exp": <timestamp>,
    "iat": <timestamp>,
}
# Algorithm: HS512
# Secret:    AIRFLOW__API_AUTH__JWT_SECRET  (NOT AIRFLOW__API__SECRET_KEY)
```

---

## 5. Platform API — Token Exchange Integration

**Files:**  
- `services/api/digitaltwins-api/app/routers/workflow.py`  
- `services/api/digitaltwins-api/src/digitaltwins/airflow/workflow.py`

When a portal user triggers a workflow, the API now:

1. Takes the user's Keycloak Bearer token from the incoming request
2. POSTs it to `/airflow/keycloak/exchange` to get a user-scoped Airflow JWT
3. Uses that JWT to trigger the DAG run
4. Falls back to the service account token if exchange fails (e.g. user not provisioned in Airflow)

```python
def _get_api_token(user_keycloak_token: str = None) -> str:
    if user_keycloak_token:
        token = _exchange_keycloak_token(user_keycloak_token)
        if token:
            return token
    return _get_service_account_token()   # fallback
```

The exchange URL is `{AIRFLOW_ENDPOINT}/keycloak/exchange` where `AIRFLOW_ENDPOINT` is the full base URL including the `/airflow` path (e.g. `https://test.digitaltwins.auckland.ac.nz/airflow`).

---

## 6. User Attribution

In Airflow 3, the `triggered_by` field on a DAG run records the *mechanism* (`rest_api`, `timetable`, etc.), not the specific user. The user identity is recorded in the event log (Browse → Event Logs in the UI) against the authenticated API call.

**Practical implication:** DAG runs in the UI do not display the triggering username inline. Attribution is auditable via the event log but is not surfaced as a prominent field on each run.

---

## 7. Access Control Summary

| User has Keycloak role | Airflow UI access | Portal workflow trigger |
|---|---|---|
| `airflow_admin` | Full admin | Yes |
| `airflow_op` | Operator | Yes |
| `airflow_user` | User | Yes |
| `airflow_viewer` | View only | Yes (via service account fallback) |
| No Airflow role | Viewer (current config) | Yes (via service account fallback) |
| No Airflow role | 403 (if `AUTH_USER_REGISTRATION_ROLE = "Public"`) | Yes (via service account fallback) |

Researchers using only the portal never need to visit the Airflow UI. Access control for them is enforced at the portal layer, not at Airflow.

---

## 8. Files Changed (Summary)

| File | What changed |
|---|---|
| `buildout/dev/nginx.conf` | Added `/airflow/` location block (no trailing slash on proxy_pass) |
| `services/airflow/docker-compose.yml` | Added BASE_URL, proxy fix, JWT secrets, Keycloak credentials |
| `services/airflow/config/webserver_config.py` | Full Keycloak OIDC config, role mapping, hairpin NAT fix |
| `services/airflow/plugins/keycloak_token_exchange.py` | New — token exchange endpoint via middleware |
| `services/airflow/plugins/keycloak_auth_manager.py` | New — custom auth manager (created but not active; see note) |
| `services/api/digitaltwins-api/app/routers/workflow.py` | Token exchange + user-scoped DAG triggering |
| `services/api/digitaltwins-api/src/digitaltwins/airflow/workflow.py` | Same, for the library version |

**Note on `keycloak_auth_manager.py`:** This file was written as an alternative approach to accept Keycloak Bearer tokens directly on Airflow API calls (bypassing the token exchange). It was not activated because it caused 403 errors in testing. It is left in the plugins directory but is not referenced in docker-compose. Do not set `AIRFLOW__CORE__AUTH_MANAGER` to `keycloak_auth_manager.KeycloakFabAuthManager` without further investigation.

---

## 9. Dockerfile

The Airflow Dockerfile (`services/airflow/Dockerfile`) was deliberately kept as close to stock as possible. No custom FAB static file patches were applied. The only additions are system packages (`vim`, `libpq-dev`, `build-essential`), the `digitaltwins` Python package, removal of the conflicting `asyncio` package, and a CWL virtual environment.

---

## 10. Remote Compute Worker

Airflow tasks (DAG execution) can be offloaded to a separate VM using Celery. The main VM runs all Airflow infrastructure (scheduler, API server, dag processor, triggerer, Redis, Postgres, MinIO). The compute VM runs only the Celery worker.

### Architecture

```
Main VM                          Compute VM
─────────────────────────        ─────────────────
airflow-apiserver                airflow-worker
airflow-scheduler                    ↕
airflow-dag-processor            (picks tasks from Redis,
airflow-triggerer                 reads/writes MinIO,
redis          ←─────────────────reports back via Postgres)
postgres (airflow)
minio
```

### Ports exposed on the main VM

The following ports must be open on the main VM and reachable from the compute VM. All are controlled via `.env` variables:

| Service | `.env` variable | Default port | Internal port |
|---|---|---|---|
| Airflow API server | `AIRFLOW_PORT` | `8002` | 8080 |
| Airflow Postgres | `AIRFLOW_POSTGRES_PORT` | `8013` | 5432 |
| Redis | `REDIS_PORT` | `8016` | 6379 |
| MinIO API | `MINIO_BIND_ADDRESS` | `8011` | 9000 |

All bind addresses default to `0.0.0.0` for prototyping. **Before production**, change these to the compute VM's specific IP address in `.env` and add UFW rules:

```bash
sudo ufw allow from <COMPUTE_VM_IP> to any port 8002
sudo ufw allow from <COMPUTE_VM_IP> to any port 8013
sudo ufw allow from <COMPUTE_VM_IP> to any port 8016
sudo ufw allow from <COMPUTE_VM_IP> to any port 8011
```

### Airflow Postgres port

Airflow's internal Postgres (separate from the platform's shared Postgres on port 8003) was not originally exposed. A port mapping was added to `services/airflow/docker-compose.yml`:

```yaml
postgres:
  ports:
    - "${AIRFLOW_POSTGRES_BIND_ADDRESS:-0.0.0.0}:${AIRFLOW_POSTGRES_PORT:-8013}:5432"
```

### Worker docker-compose.yml

The compute VM needs only:
- The `Dockerfile` (copied from `services/airflow/Dockerfile`)
- A `docker-compose.yml` (see below)
- A `.env` file with secrets
- A `dags/`, `plugins/`, `config/`, `data/`, and `logs/` directory

The `logs/` directory must exist and be writable before starting:
```bash
mkdir -p logs && chmod 777 logs
```

Worker `docker-compose.yml`:

```yaml
services:
  airflow-worker:
    build: .
    command: celery worker
    environment:
      AIRFLOW__CORE__EXECUTOR: CeleryExecutor
      AIRFLOW__CORE__AUTH_MANAGER: airflow.providers.fab.auth_manager.fab_auth_manager.FabAuthManager

      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://airflow:airflow@${MAIN_VM_IP}:${AIRFLOW_POSTGRES_PORT:-8013}/airflow
      AIRFLOW__CELERY__RESULT_BACKEND:     db+postgresql://airflow:airflow@${MAIN_VM_IP}:${AIRFLOW_POSTGRES_PORT:-8013}/airflow
      AIRFLOW__CELERY__BROKER_URL:         redis://:@${MAIN_VM_IP}:${REDIS_PORT:-8016}/0

      AIRFLOW__CORE__EXECUTION_API_SERVER_URL: http://${MAIN_VM_IP}:${AIRFLOW_PORT:-8002}/airflow/execution/

      AIRFLOW__CORE__FERNET_KEY:       ${AIRFLOW__CORE__FERNET_KEY}
      AIRFLOW__API_AUTH__JWT_SECRET:   ${AIRFLOW__API_AUTH__JWT_SECRET}
      AIRFLOW__API__SECRET_KEY:        ${AIRFLOW__API__SECRET_KEY}

      AIRFLOW_ENDPOINT: http://${MAIN_VM_IP}:${AIRFLOW_PORT:-8002}/airflow
      AIRFLOW_USERNAME: ${AIRFLOW_USERNAME}
      AIRFLOW_PASSWORD: ${AIRFLOW_PASSWORD}

      MINIO_ENDPOINT:   http://${MAIN_VM_IP}:8011
      MINIO_ACCESS_KEY: ${MINIO_ACCESS_KEY}
      MINIO_SECRET_KEY: ${MINIO_SECRET_KEY}

      DIGITALTWINS_API_BASE_URL: ${DIGITALTWINS_API_BASE_URL}
      DIGITALTWINS_API_PORT:     ${DIGITALTWINS_API_PORT}

      DUMB_INIT_SETSID: "0"

    volumes:
      - ./dags:/opt/airflow/dags
      - ./logs:/opt/airflow/logs
      - ./plugins:/opt/airflow/plugins
      - ./config:/opt/airflow/config
      - ./data:/opt/airflow/data

    user: "${AIRFLOW_UID:-50000}:0"
    restart: always
    healthcheck:
      test:
        - "CMD-SHELL"
        - 'celery --app airflow.providers.celery.executors.celery_executor.app inspect ping -d "celery@$${HOSTNAME}"'
      interval: 30s
      timeout: 10s
      retries: 5
      start_period: 30s
```

### Worker `.env` file

Copy from the main VM's `.env` and add/set:

```bash
MAIN_VM_IP=<main VM private/public IP>
AIRFLOW_POSTGRES_PORT=8013
REDIS_PORT=8016
AIRFLOW_PORT=8002
MINIO_ACCESS_KEY=minioadmin        # or your actual credentials
MINIO_SECRET_KEY=minioadmin

# These must match the main VM exactly:
AIRFLOW__CORE__FERNET_KEY=<from main .env>
AIRFLOW__API_AUTH__JWT_SECRET=<from main .env>
AIRFLOW__API__SECRET_KEY=<from main .env>
AIRFLOW_USERNAME=<from main .env>
AIRFLOW_PASSWORD=<from main .env>
DIGITALTWINS_API_BASE_URL=<from main .env>
DIGITALTWINS_API_PORT=<from main .env>
```

### DAG synchronisation

The compute VM needs the same DAGs as the main VM. Simplest approach for prototyping: clone the repo and run `git pull` when DAGs change. The worker checks for bundle updates every 30 minutes automatically.

### Stopping the main VM worker

When using a remote worker, stop the local worker on the main VM to ensure all tasks go to the compute VM:

```bash
docker compose stop airflow-worker
```

To permanently remove it from the main VM startup, add `profiles: ["worker"]` to the `airflow-worker` service in `services/airflow/docker-compose.yml` so it doesn't start by default.

### Scaling

To add more compute capacity, repeat the worker VM setup on additional VMs. Celery distributes tasks across all registered workers automatically. Each worker must have the same image, secrets, and DAGs.
