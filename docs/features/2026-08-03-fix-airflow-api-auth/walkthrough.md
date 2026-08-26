# Walkthrough: Fix Airflow Preprocessor 401 Auth Error

## Summary

Switched the preprocessor DAG from using Airflow web UI credentials (`_AIRFLOW_WWW_USER_PASSWORD`) for platform API authentication to a Keycloak **client_credentials grant** using the existing `api` client's service account.

## Changes Made

### [preprocessor.py](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/preprocessor.py)

- **Replaced `_get_api_token()`** — now calls Keycloak's token endpoint directly with `grant_type=client_credentials` instead of proxying through the API's `/token` endpoint with Basic auth
- **Replaced env vars** — removed `_AIRFLOW_WWW_USER_USERNAME` / `_AIRFLOW_WWW_USER_PASSWORD` usage, replaced with `KEYCLOAK_INTERNAL_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`
- **Updated both call sites** in `fetch_assay_configs` and `discover_subjects` — `_get_api_token()` now takes no arguments

### [docker-compose.yml](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/docker-compose.yml)

- Added `KEYCLOAK_INTERNAL_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET` to the `x-airflow-common` environment block so they're available inside Airflow containers

## What Was Tested

- Python syntax verification passed (`ast.parse`)

## Deployment Notes

> [!IMPORTANT]
> On the remote server, ensure `KEYCLOAK_CLIENT_SECRET` is set correctly in the `.env` file. This is the secret for the `api` Keycloak client — the same value already used by the API service (`KEYCLOAK_CLIENT_SECRET` in `.env.template` line 280).

No new env vars need to be added to `.env` — all `KEYCLOAK_*` variables already exist there. They're now just forwarded to the Airflow containers as well.
