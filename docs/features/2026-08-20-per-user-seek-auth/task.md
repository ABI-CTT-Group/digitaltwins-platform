# Per-User SEEK Auth — Task Checklist

## Part 1: SEEK-side — Accept Keycloak JWT tokens
- [ ] Create `keycloak_jwt_auth.rb` initializer
- [ ] Mount it in SEEK's `docker-compose.yml`
- [ ] Restart SEEK and verify JWT auth works directly
- [ ] Sync artifacts to docs/features/

## Part 2: API-side — Pass user's token to SEEK
- [x] Modify `auth.py` to return `{username, token}` dict
- [x] Modify `seek/querier.py` to accept `api_token` parameter
- [x] Modify `core/querier.py` to pass `api_token` through
- [x] Modify `query.py` — remove global querier, add `get_querier` dependency
- [x] Modify `assay.py` — use injected querier
- [x] Modify `upload.py` — use injected querier
- [x] Modify `download.py` — update dependency type
- [x] Modify `delete.py` — update dependency type

## Part 3: Remove `SEEK_API_TOKEN` from environment
- [x] Remove from `.env`
- [x] Remove from `secrets.env`
- [x] Remove from `secrets.env.template`
- [x] Remove from API `docker-compose.yml`
- [x] Remove from `.env.template`

## Verification
- [x] Restart SEEK, test JWT auth directly with curl
- [x] Restart digitaltwins-api, test via API endpoints
- [x] Create walkthrough
