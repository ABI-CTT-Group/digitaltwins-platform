# Fix 401 Unauthorized Error in Airflow Preprocessor DAG

## Problem

The `fetch_assay_configs` task in the preprocessor DAG fails with `401 Unauthorized` when calling `POST http://digitaltwins-api:8000/token`.

### Root Cause

The DAG uses `_AIRFLOW_WWW_USER_PASSWORD` (Airflow web UI password) as the credential to authenticate against the platform API's `/token` endpoint ([preprocessor.py:60-61](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/preprocessor.py#L60-L61)). That endpoint performs a Keycloak `password` grant, so it needs valid **Keycloak user** credentials — not Airflow's web password.

On **local dev**, both happen to be `"admin"` so it works by coincidence. On **remote**, `_AIRFLOW_WWW_USER_PASSWORD` differs from any Keycloak user password → 401.

### The Trigger Flow

```
User → POST /assays/{id}/run (API, authenticated via Keycloak)
  → API triggers Airflow preprocessor DAG via Airflow REST API
    → DAG calls POST /token on the platform API (needs Keycloak credentials) ← FAILS HERE
    → DAG calls GET /assays/{id}?get_configs=true (needs Bearer token)
    → DAG calls GET /datasets/{uuid}/samples (needs Bearer token)
```

The DAG needs to call back into the platform API, but currently must independently authenticate.

---

## Options Analysis

### Option A: Store Keycloak user password in env vars

Add `DIGITALTWINS_API_USERNAME` / `DIGITALTWINS_API_PASSWORD` env vars that hold a real Keycloak user's credentials.

| Pros | Cons |
|---|---|
| Simple, minimal code change | A real user's password stored in plaintext in `.env` |
| Works immediately | Password rotation requires redeploying Airflow |
| | Ties Airflow to a specific user account |

### Option B: Use Keycloak client_credentials grant (Recommended)

