# The builder

The builder is the portal's tool and workflow builder: the Tool Hub's register, build, approve and deploy steps. It used to be the portal backend (`services/portal/backend`, service `portal-backend`). It runs as the `builder` service, separate from the platform API (`services/api`), and shares no code with it. Why it is separate: [ADR 2026-10-21-builder-as-its-own-service](../../docs/decisions/2026-10-21-builder-as-its-own-service.md).

## Layout

| Path | What |
|---|---|
| `app/main.py` | The FastAPI app (`app.main:app`): startup reconcile, plugin shutdown hook, CORS |
| `app/router/` | `/api/builder/tools/...` and `/api/builder/workflow/...` |
| `app/engine/` | Build and deploy: source acquisition, Vite patching, `npm`/`yarn` builds, SPARC datasets, `docker compose` deploys, nginx plugin routes, live logs |
| `app/services/` | Approval handoff: uploads a build to the platform API as the user |
| `app/models/`, `app/database/` | SQLAlchemy models of the `portal` schema, and its numbered SQL migrations (`app/database/migrations/`) |
| `app/client/` | Keycloak, MinIO and HAPI FHIR clients |
| `app/cli/` | One-off commands, run in the builder container: `python -m app.cli.<name>` |
| `tests/` | Unit tests (`make test-builder`) |
| `requirements.txt`, `requirements-test.txt` | Its dependencies, pinned to the versions the tests run against |
| `Dockerfile` | Python 3.11 plus git, Node 22, yarn and the Docker CLI with the compose plugin |
| `docker-compose.yml` | Its service definition, which the root `docker-compose.yml` extends |

## The security boundary

The builder runs untrusted code. A build clones the user's repository and runs `npm install` and the plugin's build command. A deploy runs the plugin's own `docker-compose.yml` against the host Docker socket. Every step inherits the builder's environment, minus `BUILDER_DB_*`. So:

- Only `builder` mounts `/var/run/docker.sock`; the API never does.
- `builder` gets no API credentials (`POSTGRES_*`, `JUPYTERHUB_*`, `AIRFLOW_*`, `SEEK_*`, `API_PUBLIC_URL`, `KEYCLOAK_CLIENT_SECRET`). It connects to Postgres as the `portal` role, which owns only the `portal` schema.

`tests/test_service_separation.py` checks this in the compose files. Separate folders and images keep the code apart. Builds are not sandboxed: anything that can run a build can reach the host Docker daemon.

The builder and the API talk over HTTP, as the calling user:

- The builder's approval handoff uploads builds to the API (`API_BASE_URL`/`API_PORT`).
- The API's dashboard asks the builder which tool backs a GUI assay (`BUILDER_URL`, `GET /api/builder/workflow/gui-tool`).

## Configuration

| Variable | Use |
|---|---|
| `BUILDER_DB_HOST`, `BUILDER_DB_PORT`, `BUILDER_DB_NAME`, `BUILDER_DB_USER`, `BUILDER_DB_PASSWORD` | Postgres (`portal` role and schema). With `BUILDER_DB_HOST` unset, SQLite at `DATABASE_PATH` |
| `PLATFORM_DOMAIN`, `SSL` | Public host and scheme in generated URLs and the CORS origin |
| `KEYCLOAK_BASE_URL`, falling back to `KEYCLOAK_PUBLIC_URL` | Where token signatures are checked |
| `BUILDER_PORT` | The port portal-frontend's nginx proxies `/api/builder/` to |

Plugin compose files interpolate against the builder's environment. `MINIO_SERVER_*`, `PROJECT_NAME` and `SSL` are the names plugins may rely on.

## Database migrations

On Postgres, the builder applies `app/database/migrations/NNNN_<name>.sql` at startup and records each one in `portal.schema_migrations`. The runner is a verbatim copy of the platform API's, `services/api/src/digitaltwins/postgres/migration_runner.py`. `tests/test_migration_runner.py` fails if the two differ, so change both together. Why: [ADR 2026-10-21-builder-numbered-sql-migrations](../../docs/decisions/2026-10-21-builder-numbered-sql-migrations.md).

To change the schema:

1. Change the model in `app/models/db_model.py`.
2. Add the next numbered file, for example `0002_<what>.sql`, with the matching SQL. Qualify names with `portal.`. Each file runs in one transaction; never edit a file that has shipped.
3. Run the Postgres tests, `tests/test_postgres_integration.py`, against a throwaway `postgres:16` (see its docstring). CI skips them. They check that the migrations build the schema the models describe.

SQLite, used by the unit tests and a standalone builder, gets its tables from the models and runs no migrations.

## Running it

Under the platform: `docker compose up -d builder`, from the repository root. To rebuild after a code change: `docker compose build builder && docker compose up -d builder`.

Restarting the builder stops every plugin backend it started and marks it down. Redeploy them afterwards.

Tests: `make test-builder`, from the repository root (see `docs/testing.md`). Never run them inside the live `builder` container: they drop and recreate every table.
