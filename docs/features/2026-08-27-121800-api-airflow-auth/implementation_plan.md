# Long-term Fix: Airflow API Auth Regression

## Problem Analysis

The `digitaltwins-api` triggers Airflow DAGs by:
1. `_get_api_token()` → POSTs `AIRFLOW_USERNAME`/`AIRFLOW_PASSWORD` to Airflow's `/auth/token`
2. `_trigger_dag()` → Uses that token as `Bearer` to call Airflow's `/api/v2/dags/.../dagRuns`

This fails on the remote server for **two reasons**:

### 1. Username mismatch
- The API authenticates as `AIRFLOW_USERNAME` → currently `admin1` in [.env](file:///home/clin864/Projects/digitaltwins-platform/.env#L285)
- But `airflow-init` creates user `${_AIRFLOW_WWW_USER_USERNAME:-admin}` → defaults to `admin`
- `_AIRFLOW_WWW_USER_USERNAME` is **not set** in `.env`, so the init creates `admin`, while the API tries to log in as `admin1`

### 2. OAuth user collision
- If someone logs into the Airflow UI via Keycloak before init, an OAuth-provisioned user (no local password) is created
- `airflow-init` skips creation if a user with that name already exists → API can never authenticate

> [!CAUTION]
> **The Keycloak client-credentials approach (Option B in the earlier docs) will NOT work here.** Airflow's REST API with FAB auth manager only accepts tokens issued by its own `/auth/token` endpoint. A Keycloak JWT would be rejected — the OAuth config in `webserver_config.py` only applies to the browser UI login flow, not API Bearer token validation.

## Proposed Changes

### Airflow Docker Compose

#### [MODIFY] [docker-compose.yml](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/docker-compose.yml)

Align `airflow-init` user creation with the API's credentials by using `AIRFLOW_USERNAME` and `AIRFLOW_PASSWORD` directly:

```diff
     environment:
       <<: *airflow-common-env
       _AIRFLOW_DB_MIGRATE: 'true'
       _AIRFLOW_WWW_USER_CREATE: 'true'
-      _AIRFLOW_WWW_USER_USERNAME: ${_AIRFLOW_WWW_USER_USERNAME:-admin}
-      _AIRFLOW_WWW_USER_PASSWORD: ${AIRFLOW_PASSWORD:-admin}
+      _AIRFLOW_WWW_USER_USERNAME: ${AIRFLOW_USERNAME:-admin}
+      _AIRFLOW_WWW_USER_PASSWORD: ${AIRFLOW_PASSWORD:-admin}
       _PIP_ADDITIONAL_REQUIREMENTS: ''
```

This ensures the user created by `airflow-init` always matches the credentials the API uses.

> [!NOTE]
> This alone doesn't solve the OAuth collision problem — if an OAuth-provisioned user with the same username already exists, `airflow-init` will skip creation. But it fixes the primary username mismatch. The OAuth collision is a one-time issue that can be resolved by the immediate fix (manually deleting and recreating the user on the remote server). On fresh deployments, `airflow-init` runs before any OAuth login, so it should work correctly.

## Open Questions

> [!IMPORTANT]
> **Should we also remove `_AIRFLOW_WWW_USER_USERNAME` from other templates?** The variable `_AIRFLOW_WWW_USER_USERNAME` is still referenced in [.env.template](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/.env.template#L179) (set to `admin`). If we're now deriving it from `AIRFLOW_USERNAME`, this old variable is dead. Should I clean it up?

## Verification Plan

### Manual Verification
1. Check that `AIRFLOW_USERNAME` in `.env` matches the username `airflow-init` will create
2. On remote: apply the immediate fix (delete + recreate user as `admin1`), then deploy the updated `docker-compose.yml`
3. Trigger an assay run and confirm DAGs are created successfully
4. On a fresh local deployment: `docker compose down -v && docker compose up` and verify assay runs work