The `api` Keycloak client already has `serviceAccountsEnabled: true` ([realm export](file:///home/clin864/Projects/digitaltwins-platform/services/keycloak/archive/realm-cc-digitaltwins_20260715.json#L764-L784)). This means we can obtain a token using the **client_credentials** grant — no user password needed. The Airflow containers already have access to `KEYCLOAK_CLIENT_ID` and `KEYCLOAK_CLIENT_SECRET` (used by the API service).

The DAG would call Keycloak's token endpoint **directly** (bypassing the API's `/token` proxy) with:
```
grant_type=client_credentials
client_id=api
client_secret=<KEYCLOAK_CLIENT_SECRET>
```

| Pros | Cons |
|---|---|
| No user password stored anywhere | Slightly more code in the DAG |
| Uses existing `KEYCLOAK_CLIENT_SECRET` (already in `.env`) | DAG calls Keycloak directly instead of through the API |
| Standard OAuth2 machine-to-machine pattern | Service account may need role mappings in Keycloak |
| No password rotation issues | |

### Option C: Pass the user's token through DAG conf

The API's `run_assay` endpoint already has the authenticated user. We could pass their Bearer token in the DAG run conf so the DAG reuses it.

| Pros | Cons |
|---|---|
| No stored credentials at all | Token expires (typically 5 min) — DAG may outlive it |
| Respects per-user permissions | Token is persisted in Airflow's DAG run metadata (security risk) |
| | Refresh token handling adds significant complexity |

---

## Recommendation

> [!IMPORTANT]
> **Option B (client_credentials grant) is recommended.** It avoids storing any user password, uses credentials already available in the platform, and follows standard OAuth2 machine-to-machine patterns. The `api` client's service account in Keycloak already exists.

## Proposed Changes (Option B)

### Preprocessor DAG

#### [MODIFY] [preprocessor.py](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/preprocessor.py)

1. Replace `_get_api_token()` to use the Keycloak client_credentials grant directly instead of the API's `/token` proxy
2. Replace `_AIRFLOW_WWW_USER_*` env vars with `KEYCLOAK_*` env vars

```diff
-# Credentials for the digitaltwins platform API (via Keycloak Basic auth)
-APIUSERNAME: str = os.environ.get("_AIRFLOW_WWW_USER_USERNAME", "admin")
-APIPASSWORD: str = os.environ.get("_AIRFLOW_WWW_USER_PASSWORD", "admin")
+# Keycloak service-account credentials (client_credentials grant)
+KEYCLOAK_TOKEN_URL: str = os.environ.get(
+    "KEYCLOAK_TOKEN_URL",
+    f'{os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth")}'
+    f'/realms/{os.environ.get("KEYCLOAK_REALM", "digitaltwins")}'
+    "/protocol/openid-connect/token",
+)
+KEYCLOAK_CLIENT_ID: str = os.environ.get("KEYCLOAK_CLIENT_ID", "api")
+KEYCLOAK_CLIENT_SECRET: str = os.environ.get("KEYCLOAK_CLIENT_SECRET", "")
```

```diff
-def _get_api_token(api_base: str, username: str, password: str) -> str:
-    """Return a Bearer token for the digitaltwins platform API."""
+def _get_api_token() -> str:
+    """Obtain a Bearer token via Keycloak client_credentials grant."""
     import requests
-    from requests.auth import HTTPBasicAuth
-
-    token_url = f"{api_base}/token"
     resp = requests.post(
-        token_url,
-        auth=HTTPBasicAuth(username, password),
+        KEYCLOAK_TOKEN_URL,
+        data={
+            "grant_type": "client_credentials",
+            "client_id": KEYCLOAK_CLIENT_ID,
+            "client_secret": KEYCLOAK_CLIENT_SECRET,
+        },
         timeout=15,
     )
     resp.raise_for_status()
     token = resp.json().get("access_token")
     if not token:
-        raise ValueError(f"No access_token in response from {token_url}: {resp.json()}")
+        raise ValueError(f"No access_token in Keycloak response: {resp.json()}")
     return token
```

Update call sites in `fetch_assay_configs` and `discover_subjects` to use the new signature (no args):

```diff
-        token = _get_api_token(
-            api_base,
-            conf.get("api_username", APIUSERNAME),
-            conf.get("api_password", APIPASSWORD),
-        )
+        token = _get_api_token()
```

---

### Airflow Docker Compose

#### [MODIFY] [docker-compose.yml](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/docker-compose.yml)

Pass Keycloak env vars into Airflow containers (these are already defined in the root `.env`):

```diff
     AIRFLOW_PASSWORD: ${AIRFLOW_PASSWORD}
+    KEYCLOAK_INTERNAL_URL: ${KEYCLOAK_INTERNAL_URL:-http://keycloak:8080/auth}
+    KEYCLOAK_REALM: ${KEYCLOAK_REALM:-digitaltwins}
+    KEYCLOAK_CLIENT_ID: ${KEYCLOAK_CLIENT_ID:-api}
+    KEYCLOAK_CLIENT_SECRET: ${KEYCLOAK_CLIENT_SECRET}
```

> No changes to `.env.template` or `.env` — all these variables already exist there.

---

## Open Questions

> [!IMPORTANT]
> **Service account role mappings:** The `api` client's service account needs sufficient roles/permissions in Keycloak to access `GET /assays/{id}` and `GET /datasets/{uuid}/samples`. These endpoints use `validate_credentials` which just checks for a valid token — it doesn't check roles. So this should work out of the box. Can you confirm the remote Keycloak realm's `api` client still has `serviceAccountsEnabled: true`?

## Verification Plan

### Manual Verification
1. After applying changes, run `docker compose config` on the Airflow compose to verify the new Keycloak env vars appear
2. Verify the `api` Keycloak client has `serviceAccountsEnabled: true` on the remote server (Keycloak Admin Console → Clients → api → Settings → Service accounts roles)
3. Redeploy and trigger the preprocessor DAG — confirm `fetch_assay_configs` completes without 401
