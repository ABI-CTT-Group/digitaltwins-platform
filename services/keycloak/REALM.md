# DigitalTWINS Keycloak realm — reference

What lives in `digitaltwins-realm.json.template`, why, and how it maps to the
platform's services. Read this before editing the realm.

## How the template becomes a live realm

- `util/gen-realm.sh -e <env> -s <secrets>` runs `envsubst` over
  `digitaltwins-realm.json.template`, substituting **only** the platform's own
  `${VAR}` placeholders (client secrets, admin password, domain/protocol), and
  writes `services/keycloak/import/digitaltwins-realm.json` (git-ignored).
- Keycloak's own `${...}` tokens (e.g. `${client_admin-cli}`, role display names)
  are **left intact** — gen-realm only touches the platform var allow-list.
- Keycloak imports the realm **on first boot only** (empty Keycloak DB). Editing
  the template does nothing to an already-imported realm — you must re-import
  (fresh Keycloak volume) or change the live realm via the admin console / `kcadm`.
- `gen-realm.sh` **hard-fails** if any required secret var is blank in
  `secrets.env` (it greps the render for unresolved `${...}`). So every secret
  below must have a value before a build.

Realm: **`digitaltwins`** · `sslRequired = ${KC_SSL_REQUIRED}` (derived: `external`
for https, `none` for http) · self-registration disabled.

---

## Application clients (platform services)

Each is a confidential OIDC client unless noted; its secret comes from a
`secrets.env` variable and must match what the consuming service sends.

| clientId | Type / flows | Secret var | Used by (service) | Purpose |
|---|---|---|---|---|
| **`api`** | confidential · authcode + directgrant + **svcacct** | `KEYCLOAK_CLIENT_SECRET` | `digitaltwins-api` (`auth.py`), portal backend (`keycloak.py`), Airflow DAGs, compute-worker | The core **platform service client**. The API/portal authenticate users and the DAGs use client-credentials as this client. Redirect: `http://localhost/*`. |
| **`portal-frontend`** | **public** · authcode | — (public) | Portal SPA (browser) | Browser-side login for the portal UI. Redirect: `${PLATFORM_PROTOCOL}://${PLATFORM_DOMAIN}/*`. |
| **`airflow`** | confidential · authcode + directgrant | `AIRFLOW_KEYCLOAK_CLIENT_SECRET` | Airflow UI (`webserver_config.py`) | **Airflow web UI SSO.** Has the `realm roles → realm_access.roles` mapper so `airflow_*` roles reach the token. Redirect: `.../airflow/auth/oauth-authorized/keycloak`. |
| **`minio`** | confidential · authcode + directgrant | `MINIO_KEYCLOAK_CLIENT_SECRET` | MinIO (`services/minio`) | MinIO console SSO. Mapper puts realm roles into the **`policy`** claim (MinIO maps that claim → its access policy). Redirect: `.../minio/oauth_callback`. |
| **`seek`** | confidential · authcode + directgrant | `SEEK_KEYCLOAK_CLIENT_SECRET` | SEEK | SEEK login. Redirects include internal `http://seek:*/users/auth/seek/callback`. |
| **`jupyterhub`** | confidential · authcode | `JUPYTERHUB_CLIENT_SECRET` | JupyterHub | Notebook hub login. Redirect: `.../jupyter/hub/oauth_callback`. |
| **`grafana`** | confidential · authcode + directgrant + **svcacct** | `GRAFANA_OAUTH_SECRET` | Grafana | Grafana SSO. Role/permission driven by the `grafana-admin/editor/viewer` **groups** (see Groups). Redirect: `.../grafana/login/generic_oauth`. |
| **`orthanc`** | **public** · authcode + directgrant | — (public) | Orthanc PACS (user login) | **Interactive** Orthanc login flow. Mapper: realm roles → `realm_access.roles`. Redirects: `.../orthanc-1/*`, `.../orthanc-2/*`. Note: this is *not* the client that carries the Orthanc service secret — see `admin-cli`. |
| **`admin-cli`** | confidential · directgrant + **svcacct** | `ORTHANC_KEYCLOAK_CLIENT_SECRET` | Orthanc PACS **auth services** (`services/pacs`) | Keycloak built-in client **repurposed** as the Orthanc service-to-service account (`serviceAccountsEnabled`, confidential). This is what `ORTHANC_KEYCLOAK_CLIENT_SECRET` sets. ⚠️ Overloading `admin-cli` is a smell — a dedicated `orthanc-service` client would be cleaner. This is the *digitaltwins*-realm `admin-cli`, not master's, so it doesn't affect `kcadm` master logins. |

### Two Orthanc clients — don't cross them
- **`orthanc`** (public) = interactive user login to the PACS UI.
- **`admin-cli`** (confidential, `ORTHANC_KEYCLOAK_CLIENT_SECRET`) = the PACS auth
  services authenticating to Keycloak machine-to-machine.

## Keycloak built-in clients (leave alone)

`account`, `account-console`, `security-admin-console`, `broker`,
`realm-management` — standard Keycloak infrastructure clients present in every
realm export. Don't edit; they carry no platform secret (except the `admin-cli`
override above).

---

## Secret variables → clients (single source of truth)

