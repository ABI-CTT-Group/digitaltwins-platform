# Agent notes: services/api

Read the root AGENTS.md first; this file adds only what's specific to this service.

The code map, connections and config are in [README.md](README.md#developing-this-package).

## Where changes go

- **An endpoint** goes in the matching module in `app/routers/`. For a new area, create
  `app/routers/<area>.py` with `router = APIRouter(...)` and register it in `create_app()` in
  `app/main.py`. Register a router with fixed paths before one whose `/{param}` would capture them
  (`dataset_uploads` comes before `datasets`).
- **Paths never start with `/api`**: the gateway strips it and uvicorn runs with `--root-path /api`.
- **Auth** comes from `app/routers/auth.py`: `validate_credentials` (any valid token),
  `require_upload_role` (realm role `admin` or `researcher`) or `require_admin_role`. SEEK calls run
  as the caller: build clients from the request's token (`get_querier`, `get_deleter` in
  `app/routers/dependencies.py`), never from a shared token.
- **Library code** goes in `src/digitaltwins/<area>/`. It is also the published `digitaltwins`
  package and imports nothing from FastAPI; keep it that way. Request models go in `app/schemas/`.
- **A schema change** is a new file `src/digitaltwins/postgres/migrations/NNNN_<name>.sql`, numbered
  after the last one. It runs once, in its own transaction, at the next API start. Write it to be safe
  on any existing deployment (`IF NOT EXISTS`). Never edit a shipped migration or
  `services/postgres/digitaltwins_schema.sql`; a reverse change is a new migration.
- **`migration_runner.py` or `core/keycloak_verifier.py`**: copy your change byte for byte into the
  builder (`services/builder/app/database/`, `services/builder/app/client/`) in the same PR.
- **A new environment variable**: add it to `docker-compose.yml` and to the root `.env.template`
  (and `secrets.env.template` if secret), names only.

## Tests

- One file per area: `tests/test_<area>.py`. pytest runs with `--strict-markers` and
  `pythonpath = ["src", "."]`, so tests import both `digitaltwins` and `app`.
- Use the fakes in `tests/conftest.py` rather than real services: the `hapi` fixture (in-memory HAPI
  FHIR) and the `seek` fixture (in-memory SEEK `Writer`). For tokens, `tests/test_keycloak_verifier.py`
  has a stand-in realm (`FakeRealm`) that `tests/test_auth_roles.py` reuses.
- Live-service fixtures: `scratch_db`, `platform_db` (baseline plus migrations, with `POSTGRES_*`
  pointed at it), `minio_bucket`, `s3`, and `tool_bucket`, all in `tests/conftest.py`.
  A test that uses one must carry `@pytest.mark.integration`, or collection fails. `make test-api`
  deselects those tests and runs the rest offline.
- `make test-api` mounts this folder and `services/postgres` only. A test that needs another file
  from the repo won't find it there.

## Domain rules that bite

- `assay.cohort` holds the indices of the subjects to run, not a count; empty means all subjects
  (`app/routers/assays.py`).
- Tool and workflow ingest is all-or-nothing: if a step fails, the pipeline removes the SEEK entries
  and datasets it already made (`_undo` in `tools/pipeline.py`). Keep that rollback when changing
  `tools/` or `workflows/`.
- An assay run triggers the DAG `workflow_<seek_id>`. `src/digitaltwins/workflows/dag.py` checks a
  DAG before deploy; [docs/workflow-dag-authoring.md](../../docs/workflow-dag-authoring.md) is the
  contract with DAG authors.
- DAG tasks import the `digitaltwins` release pinned in `services/airflow/Dockerfile`, not this
  folder, so library changes don't reach them until that pin moves.
