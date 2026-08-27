# Walkthrough: Airflow API Auth Long-term Fix

## Changes Made

### 1. [docker-compose.yml](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/docker-compose.yml#L369) (Airflow)

Changed `airflow-init` to derive its username from `AIRFLOW_USERNAME` (the same variable the API uses) instead of the separate `_AIRFLOW_WWW_USER_USERNAME`:

```diff
-      _AIRFLOW_WWW_USER_USERNAME: ${_AIRFLOW_WWW_USER_USERNAME:-admin}
+      _AIRFLOW_WWW_USER_USERNAME: ${AIRFLOW_USERNAME:-admin}
```

This ensures the local FAB user created at init time always matches the credentials the `digitaltwins-api` uses to authenticate with Airflow.

### 2. [.env.template](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/.env.template) (API)

Removed the now-dead `_AIRFLOW_WWW_USER_USERNAME` and `_AIRFLOW_WWW_USER_PASSWORD` variables from the template.

## What Was Validated

- Verified no remaining functional references to `_AIRFLOW_WWW_USER_USERNAME` in the codebase (only docs/comments remain as historical context)
- The password was already aligned (`_AIRFLOW_WWW_USER_PASSWORD` already derived from `${AIRFLOW_PASSWORD:-admin}`)

## Remote Deployment Steps

After deploying this change to the remote server, you still need the **one-time immediate fix** to replace the existing OAuth-provisioned user:

```bash
docker compose exec airflow-apiserver airflow users delete -u admin1
docker compose exec airflow-apiserver airflow users create \
  --username admin1 --password 'BXfeeHe5c4694t6xVMuV' --role Admin \
  --firstname DigitalTwins --lastname Admin --email admin@digitaltwins.com
```

After that, future `docker compose up` runs will correctly create/maintain the `admin1` user via `airflow-init`.
