# Plan: Configuration consolidation (future_refactoring item 6)

## Context

The API service reads environment variables through ~119 scattered `os.getenv()` / `os.environ`
calls across 34 files in `services/api/app/` and `services/api/src/digitaltwins/`.
- The same variable is read in up to 4 places: `POSTGRES_*` in 4 classes, `MINIO_*` in 3.
- Defaults disagree between sites. `AIRFLOW_USERNAME`/`AIRFLOW_PASSWORD` default to `admin` in
  `app/routers/assays.py` but to nothing in `airflow/workflow.py`. `KEYCLOAK_CLIENT_ID` defaults to
  `api` in the CLI but to nothing in `app/routers/auth.py`.
- `load_dotenv()` runs at import in 23 modules.
- Nothing lists what the service needs to run.

Outcome: one module, `src/digitaltwins/settings.py`, owns every env var name, type and default.
Call sites ask it for a typed, frozen settings object instead of reading the environment.

**No PyPI release needed.** Nothing outside `services/api` imports `digitaltwins` at runtime.
Airflow pins `2.0a3` but no DAG imports it, and the API image builds from local `src/`. Env var names
don't change, so a later release stays backward compatible.

## Decisions (settled with the user)

| Topic | Decision |
|---|---|
| Scope | Both `app/` and `src/digitaltwins/`. The module lives in the library, which must not import `app/` or FastAPI; `app/` imports from it. Env var names stay the same. |
| Mechanism | Stdlib frozen dataclasses. No new dependency (no `pydantic-settings`). |
| Interface | One function, `load_settings() -> Settings`, which returns nested groups: `s.postgres.host`, `s.minio.endpoint`, `s.enabled.seek`, ... |
| Read timing | Read fresh at every call, with no cache. The import-time constants in `assays.py`, `auth.py` and `chunk_store.py` move to call time. Existing `monkeypatch.setenv` tests keep working. |
| Behaviour | Pure refactor, but each variable gets one default (table below). No new startup validation. |
| `load_dotenv` | Exactly one call, at import of `settings.py`. It searches from the same directory tree as today, so it finds the same `.env`. The other calls go, except in the excluded files. |
| Excluded | `core/keycloak_verifier.py`, which must stay byte-identical with the builder's copy (`test_shared_with_api.py`). The iRODS/Gen3 dead code: `irods/`, `gen3/`, `core/uploader_gen3.py`, `core/querier_factory.py` (37 reads, not deployed or tested). |

## Interface sketch

```python
# src/digitaltwins/settings.py
load_dotenv()  # the only call in the library (excluded files aside)

@dataclass(frozen=True)
class Settings:
    enabled: Enabled          # postgres, seek, minio, airflow, gen3, irods (bools via is_truthy)
    postgres: Postgres        # host, port, db, user, password
    minio: Minio              # endpoint, access_key, secret_key
    seek: Seek                # base_url
    airflow: Airflow          # endpoint, base_url, username, password, dags_dir, deploy_timeout: float
    jupyterhub: JupyterHub    # public_url, internal_url, api_token
    keycloak: Keycloak        # base_url, realm, client_id, client_secret  (auth.py + CLI login)
    uploads: Uploads          # staging_dir: Path, max_upload_mb: int, part_size_bytes: int, manifest_max_files: int
    api_public_url: str
    fhir_endpoint: str
    builder_url: str
    workflow_timezone: str

def load_settings() -> Settings: ...   # reads os.environ every call
```

Fields mirror what call sites read today, and nothing more. Call sites keep their own checks: the
MinIO missing-var `ValueError`, `Connection(host=...)` explicit args overriding settings, and a missing
`JUPYTERHUB_API_TOKEN` raising the same error tests expect today. `is_truthy` stays in
`utils/config_loader.py`, and `settings.py` uses it.

### One default per variable (where sites disagree today)

| Variable | Today | Chosen |
|---|---|---|
| `AIRFLOW_USERNAME` / `AIRFLOW_PASSWORD` | `admin` (assays) / none (workflow.py) | none. Compose always sets them; no hard-coded credentials |
| `AIRFLOW_ENDPOINT` | default (assays) / required, `KeyError` (deploy.py) / none (workflow.py) | `http://airflow-apiserver:8080/airflow` |
| `AIRFLOW_ENABLED` | `== "true"` | `is_truthy`, like every other `*_ENABLED` flag |
| `KEYCLOAK_CLIENT_ID` | none (auth.py) / `api` (CLI) | `api` |
| `KEYCLOAK_REALM` | none (auth.py) / `""` (CLI) / `digitaltwins` (verifier) | `digitaltwins`, matching the verifier |
| `KEYCLOAK_BASE_URL` | none / `""` (CLI) | none; the CLI keeps `(x or "").rstrip("/")` |

All other defaults move over unchanged, e.g. `AIRFLOW_BASE_URL` → `http://$HOSTNAME/airflow`,
`WORKFLOW_TIMEZONE` → `$TZ` → `Pacific/Auckland`, `JUPYTERHUB_INTERNAL_URL`, `MAX_UPLOAD_MB`,
`UPLOAD_PART_SIZE_BYTES`, `UPLOAD_MANIFEST_MAX_FILES`, `AIRFLOW_DAG_DEPLOY_TIMEOUT`, `FHIR_ENDPOINT`,
`API_PUBLIC_URL`, `BUILDER_URL`, `DATASET_STAGING_DIR`.

## Steps (TDD)

Branch `refactor/api-settings` off `main`, with one commit per step (Conventional Commits).

