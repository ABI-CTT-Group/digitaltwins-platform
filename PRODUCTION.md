# Production hardening checklist

Things to review/change **before** running this platform in production. The
defaults here are tuned for getting a deployment *working* (dev/test/airgap
bring-up); several are deliberately permissive and must be tightened for a real
deployment.

Legend: `[ ]` to do · `[x]` done · `(verify)` = confirm current value, may
already be fine.

---

## 1. Edge exposure (gateway routes)

The browser/app only ever talks to the portal's own `/api/...`; the portal
**backend** reaches HAPI/MinIO internally on the docker network. So several
gateway routes are admin-only or redundant and should not hang off the public
edge. Edit `services/nginx/snippets/platform-routes.conf`, then
`docker exec ${PROJECT_NAME}-gateway nginx -t && nginx -s reload` (no rebuild).

- [ ] **Remove `/pgadmin/`** — a database admin GUI must never sit at the edge.
- [ ] **Remove `/fhir/`** — HAPI is served **unauthenticated**; an open
  read/write clinical-data API at the edge is a real exposure. Nothing app-side
  uses it (the backend talks to `hapi-fhir:8080` internally).
- [ ] **Remove `/minio/`** — this is the MinIO **console** (admin UI, port 9001)
  behind default creds. No app path uses it; there is already no edge route to
  MinIO's S3 API (9000).
- [ ] Admins reach these via SSH tunnel instead, e.g.
  `ssh -L 5050:pgadmin:80 -L 9001:minio:9001 -L 8080:hapi-fhir:8080 <host>`.
- [ ] **`/airflow/`** — reachable at the edge with baked-in `admin/admin` (see §3).
  Decide whether Airflow should be edge-exposed at all, or tunnel-only.

## 2. Keycloak / identity

Realm template: `services/keycloak/digitaltwins-realm.json.template` (imported on
Keycloak's first boot only — recreate the `keycloak_data` volume to re-import, or
change via the admin console on a running system).

- [ ] **Disable/remove the test users** shipped in the realm with **plaintext
  passwords**: `clinician/clinician`, `researcher/researcher`, `test1/test1`,
  `test2/test2`. Disable in the admin console, or remove them from the template
  before the realm is imported.
- [ ] **Realm admin (`admin`)** uses `KEYCLOAK_REALM_ADMIN_PASSWORD` — ensure it's
  a strong, unique secret (not a placeholder).
- [ ] **Keycloak bootstrap admin** `KC_BOOTSTRAP_ADMIN_PASSWORD` — strong secret.
- [ ] SEEK is **not** on Keycloak SSO (local-admin login only) — known/accepted;
  ensure its admin password is strong.

## 3. Default / baked-in credentials

Set every one of these to a strong value in `secrets.env` (never leave a
`:-default`):

- [ ] **Airflow** — baked `admin/admin` via FAB (`_AIRFLOW_WWW_USER_PASSWORD`,
  `AIRFLOW_PASSWORD` in `services/airflow/docker-compose.yml` / `.env`).
- [ ] **MinIO root** — `MINIO_ROOT_PASSWORD` / `MINIO_SERVER_SECRET_KEY` (compose
  falls back to `minioadmin`).
- [ ] **pgAdmin** — `PGADMIN_DEFAULT_PASSWORD` (`services/postgres/docker-compose.yml`).
- [ ] **Postgres** superuser — `POSTGRES_PASSWORD` (shared DB, user `admin`).
- [ ] **JupyterHub** — `JUPYTERHUB_CRYPT_KEY` (compose ships a hardcoded default).
- [ ] **Orthanc** — `ORTHANC_AUTH_SECRET_KEY`, `ORTHANC_AUTH_SERVICE_PASSWORD`,
  `ORTHANC_KEYCLOAK_CLIENT_SECRET`.

## 4. TLS / transport

- [ ] Real CA-signed cert in place (`data/fullchain.pem`/`privkey.pem`), not
  self-signed; `PLATFORM_PROTOCOL=https`, `NGINX_MODE=ssl`.
- [ ] **`KEYCLOAK_VERIFY_SSL`** (portal backend) — currently `false` to tolerate
  self-signed certs; set **`true`** in production with a real cert.
- [ ] Cert **renewal** process in place (Let's Encrypt / provider) — certs expire.

## 5. Secrets handling

- [ ] `secrets.env` / `env` are git-ignored and `chmod 600`; never committed.
- [ ] No secrets hardcoded in tracked templates. (Two Orthanc secrets that were
  hardcoded in the tracked `.env.template` have already been rotated — `[x]`.)
- [ ] Rotate any credential that has ever been committed or shared in plaintext.

## 6. Firewall / network

- [ ] UFW enforced (`util/airgap.sh`) — inbound only 22/80/443, egress denied,
  for an airgapped/walled deployment.
- [ ] SSH restricted (keys only, no password auth); consider limiting source IPs.

## 7. Dev/test artifacts to disable

- [ ] **`pacs_pretend_external`** — the fake "external" PACS is commented out of
  the root `docker-compose.yml` `include:`; keep it disabled in prod.
- [ ] **`_PIP_ADDITIONAL_REQUIREMENTS`** (Airflow) — dev convenience; bake deps
  into the image for prod, don't pip-install at runtime.
- [ ] Any debug/verbose logging or permissive CORS left on for development.

## 8. Data / operations

- [ ] A **backup** strategy is in place before go-live (DB dumps + MinIO +
  Orthanc); see `util/stage-dump.sh` and the legacy `buildout/util` backup
  scripts catalogued in `util/legacy-buildout-utils.md`.
- [ ] Restore has been **tested**, not just backup.

---

> This list is a starting point drawn from the current codebase; review each
> service's own config as the deployment target is finalised.
