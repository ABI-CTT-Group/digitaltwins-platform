# Airflow API auth regression — assay launch never reaches a workflow

**Symptom:** Launching an assay from the portal produces **no Airflow DAG run** — nothing
appears in `workflow_<id>`. No error surfaces in the UI.

**Environment where found:** `drai-staging`, branch `dev_matt` (merged `origin/main`),
Airflow 3 with `auth_manager = FabAuthManager` + Keycloak OAuth SSO.

---

## Root cause (chain)

1. The API triggers workflows in `services/api/digitaltwins-api/app/routers/assay.py`:
   - `_get_api_token()` (lines ~51–72) authenticates by **POSTing `AIRFLOW_USERNAME` /
     `AIRFLOW_PASSWORD` (username + password) to `${AIRFLOW_ENDPOINT}/auth/token`**.
   - It then POSTs to `.../api/v2/dags/workflow_{workflow_seek_id}/dagRuns` (line ~377).
   - If the token step fails, `_trigger_dag` never fires and **the launch silently produces
     no run**.

2. Airflow's auth moved to **Keycloak OAuth via FAB** (`services/airflow/config/webserver_config.py`,
   `AUTH_TYPE = AUTH_OAUTH`). Users are **auto-provisioned on first Keycloak login**
   (`AUTH_USER_REGISTRATION = True`). **OAuth-provisioned FAB users have no local password.**

3. The merge from `main` set **`_AIRFLOW_WWW_USER_CREATE: 'false'`** in
   `services/airflow/docker-compose.yml` and dropped `_AIRFLOW_WWW_USER_USERNAME` /
   `_AIRFLOW_WWW_USER_PASSWORD`. That init step previously created a **local** `admin`
   FAB user (password = `AIRFLOW_PASSWORD`, role Admin) — which is exactly the account
   `_get_api_token()` logs into.

**Result:** with the local admin no longer created, the only `admin` is the OAuth-provisioned
one, which has **no local password**. So `/auth/token` returns **`invalid credentials`** for
every value of `AIRFLOW_PASSWORD`, and no assay ever reaches a workflow.

### Secondary problem — wrong role
The auto-provisioned `admin` also landed on `AUTH_USER_REGISTRATION_ROLE = "Viewer"`
(`webserver_config.py:40`) instead of Admin, even though the realm role map is correct
(`_ROLE_MAP: airflow_admin → Admin`, `webserver_config.py:81`). FAB does not re-sync roles on
later logins by default, so a user first created before it had `airflow_admin` stays Viewer.
A Viewer cannot trigger/unpause DAGs even with a valid token.

