# Tasks: configuration consolidation

- [x] 0. Branch `refactor/api-settings` off `main`; plan and tasks in this folder; ADR drafted
- [x] Sync plans to docs/plans/
- [x] 1. Red: `tests/test_settings.py` (defaults, coercion, fallbacks, fresh read, guard test). Failed on the missing module
- [x] 2. Green: `src/digitaltwins/settings.py`. 8 passed; the guard test still failed as expected
- [x] 3a. Postgres call sites (`core/connection.py`, `postgres/*`)
- [x] 3b. MinIO call sites
- [x] 3c. Feature flags (`core/*`, `app/main.py`)
- [x] 3d. SEEK call sites
- [x] 3e. Airflow and workflows (`assays.py` constants; `test_assay_notebook_launch.py` moves to setenv)
- [x] 3f. JupyterHub (`hub.py`, `assays.py`; a missing token still raises `KeyError`)
- [x] 3g. Keycloak client (`auth.py`, CLI login)
- [x] 3h. Uploads and measurements. Also changes two tests that patched or read module constants:
      `test_measurement_chunk_store.py` (now `patch.dict(os.environ)`) and `test_dataset_uploads_api.py`
- [x] 3i. Dashboard (`BUILDER_URL`)
- [x] Guard test passes; `make test-api`: 422 passed, 1 skipped
- [x] Integration tests (throwaway Postgres and MinIO, removed afterwards): 215 passed
- [x] Agent rule: tick `tasks.md` items as each step passes (root `AGENTS.md`, at the user's request)
- [x] 4. Docs: api README, api AGENTS.md, BUILD-FULL-SYSTEM recipe, future_refactoring, codemap
- [x] Finalise ADR
- [x] Sync plans to docs/plans/
- [x] Verify: `make test` (api 422, builder 260, frontend 374, hub 5, util), `make lint` 0 findings, `make docs-check` 0 problems, gitleaks (dir scan of changed files, nothing committed yet) no leaks
- [x] Rebuild and restart `api` (healthy); settings resolve in the container; smoke test: `/api/token` (Basic → Keycloak), health, programs, datasets, upload config, and an Airflow token all OK