Every secret is defined (empty) in `secrets.env.template`, given a real value in
`secrets.env`, rendered into `.env` (via `.env.template` + `gen-env.sh`) for the
consuming service, and into the realm import (via `gen-realm.sh`) for Keycloak.
The two sides must match — that's the whole point of using one variable.

| Variable | Realm client | Notes |
|---|---|---|
| `KEYCLOAK_CLIENT_SECRET` | `api` | Shared by API, portal backend, Airflow DAGs, compute-worker. |
| `AIRFLOW_KEYCLOAK_CLIENT_SECRET` | `airflow` | Airflow UI SSO only. |
| `MINIO_KEYCLOAK_CLIENT_SECRET` | `minio` | Also read by `services/minio` as `MINIO_IDENTITY_OPENID_CLIENT_SECRET`. |
| `SEEK_KEYCLOAK_CLIENT_SECRET` | `seek` | |
| `JUPYTERHUB_CLIENT_SECRET` | `jupyterhub` | |
| `GRAFANA_OAUTH_SECRET` | `grafana` | |
| `ORTHANC_KEYCLOAK_CLIENT_SECRET` | `admin-cli` | Consumed by `services/pacs` Orthanc auth services. |
| `PLATFORM_ADMIN_PASSWORD` | (the `admin` **user** password) | Not a client secret — the seeded `admin` user's password. |

> **Not in the realm:** `AIRFLOW_PASSWORD` is *not* a Keycloak secret. It's the
> local Airflow (FAB) admin password the `digitaltwins-api` uses for
> `/auth/token`. See the airflow auth notes below.

---

## Realm roles

| Role | Meaning |
|---|---|
| `airflow_admin` / `airflow_op` / `airflow_user` / `airflow_viewer` | Mapped to Airflow's Admin/Op/User/Viewer by `webserver_config.py` (`_ROLE_MAP`) at login. Granting `airflow_admin` is what makes a user an Airflow admin (can trigger/unpause DAGs). |
| `admin`, `clinician`, `researcher` | Platform/domain roles (see Groups). |
| `consoleAdmin` | Keycloak console admin. |
| `default-roles-digitaltwins`, `offline_access`, `uma_authorization` | Keycloak defaults. |

## Groups

| Group | realmRoles | Notes |
|---|---|---|
| `/admin` | `admin` | |
| `/clinician` | `clinician` | |
| `/researcher` | `researcher` | |
| `/grafana-admin`, `/grafana-editor`, `/grafana-viewer` | — | Group membership drives Grafana's role via the `grafana` client. |

## Seeded users

Passwords are in the realm import (redacted on export); the `admin` user's
password is `${PLATFORM_ADMIN_PASSWORD}`. Interactive users get their
Airflow role re-synced on each login (`AUTH_ROLES_SYNC_AT_LOGIN = True`).

| User | realmRoles | Groups | Purpose |
|---|---|---|---|
| `admin` | `airflow_admin`, `consoleAdmin`, `default-roles-*` | all | Primary admin; airflow admin. |
| `test1` | all `airflow_*` + defaults | all | Test/superuser. |
| `test2` | defaults | `/researcher` | Test researcher. |
| `clinician` | (via group) | `/clinician` | Sample clinician. |
| `researcher` | (via group) | `/researcher` | Sample researcher. |
| `service-account-api` | `airflow_admin`, defaults | — | Service account for the `api` client's client-credentials grant. Has `airflow_admin` so the API can drive Airflow as a service (client-credentials path). |
| `service-account-grafana` | defaults | — | Service account for the `grafana` client. |

---

## Role → application mapping (where the claims are consumed)

- **Airflow:** `webserver_config.py` reads `realm_access.roles`, maps `airflow_*`
  → Airflow roles. The `airflow` client's role mapper puts them in the token.
- **MinIO:** the `minio` client maps realm roles into the **`policy`** claim;
  MinIO's `MINIO_IDENTITY_OPENID_CLAIM_NAME=policy` turns that into its access policy.
- **Grafana:** driven by `grafana-*` group membership.
- **Orthanc:** the public `orthanc` client exposes `realm_access.roles` for the
  PACS authorization logic.

---

## Operational gotchas (learned the hard way)

- **First-boot import only.** Template edits don't reach a running realm. To pick
  up a new/changed client you re-import (fresh Keycloak DB volume) or apply the
  change live via `kcadm`/console.
- **Missing secret ⇒ build stops.** `gen-realm.sh` errors on any unresolved
  `${..._SECRET}` / `${..._PASSWORD}`. Set every var in `secrets.env` first.
- **Airflow API auth is separate from Keycloak.** `digitaltwins-api` gets its
  Airflow token via **username/password** against Airflow's `/auth/token`, which
  validates a **local FAB user** — *not* Keycloak. That user is (re)created by
  `_AIRFLOW_WWW_USER_CREATE: 'true'` with password `${AIRFLOW_PASSWORD}`. If it's
  missing, assay launches fail with `invalid credentials` no matter what Keycloak
  says. See `docs/airflow-api-auth-regression.md`.
- **Direct-access-grants** are enabled on several clients (`airflow`, `minio`,
  `seek`, `api`, `admin-cli`) so machine/password flows can mint tokens.
- **Client-secret ↔ service env must match.** Because both sides read the same
  `secrets.env` variable, they match by construction — don't hand-edit one side.