### What is NOT the problem
- The Keycloak realm is correct and live: the `admin` user has the `airflow_admin` realm role,
  and the `airflow` client has `directAccessGrantsEnabled=true` + the `realm_access.roles`
  mapper (verified against a working system's realm export). `/auth/token` does **not** consult
  Keycloak, so setting the Keycloak admin password has no effect on the API path.

---

## Immediate fix (applied on staging to unblock)

Replace the OAuth `admin` with a local-password Admin the API can log into:

```
docker compose exec airflow-apiserver airflow users delete -u admin
docker compose exec airflow-apiserver airflow users create \
  --username admin --password '<AIRFLOW_PASSWORD value>' --role Admin \
  --firstname DigitalTwins --lastname Admin --email <addr>
```

Verify the token step now works (reproduces `_get_api_token()` exactly):

```
docker compose exec digitaltwins-api python -c "import os,requests;r=requests.post(os.environ['AIRFLOW_ENDPOINT']+'/auth/token',json={'username':os.environ['AIRFLOW_USERNAME'],'password':os.environ['AIRFLOW_PASSWORD']},timeout=30);print('HTTP',r.status_code)"
```

Expect `HTTP 200` + an `access_token`. Then unpause the DAG and re-launch.

---

## Durable fix (choose one)

**Option A — restore the local admin (matches the previously-working setup).**
Re-add to the airflow env so `airflow-init` recreates the local admin every build:
```
_AIRFLOW_WWW_USER_CREATE=true
_AIRFLOW_WWW_USER_USERNAME=admin
_AIRFLOW_WWW_USER_PASSWORD=${AIRFLOW_PASSWORD}
```
and restore the two env injections in `services/airflow/docker-compose.yml` that the merge
removed. Lowest-effort; keeps the API's password-grant path.

**Option B — move the API off password auth (cleaner long-term).**
Have the API obtain its Airflow token via **Keycloak client-credentials** using the existing
`api` service account (`service-account-api` is already in the realm) instead of
`admin` + password. Removes the dependency on a local FAB user entirely and aligns the API with
the Keycloak-only auth model. Requires a change in
`services/api/digitaltwins-api/app/routers/assay.py::_get_api_token()`.

**Also fix the role sync (independent of A/B):** so interactive Keycloak logins get the right
Airflow role, set `AUTH_ROLES_SYNC_AT_LOGIN = True` in `webserver_config.py` (and ensure users
hold `airflow_admin` in the realm before/at login), otherwise UI admins stay stuck on Viewer.

---

## How to tell which layer is failing (quick triage)

- `docker compose exec digitaltwins-api python -c "...post .../auth/token..."` → **401
  `invalid credentials`** = no local-password admin (this bug). **200** = auth OK.
- `docker compose exec airflow-apiserver airflow users list` → is `admin` present and **Admin**?
- `docker compose exec airflow-scheduler airflow dags list | grep workflow` → does
  `workflow_<id>` exist and is it unpaused? (DAGs are synced separately via `util/sync-dags.sh`,
  not by the buildout.)
- API 404 on `.../dags/workflow_XX/dagRuns` = DAG missing or the assay is linked to a different
  workflow SEEK id than the DAG that exists.

---

## Root-cause fix (shipped)

The 401 on a **fresh** build had a concrete cause: the API authenticates as
`AIRFLOW_USERNAME` (`admin1` in `.env.template`), but `airflow-init` created
`_AIRFLOW_WWW_USER_USERNAME` = `admin`, so `admin1` had no local password and every
fresh build 401'd (which is why we kept hand-creating `admin1`). Fixed in
`services/airflow/docker-compose.yml`: `_AIRFLOW_WWW_USER_USERNAME` now follows
`${AIRFLOW_USERNAME:-admin}`, so init creates the *same* local FAB user the API logs
in as. Passwords already both come from `AIRFLOW_PASSWORD`. No more manual
`airflow users create` after a rebuild; only an *already-running* box created before
this fix needs the one-liner (see *Immediate fix*).

---

## OPEN CONCERN — user identity does not reach Airflow (attribution + UI isolation)

The regression above is about auth *working*. Separately, the identity **model** has
gaps worth a deliberate design decision **before a hospital / multi-institution
deployment** — surfaced 2026-09.

**Trigger runs as a shared service account, not the user.** A user launches a workflow
from the portal with their own Keycloak JWT; the API authenticates *them* and gates
data access via SEEK **as them** (see `seek-integration.md`). But the API→Airflow
trigger uses `AIRFLOW_USERNAME`/`AIRFLOW_PASSWORD` — the shared `admin1` local FAB user.
So **every** DAG run is triggered into Airflow as `admin1`; Airflow has no record of
which user launched which run. Authorization is real (upstream, per-user); **attribution
in Airflow is not**.

**The monitor GUI has no per-user isolation.** `run_assay` returns a `monitor_url`
pointing the user straight at the Airflow **UI** (`/airflow/dags/workflow_<id>`), where
they log in as themselves via Keycloak OAuth (auto-provisioned FAB user; role from
`AUTH_ROLES_MAPPING`, default `Viewer`). Open-source Airflow's UI is **not multi-tenant**:
any authenticated user sees **all** DAGs, **all** runs, and **all task logs** — not just
their own (and there's nothing to filter on, since all runs are `admin1`'s). For
clinical / cross-institution data this is a **cross-tenant visibility problem**: pointing
end users at the Airflow GUI exposes everyone's runs and logs.

**Directions (dev-team decision):**
- **Audit (cheap):** have the API log the user→run mapping at trigger time — it knows the
  user (JWT) and the `run_id` it creates. A trail without re-architecting.
- **Isolation (the real fix):** don't expose the Airflow UI to end users. The portal
  shows a user *their own* run status (the API can map runs→users); Airflow stays an
  internal ops-only tool behind admin logins. Today's `monitor_url` does the opposite.
- **Identity to Airflow (largest):** the API gets its Airflow token via Keycloak (service
  account, or user-token exchange — "Option B" above), so identity reaches Airflow and
  per-user attribution/authorization become possible.