0. **Plans**: create `docs/plans/2026-11-18-155050-config-consolidation/` with `plan.md` (this plan)
   and `tasks.md` (checklist, ticked during the work). Draft the ADR
   `docs/decisions/2026-11-18-api-settings-module.md`. It covers stdlib dataclasses vs pydantic-settings,
   reading at every call vs caching, and the module living in the library. The debt item suggested
   pydantic-settings, so a reader would ask why not.
1. **Red**: `tests/test_settings.py`
   - Defaults with an empty env, int/bool/Path coercion, and the `HOSTNAME` and `TZ` fallbacks.
   - The chosen defaults from the table above.
   - A fresh read after `setenv` (no caching).
   - Guard test: no `os.getenv`/`os.environ` in `app/` or `src/digitaltwins/` outside `settings.py`
     and the excluded files. It fails until step 3 is done.
   → `make test-api` shows the new tests failing.
2. **Green, the module**: write `src/digitaltwins/settings.py` → the settings tests pass; the guard
   test still fails.
3. **Migrate call sites**, one commit per area, running `make test-api` after each:
   - a. Postgres: `core/connection.py`, `postgres/{querier,uploader,deleter}.py`.
   - b. MinIO: `minio/{uploader,downloader,deleter}.py`.
   - c. Feature flags: `core/{querier,uploader,deleter,downloader}.py`, `app/main.py`.
   - d. SEEK: `seek/{querier,writer}.py`.
   - e. Airflow and workflows: `airflow/workflow.py`, `workflows/{deploy,dag}.py`, and the constants
     in `app/routers/assays.py`. `test_assay_notebook_launch.py:79` changes from
     `setattr(assays, "AIRFLOW_ENABLED", False)` to `monkeypatch.setenv`.
   - f. JupyterHub: `jupyterhub/hub.py`, `assays.py`.
   - g. Keycloak client: `app/routers/auth.py` (the module-level token URL becomes a function) and
     `cli/keycloak_login.py`.
   - h. Uploads and measurements: `measurements/{staging,chunk_store,jobs,fhir_service}.py`, and
     `app/routers/dataset_uploads.py`, which uses `PART_SIZE`.
   - i. `app/routers/dashboard.py` (`BUILDER_URL`).
   - Remove the `dotenv` imports and `os` imports that these changes leave unused.
   → After step i the guard test passes and the existing suite passes with no other test edits.
4. **Docs**
   - `services/api/README.md`: the config section points to `settings.py`.
   - `services/api/AGENTS.md`: in "A new environment variable", add `settings.py` as the first stop.
   - `util/BUILD-FULL-SYSTEM.md:381-384`: the recipe copies the old `assays.py` defaults; update it.
   - `docs/future_refactoring.md`: remove item 6. Add an item to remove the dead iRODS/Gen3 backends,
     with their excluded env reads. Add an item for the leftovers found but not fixed: the stale
     `./configs.ini` bind mount (`services/api/docker-compose.yml:59`), the unread `AIRFLOW_PORT`, and
     the unused `_coerce_value` in `utils/config_loader.py`.
   - `docs/codemap.md`: add `settings.py` if the library's module list names files.
   - Re-sync the plan and tasks to `docs/plans/`, and finalise the ADR.

## Verification

- `make test` and `make lint` pass, with lint compared against `main`. `make docs-check` passes, after
  `git add` of the new files.
- Guard test: `grep -rnE "os\.(getenv|environ)" services/api/app services/api/src` finds only
  `settings.py` and the excluded files.
- Live check:
  - Rebuild and restart only the API with `docker compose up -d --build api`.
  - In the container, print non-secret fields only, e.g.
    `load_settings().airflow.endpoint, .enabled, .uploads`. Never print passwords or tokens.
  - Smoke test through the gateway: sign in on the portal, list datasets (Postgres/SEEK), open the
    upload config (`max_part_size`), and launch an assay (Airflow) to confirm the wiring.
- `make gitleaks` before opening the PR.

## Not in this change

- PyPI release; Airflow pin bump.
- Startup validation of required settings.
- Deleting the iRODS/Gen3 code, the stale examples and tutorials (already listed as debt), and the
  `configs.ini` mount.
- `GLOSSARY.md`: no domain terms change, since config is implementation detail.

## Outcome: where implementation differed from the plan

- Two more tests changed besides `test_assay_notebook_launch.py`, because they patched or read the
  removed `chunk_store` module constants. `test_measurement_chunk_store.py` now sets
  `UPLOAD_MANIFEST_MAX_FILES` through `patch.dict(os.environ)`. `test_dataset_uploads_api.py`
  (integration) compares against `load_settings().uploads.part_size_bytes`.
- `settings.require(value, name)` raises `KeyError(name)` for a setting with no safe default. It keeps
  today's `KeyError("JUPYTERHUB_API_TOKEN")` in `assays.py` and `jupyterhub/hub.py`.
- `auth.py` builds the token URL inline in `get_token`, its only user, instead of in a new function.
- A malformed number now falls back to its default in every case: `MAX_UPLOAD_MB` already did, and
  `UPLOAD_PART_SIZE_BYTES`, `UPLOAD_MANIFEST_MAX_FILES` and `AIRFLOW_DAG_DEPLOY_TIMEOUT` used to raise.
- `jupyterhub/hub.py` lost its `DEFAULT_URL` constant; the default lives in `settings.py`.
- At the user's request, root `AGENTS.md` (Plans → Task Tracking) now says to keep a `tasks.md` and
  tick each item as soon as its check passes.
- Integration tests ran against a throwaway Postgres and MinIO: 215 passed.
