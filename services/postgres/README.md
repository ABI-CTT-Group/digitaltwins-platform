# PostgreSQL

The platform's shared relational database: one `postgres:16` server, the `database` service.

## Purpose

One Postgres server holds the databases of most platform services:

| Database | Schema | Used by | Connects as |
|---|---|---|---|
| `digitaltwins` (`POSTGRES_DB`) | `public` | api: datasets, subjects, samples, assay configurations, upload sessions | the superuser (`POSTGRES_USER`) |
| `digitaltwins` | `portal` | builder: tool, workflow and plugin registry | the `portal` role, which owns only this schema |
| `airflow` | | Airflow metadata and Celery result backend | the `airflow` role |
| `keycloak` | | Keycloak | the `keycloak` role |
| `hapi` | | HAPI FHIR | the superuser |

SEEK is the exception: it keeps its own MySQL in `services/seek/ldh-deployment`.

## Status

Active. The root `docker-compose.yml` `extends` the `database` service from this folder's
`docker-compose.yml`.

`pgadmin` is defined in the same file but the root compose doesn't extend it, so it never starts
under the platform.

## Code map

The init scripts are mounted into `/docker-entrypoint-initdb.d/` under a numbered name, which sets
their order.

| Path | Mounted as | What it is |
|---|---|---|
| `docker-compose.yml` | | The `database` and `pgadmin` services |
| `digitaltwins_schema.sql` | `01_schema.sql` | A `pg_dump` of the `public` schema: the **baseline** the API's migrations build on |
| `airflow_init.sql` | `02_airflow.sql` | Creates the `airflow` role and database |
| `keycloak_init.sql` | `03_keycloak.sql` | Creates the `keycloak` role and database |
| `hapi_init.sql` | `04_hapi.sql` | Creates the `hapi` database, owned by the superuser |
| `portal_init.sh` | `05_portal.sh` | Creates the builder's `portal` role and the `portal` schema it owns, with password `BUILDER_DB_PASSWORD`. Idempotent |

## How the schemas are built and changed

Three mechanisms, in this order:

1. **Init scripts (this folder).** Postgres runs them once, on first start with an empty
   `postgres_data` volume. They never run again.
2. **The API's numbered migrations**, `services/api/src/digitaltwins/postgres/migrations/NNNN_<name>.sql`.
   The API applies pending ones to `public` at startup and records them in `public.schema_migrations`.
   They run on top of `digitaltwins_schema.sql`, both on fresh installs and on existing volumes.
3. **The builder's numbered migrations**, `services/builder/app/database/migrations/NNNN_<name>.sql`.
   The builder applies them to `portal` at startup, as the `portal` role, and records them in
   `portal.schema_migrations`.

`digitaltwins_schema.sql` is still used: it is the init script for `public`, and the API's tests
load it as the baseline before applying the migrations (`services/api/tests/conftest.py`). Don't
edit it. A change to `public` is a new API migration, or fresh and upgraded installs will diverge.

## Connects to

| Client | How |
|---|---|
| api | `POSTGRES_HOST=database`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` |
| builder | `BUILDER_DB_HOST=database`, `BUILDER_DB_PORT`, `BUILDER_DB_NAME`, `BUILDER_DB_USER=portal`, `BUILDER_DB_PASSWORD`, set in the root `docker-compose.yml` |
| Airflow | `AIRFLOW_DB_USER`, `AIRFLOW_DB_PASSWORD`, `AIRFLOW_DB_NAME` in the SQLAlchemy and Celery result-backend URLs (`services/airflow/docker-compose.yml`) |
| Keycloak | `KC_DB_URL` (`database:5432/keycloak`), `KEYCLOAK_DB_USER`, `KEYCLOAK_DB_PASSWORD` (`services/keycloak/docker-compose.yml`) |
| HAPI FHIR | `SPRING_DATASOURCE_URL` (`database:5432/hapi`), with `POSTGRES_USER` and `POSTGRES_PASSWORD` (`services/hapi-fhir/docker-compose.yml`) |

The host publishes the server on port 8003.

## Configuration

Set in the root `.env` (rendered from `.env.template`); the passwords come from `secrets.env`.

| Variable | Use |
|---|---|
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | The superuser and the main database |
| `BUILDER_DB_PASSWORD` | Required. Read only by `portal_init.sh`, for the `portal` role |
| `PGADMIN_DEFAULT_EMAIL`, `PGADMIN_DEFAULT_PASSWORD` | pgAdmin's login (pgAdmin doesn't start under the platform) |

## Run & test

This folder has no tests of its own. `make test-api` mounts it read-only, because the API's tests
load `digitaltwins_schema.sql`, and CI runs the API job when anything here changes. The API's and the
builder's Postgres integration tests each create a throwaway database (see
[docs/testing.md](../../docs/testing.md)).

## Gotchas

- **Init scripts only run on an empty volume.** Editing one changes nothing on an existing deployment.
  To add the `portal` role and schema to an existing volume, run the script by hand, as its header
  says: `docker compose exec database bash /docker-entrypoint-initdb.d/05_portal.sh`. Re-running it
  resets the role's password to `BUILDER_DB_PASSWORD`.
- **Role passwords in the SQL files are literals.** `airflow_init.sql` and `keycloak_init.sql` set the
  role passwords in the file, not from the environment. Keycloak's compose defaults match them unless
  `KEYCLOAK_DB_PASSWORD` is set. Airflow connects with `AIRFLOW_DB_PASSWORD` from `secrets.env`, and
  nothing in the repo sets the `airflow` role's password from it. Unclear how a fresh install with a
  different `AIRFLOW_DB_PASSWORD` connects; check before changing either side.
- **The API connects as the superuser** and runs its migrations with it. The `portal` role can't
  create schemas or touch `public`.
- `hapi_init.sql` creates no role: HAPI FHIR connects as the superuser.

## Related ADRs

- [Numbered SQL migrations for the platform `public` schema](../../docs/decisions/2026-09-28-platform-schema-migrations.md)
- [Move the portal database into the platform Postgres](../../docs/decisions/2026-09-28-portal-database-in-platform-postgres.md)
- [The builder migrates the `portal` schema with the API's runner](../../docs/decisions/2026-10-21-builder-numbered-sql-migrations.md)
