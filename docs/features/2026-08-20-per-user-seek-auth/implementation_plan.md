# Per-User SEEK Permissions via Keycloak JWT

## Problem

The `digitaltwins-api` uses a single admin-level `SEEK_API_TOKEN` for all SEEK queries. This means every user gets the same (admin-level) view of SEEK objects, regardless of their actual SEEK permissions.

## Goal

When a user calls the `digitaltwins-api`, their Keycloak identity determines what SEEK objects they can see. If user `admin` (people/3) has access to `study/10` in SEEK, then `GET /studies` via the API returns study 10. If they don't, it doesn't.

## Design Decisions (Resolved)

| Decision | Choice |
|---|---|
| Approach | Add a Ruby initializer in SEEK to accept Keycloak JWT Bearer tokens |
| `SEEK_API_TOKEN` | Remove completely from env and code |
| Auth methods | Support both Bearer and Basic Auth (extract token from Basic exchange) |
| Auth chain position | Insert `user_from_keycloak_jwt` first (before session) |
| JWT verification | Cryptographically verify via Keycloak JWKS endpoint with caching |

---

## Proposed Changes

### Part 1: SEEK-side — Accept Keycloak JWT tokens

#### [NEW] [keycloak_jwt_auth.rb](file:///home/clin864/Projects/digitaltwins-platform/services/seek/ldh-deployment/keycloak_jwt_auth.rb)

A new Ruby initializer (~50 lines) that:
1. Monkey-patches `AuthenticatedSystem` to insert `user_from_keycloak_jwt` as the **first** auth check in the `current_user` chain
2. Extracts `Authorization: Bearer <token>` from the request
3. Fetches and caches the Keycloak realm's JWKS public keys from `KEYCLOAK_INTERNAL_URL`
4. Decodes and verifies the JWT using the `jwt` gem (RS256, already bundled)
5. Looks up the SEEK `User` via the `identities` table using `provider: 'oidc'` and `uid: <token.sub>` — the exact same mapping SEEK already uses for Keycloak SSO login
6. Returns the matched `User` or `nil` (falls through to remaining auth methods)

---

#### [MODIFY] [docker-compose.yml](file:///home/clin864/Projects/digitaltwins-platform/services/seek/ldh-deployment/docker-compose.yml)

Mount the new initializer into the SEEK container alongside the existing `keycloak_oidc.rb`:

```diff
       - ./keycloak_oidc.rb:/seek/config/initializers/keycloak_oidc.rb:ro
+      - ./keycloak_jwt_auth.rb:/seek/config/initializers/keycloak_jwt_auth.rb:ro
```

---

### Part 2: API-side — Pass user's token to SEEK

#### [MODIFY] [auth.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/auth.py)

- `auth_basic`: Return `{"username": ..., "token": access_token}` (the token from the Keycloak exchange) instead of just the username string.
- `auth_bearer`: Return `{"username": ..., "token": token}` instead of just the username string.
- `validate_credentials`: Return the dict from whichever method succeeds.
- `verify_token`: Extract username from the returned dict.

---

#### [MODIFY] [seek/querier.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/src/digitaltwins/seek/querier.py)

- Change `__init__` to accept `api_token` as a required parameter: `def __init__(self, api_token: str)`
- Remove `os.getenv("SEEK_API_TOKEN")` — the token always comes from the caller
- Remove the validation that checks `self._api_token` is set from env

---

#### [MODIFY] [core/querier.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/src/digitaltwins/core/querier.py)

- Change `__init__` to accept `api_token: str | None = None`
- Pass `api_token` to `SeekQuerier(api_token=api_token)` when SEEK is enabled

---

#### [MODIFY] [query.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/query.py)

- Remove the module-level `querier = Querier()` singleton
- Add a FastAPI dependency: `def get_querier(credentials=Depends(validate_credentials)) -> Querier` that creates a per-request `Querier(api_token=credentials["token"])`
- Update all route handlers to use `querier = Depends(get_querier)` instead of `valid = Depends(validate_credentials)`
- Export `get_querier` so other routers can import it

---

#### [MODIFY] [assay.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/assay.py)

- Import `get_querier` from `query.py` instead of the global `querier`
- Update `run_assay` to depend on `querier = Depends(get_querier)` and `credentials = Depends(validate_credentials)`
- Pass the injected `querier` into `_fetch_assay_configs` and `_discover_samples` instead of using the global
- Replace calls to the router function `get_assay()` with direct `querier.get_assay()` calls

---

#### [MODIFY] [upload.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/upload.py)

- Import `get_querier` from `query.py` instead of the global `querier`
- Update `upload_workspace_datasets` to depend on `querier = Depends(get_querier)`

---

#### [MODIFY] [download.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/download.py)

- Update `_valid` dependency to `_credentials = Depends(validate_credentials)` (type change only, no functional impact)

---

#### [MODIFY] [delete.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/delete.py)

- Update `_valid` dependency to `_credentials = Depends(validate_credentials)` (type change only, no functional impact)

---

### Part 3: Remove `SEEK_API_TOKEN` from environment

#### [MODIFY] [.env](file:///home/clin864/Projects/digitaltwins-platform/.env)

- Remove `SEEK_API_TOKEN=...` lines (lines 274-275)

#### [MODIFY] [secrets.env](file:///home/clin864/Projects/digitaltwins-platform/secrets.env)

- Remove `SEEK_API_TOKEN=...` lines (lines 25-26)

#### [MODIFY] [secrets.env.template](file:///home/clin864/Projects/digitaltwins-platform/secrets.env.template)

- Remove `SEEK_API_TOKEN=` line (line 25)

#### [MODIFY] [docker-compose.yml](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/docker-compose.yml)

- Remove `SEEK_API_TOKEN: ${SEEK_API_TOKEN:-}` (line 20)

#### [MODIFY] [.env.template](file:///home/clin864/Projects/digitaltwins-platform/.env.template)

- Remove `SEEK_API_TOKEN=${SEEK_API_TOKEN}` (line 264)

> [!NOTE]
> Documentation files (`docs/seek-integration.md`, `docs/api_examples.md`, etc.) and utility scripts (`util/generate-token.sh`, `util/airgap_build_step3.yml`, etc.) also reference `SEEK_API_TOKEN`. These should be updated to reflect the new authentication model, but I'll defer doc updates to a follow-up to keep this PR focused on the functional change.

---

## Verification Plan

### Manual Verification

1. **Restart SEEK** to load the new `keycloak_jwt_auth.rb` initializer
2. **Test SEEK directly** with a Keycloak token:
   ```bash
   TOKEN=$(curl -s -d "client_id=api" -d "client_secret=$KEYCLOAK_CLIENT_SECRET" \
     -d "grant_type=password" -d "username=admin" -d "password=admin" \
     http://localhost/auth/realms/digitaltwins/protocol/openid-connect/token | jq -r .access_token)
   
   # Should return study 10 data (admin has access)
   curl -H "Authorization: Bearer $TOKEN" -H "Accept: application/json" http://localhost/seek/studies/10
   
   # Should show the authenticated user
   curl -H "Authorization: Bearer $TOKEN" -H "Accept: application/json" http://localhost/seek/people/current
   ```
3. **Restart the digitaltwins-api** container
4. **Test the API** using Basic Auth:
   ```bash
   curl -u admin:admin http://localhost/digitaltwins-api/studies
   # Should return studies visible to the admin user
   ```
5. **Test the API** using Bearer token:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" http://localhost/digitaltwins-api/studies
   ```
6. **Negative test**: Verify a user without access to `study/10` does NOT see it in the API response
