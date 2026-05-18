# Workflow User Attribution

## The Problem

When a user triggers a workflow from the portal, their identity is lost by the time
the workflow executes. Airflow logs show the run as initiated by the service account
(`admin`), not the actual user. This makes auditing and debugging difficult.

There are two distinct points where identity is lost, at different layers of the stack.

---

## Where Identity Is Lost

### 1. DAG run attribution in Airflow

**File:** `services/api/digitaltwins-api/src/digitaltwins/airflow/workflow.py`

When the portal triggers a workflow, the DigitalTWINS API calls the Airflow REST API
to create a DAG run. In Airflow 3, the code attempts to exchange the user's Keycloak
token for a user-scoped Airflow JWT:

```python
if user_keycloak_token:
    api_token = self.get_api_token_for_user(user_keycloak_token)

if api_token is None:
    api_token = self.get_api_token()  # falls back to service account
```

This exchange only succeeds if the user already has an account provisioned in Airflow.
Airflow provisions a user's account the first time they log into the Airflow web UI
directly via Keycloak SSO. Portal users who have never done this will not have an
Airflow account, so the exchange fails silently and the DAG run is attributed to the
service account (`AIRFLOW_USERNAME`).

**Result:** Airflow shows all workflow runs as triggered by `admin`.

### 2. Platform API calls inside the DAG

**File:** `services/airflow/dags/preprocessor.py`

Once the DAG is running, it makes calls back to the DigitalTWINS platform API (to
fetch assay configs, discover subjects, etc.). These calls authenticate using
hardcoded service account credentials:

```python
APIUSERNAME = os.environ.get("_AIRFLOW_WWW_USER_USERNAME", "admin")
APIPASSWORD = os.environ.get("_AIRFLOW_WWW_USER_PASSWORD", "admin")
```

The `dag_run.conf` does support passing `api_username` and `api_password` as
overrides, but the portal does not currently send them. All platform API calls
from within a DAG run therefore appear as `admin`, regardless of who triggered
the workflow.

**Result:** Platform API logs show all DAG-originated requests as `admin`.

---

## Current Behaviour Summary

| Stage | Identity visible | Why |
|---|---|---|
| Portal → DigitalTWINS API | ✅ Real user | User's Keycloak token is forwarded |
| API → Airflow (trigger) | ⚠️ Real user *if* provisioned | Token exchange fails for unprovisioned users |
| Airflow DAG → Platform API | ❌ Always `admin` | DAG uses service account credentials |

---

## Fixes

### Fix 1 — Provision users in Airflow (low effort, partial fix)

Ensure every portal user logs into the Airflow web UI at least once via Keycloak SSO.
This provisions their Airflow account and allows the token exchange in `workflow.py`
to succeed, so DAG runs are attributed to them correctly.

This is an operational step, not a code change. It only fixes point 1 above.

### Fix 2 — Pass user identity through the DAG conf (developer task, full fix)

To fix point 2, the portal needs to pass the user's identity in the DAG run `conf`,
and the DAG needs to use it when calling the platform API.

The infrastructure for this already partially exists — `preprocessor.py` already
reads `api_username` and `api_password` from `dag_run.conf` as overrides. The
missing pieces are:

1. **Portal/API side:** include the user's token or username in the `conf` payload
   when triggering the DAG run.
2. **DAG side:** use a short-lived token or the passed username for platform API
   calls rather than the static service account credentials.

Passing a raw password in `dag_run.conf` is not appropriate. The right approach is
to pass the user's Keycloak access token (short-lived, scoped) and have the DAG use
it for API calls. This requires the portal to forward the token at trigger time.

### Fix 3 — Rename `_AIRFLOW_WWW_USER_*` in the DAG (housekeeping)

The variable names `_AIRFLOW_WWW_USER_USERNAME` and `_AIRFLOW_WWW_USER_PASSWORD`
are misleading — they were borrowed from Airflow's init variables but are used in
the DAG for a completely different purpose (calling the platform API). They should
be renamed to something like `DIGITALTWINS_API_USERNAME` / `DIGITALTWINS_API_PASSWORD`
to make the intent clear.

---

## Related Files

| File | Role |
|---|---|
| `services/api/digitaltwins-api/src/digitaltwins/airflow/workflow.py` | Triggers DAG runs; attempts user token exchange |
| `services/airflow/dags/preprocessor.py` | DAG that calls platform API using service account |
| `services/airflow/config/webserver_config.py` | Keycloak SSO config for Airflow web UI |
| `services/airflow/docker-compose.yml` | Defines `_AIRFLOW_WWW_USER_*` for airflow-init |
