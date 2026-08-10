# Changing a running deployment's domain (`PLATFORM_DOMAIN`)

Move an existing VM from one domain to another — e.g.
`abidigitaltwins.auckland.ac.nz` → `portal.abidigitaltwins.auckland.ac.nz` —
**in place, without dropping/reinstalling.** All data (SEEK/Postgres/MinIO
volumes, Keycloak users) is preserved.

It's more than a cert swap, because the domain is baked into a few places. Two
things are NOT a problem here (worth knowing):

- **The portal frontend does NOT need rebuilding.** It's built with a *relative*
  `VITE_KEYCLOAK_URL=/auth`, so it's domain-agnostic — no re-freeze/rebuild on a
  domain change.
- **The gateway nginx `server_name` is `_`** (catch-all), so no nginx conf edit —
  only the cert files change.

The one step people miss is **updating the Keycloak client redirect URIs** — the
realm imports on *first boot only*, so re-rendering it does nothing to a live
realm, and login breaks with `Invalid redirect_uri` until the clients are fixed.

---

## Procedure

Let `OLD` = the current domain, `NEW` = the target domain.

### 1. DNS
Point `NEW` at the VM's public IP. (Keep `OLD` resolving too until you've cut
over, if you want a fallback.)

### 2. TLS cert for `NEW`
The existing cert is for `OLD` (wrong CN/SAN), so issue one for `NEW`:
```
util/renew-cert.sh -d NEW          # platform already up (webroot, zero-downtime)
# or, cold / before install:  sudo util/issue-cert.sh NEW
```
Both drop `server.crt`/`server.key` where the gateway reads them. (`server_name _`
means nginx serves whatever cert is there for any host — but the cert must be
valid for `NEW` or browsers show a name mismatch.)

### 3. Re-render `.env` with the new domain
Set `PLATFORM_DOMAIN=NEW` in `data/env`, then:
```
util/gen-env.sh -e data/env -s data/secrets.env
```
`PLATFORM_DOMAIN` is a gen-env *input* (not an `.env` line itself); it's
substituted into the derived absolute-URL vars — `KC_HOSTNAME`,
`KEYCLOAK_PUBLIC_URL`, `PORTAL_BACKEND_HOST`, `PORTAL_KEYCLOAK_BASE_URL`,
`AIRFLOW__API__BASE_URL`, `JUPYTERHUB_PUBLIC_URL`, `ORTHANC_KEYCLOAK_URL`.
Confirm: `grep -E '^(KC_HOSTNAME|PORTAL_BACKEND_HOST)=' .env` shows `NEW`.

### 4. Recreate the services that read those vars (scoped — no rebuild)
```
docker compose up -d
```
Recreates keycloak (new `KC_HOSTNAME`), portal-backend, airflow*, jupyterhub,
orthanc, and the gateway (new cert) because their env changed. The frontend is
domain-agnostic so it doesn't need recreating for the URL, but a blanket `up -d`
is fine — just don't force-recreate SEEK unnecessarily (slow boot).

### 5. ⚠️ Update the Keycloak client redirect URIs (`OLD` → `NEW`)
The realm was imported on first boot with `OLD` baked into several clients'
**Valid redirect URIs** / **Web origins** / **post-logout URIs**. Re-rendering the
realm template does NOT touch a live realm, so you must update the clients. These
carry absolute `OLD` URLs (from `services/keycloak/digitaltwins-realm.json.template`):

| Client | URIs to fix |
|---|---|
| `portal-frontend` | redirect `https://OLD/*` → `https://NEW/*` (**the main login**) |
| `airflow` | redirect `…/airflow/auth/oauth-authorized/keycloak`; web origin |
| `jupyterhub` | redirect `…/jupyter/hub/oauth_callback`; post-logout |
| `grafana` | redirect `…/grafana/login/generic_oauth`; post-logout |
| `orthanc` | redirect `…/orthanc-1/*` |
| `seek` | redirect URIs (check the SEEK client) |

**Via the admin console** (`https://NEW/auth/` → realm `digitaltwins` → Clients →
each client → *Valid redirect URIs*, *Web origins*, *Valid post logout redirect
URIs*): replace `OLD` with `NEW`, Save.

**Or scripted with kcadm** (adapt admin creds — `KC_BOOTSTRAP_ADMIN_*` from
`secrets.env`):
```
KC=$(docker compose ps -q keycloak)
docker exec "$KC" /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 --realm master \
  --user <admin-user> --password <admin-pass>
# per client: find its id, then update the URIs, e.g. portal-frontend:
cid=$(docker exec "$KC" /opt/keycloak/bin/kcadm.sh get clients -r digitaltwins \
        -q clientId=portal-frontend --fields id --format csv --noquotes | tail -1)
docker exec "$KC" /opt/keycloak/bin/kcadm.sh update clients/$cid -r digitaltwins \
  -s 'redirectUris=["https://NEW/*"]' -s 'webOrigins=["https://NEW"]'
```
(Repeat for `airflow`, `jupyterhub`, `grafana`, `orthanc`, `seek` with their
respective paths.)

> **Alternative — full realm re-import.** Wiping + re-importing the freshly
> rendered template gets every client right in one shot, but it **destroys
> Keycloak users/sessions/config**. Only do this on a throwaway/fresh realm;
> otherwise edit the clients in place as above.

### 6. Point SEEK at the new domain
SEEK keeps its own **Site base URL** (used for absolute links + outgoing email).
Update it in SEEK admin → Settings (or `/seek` admin) to `https://NEW`.

### 7. Verify
- `https://NEW` loads the portal; login round-trips through Keycloak (no
  `Invalid redirect_uri`).
- Each sub-service that uses OAuth works: Airflow (`/airflow`), JupyterHub
  (`/jupyter`), Grafana (`/grafana`), Orthanc (`/orthanc-1`).
- Cert served for `NEW` is valid:
  `openssl x509 -in services/nginx/certs/server.crt -noout -subject -enddate`.

---

## What you do NOT need to do
- **No reinstall / no data loss.** Volumes are untouched.
- **No frontend rebuild / re-freeze** — relative `/auth` makes it domain-agnostic.
- **No nginx conf edit** — `server_name _` already matches any host.

## Rollback
If login breaks and you need to revert: set `PLATFORM_DOMAIN=OLD` in `data/env`,
re-run `gen-env.sh`, `docker compose up -d`, put the `OLD` cert back in
`server.crt`/`server.key`, and revert the Keycloak client URIs to `OLD`. (DNS for
`OLD` must still resolve.)
