# Gateway pathway access — who can reach what

Every route below is proxied by the gateway (`services/nginx/snippets/platform-routes.conf`).
**The gateway itself does no authentication or authorization for any of them** — no
`auth_request`, no oauth2-proxy. Each backend application handles its own Keycloak
login independently, and they do not agree with each other: some let in any realm
user, some hard-gate on Keycloak group membership, and one has no auth at all.
This was audited against each service's actual config (not assumed) on 2026-09-04.

| Path | Backend | Login gate | Notes |
|---|---|---|---|
| `/seek` | SEEK (Rails) | **Open** — any authenticated realm user | `Seek::Config.omniauth_user_create` defaults `true`; auto-provisions a brand-new SEEK account for any Keycloak login, no group/role check anywhere in `SessionsController#omniauth_authentication`. What they can *see* is governed separately by project membership/sharing policy (see [[reference_seek_permission_model]] / `util/seek-user-report.sh` etc.) — that's a content question, not a login gate. |
| `/airflow` | Airflow (FAB) | **Open** — any authenticated realm user | `AUTH_USER_REGISTRATION = True` auto-creates the account. Realm roles `airflow_admin`/`airflow_op`/`airflow_user`/`airflow_viewer` map to FAB roles (`services/airflow/config/webserver_config.py`); anyone without one of those four roles still logs in, just defaults to **Viewer** (`AUTH_USER_REGISTRATION_ROLE`). So: open door, role only affects privilege level. |
| `/digitaltwins-api` | digitaltwins-api (FastAPI) | **Open** — any authenticated realm user | `auth_bearer()` (`app/routers/auth.py`) only verifies the JWT signature against the realm's public key (`verify_aud: False`) — no role/group check in the base auth dependency. |
| `/` (portal) | DigitalTWINS-Portal (FastAPI + React) | **Open** — any authenticated realm user | `get_current_user()` (`backend/app/utils/auth.py`) only validates the token via Keycloak. `require_admin`/`require_researcher`/`require_clinician` role-checking dependencies exist in the same file but are **not wired into any router** — dead code, not an active gate. |
| `/fhir` | HAPI FHIR | **NONE — no authentication at all** | No OAuth/security interceptor is configured in `services/hapi-fhir/application.yaml` (the file's only `auth:` key is commented out, and it's for SMTP subscription email, unrelated to the REST API). Anyone who can reach the gateway can call the FHIR API with no Keycloak login whatsoever. Worth a deliberate decision, not an oversight to just note. |
| `/minio` | MinIO Console | **Open login, policy-gated access** | `MINIO_IDENTITY_OPENID_CLAIM_NAME=policy`, populated by an `oidc-usermodel-realm-role-mapper` on the `minio` client mapping realm **roles** (not groups) to a MinIO IAM policy name. A user with no realm role matching a defined MinIO policy gets no bucket access. Whether MinIO's login flow rejects such a user outright or lets them into a permission-less console session was **not verified live** — check before relying on this. |
| `/orthanc-1`, `/orthanc-2` | Orthanc + `orthanc-auth-service` (third-party image) | **Open login, permission-gated access (likely)** | `services/pacs/permissions.json` defines exactly three roles — `admin` (all), `clinician` (view/download/upload/send/share/q-r), `researcher` (view/download) — matching the `/admin`, `/clinician`, `/researcher` Keycloak groups. No role for anyone outside those three is defined, so they likely get zero permissions. Exact behavior (reject at login vs. zero-permission session) depends on `orthancteam/orthanc-auth-service`'s own internals, which aren't vendored here — **not verified live.** |
| `/grafana` | Grafana (k3s, separate from compose) | **GATED — `/grafana-admin`, `/grafana-editor`, `/grafana-viewer` groups only** | `util/observability/grafana-values.yaml`: `allowed_groups: /grafana-admin,/grafana-editor,/grafana-viewer` on `auth.generic_oauth` — Grafana's `allowed_groups` is a genuine login gate (unlike Airflow's role mapping), so anyone not in one of those three groups is refused login outright, not just under-privileged. `role_attribute_path` then maps which of the three groups gives Admin/Editor/Viewer. |
| `/jupyter` | JupyterHub | **GATED — `/admin` or `/researcher` group only** | `services/jupyterhub/jupyterhub_config.py`: `allowed_groups` defaults to `{admin, researcher}` via oauthenticator's `GenericOAuthenticator`, and — per an existing comment in that file — **the `.env` override (`JUPYTERHUB_ALLOWED_GROUPS`) is silently ignored**, because `docker-compose.yml` doesn't forward it to the container; the hardcoded default is what actually runs regardless of what's set in `.env`. A user in only e.g. `/clinician` is refused login entirely — **this is the opposite of `/seek`**, despite looking superficially similar (both are Keycloak SSO logins). If you want `/jupyter` open like `/seek`, this needs an actual code/config change (widen or drop `allowed_groups`), not just an `.env` edit — the `.env` value currently does nothing. |
| `/auth` | Keycloak itself | n/a | This *is* the identity provider, not an app with its own login gate. |

## Summary by shape

- **Open to any realm user, login-wise** (content/privilege still varies): `/seek`, `/airflow`, `/digitaltwins-api`, `/` (portal).
- **Hard-gated by Keycloak group at login**: `/grafana` (`grafana-admin`/`-editor`/`-viewer`), `/jupyter` (`admin`/`researcher`).
- **Likely permission-gated rather than login-gated, not fully verified live**: `/minio`, `/orthanc-1`/`/orthanc-2`.
- **No authentication at all**: `/fhir`.

## If you want `/jupyter` to behave like `/seek`

Two real code changes needed, not just an env var:
1. Fix the `.env` wiring gap so `JUPYTERHUB_ALLOWED_GROUPS`/`JUPYTERHUB_ADMIN_USERS` actually reach the container (currently silently ignored — see the comments in `jupyterhub_config.py`), **or**
2. Change the hardcoded defaults in `jupyterhub_config.py` directly (e.g. drop `allowed_groups` entirely, or set it to include every group that should be let in).

Neither has been done — this doc only records the current state.
