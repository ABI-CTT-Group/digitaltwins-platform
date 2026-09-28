# Numbered SQL migrations for the platform `public` schema

- **Date:** 2026-09-28
- **Status:** Accepted

## Context

The platform schema (`public` in the `digitaltwins` database) is defined only by `services/postgres/digitaltwins_schema.sql`. That file is an init script, so it runs only on an **empty** data volume, and there is no way to change the schema of an existing deployment.

The unified measurement ingest needs new tables (`upload_session`, `dataset_fhir_annotation`) and new columns on `dataset` (`fhir_status`, `fhir_failure_message`). More schema changes are likely.

digitaltwins-api and the `digitaltwins` library use raw `psycopg2`, not SQLAlchemy, and connect as the Postgres admin user.

## Alternatives Considered

### Option A: numbered SQL files, applied by the API at startup (chosen)
- `src/digitaltwins/postgres/migrations/NNNN_*.sql`, each run in its own transaction.
- Serialized with `pg_advisory_lock`.
- Applied versions recorded in `schema_migrations(version, applied_at)`.
- Can also be run by hand with `python -m digitaltwins.postgres.migrate`.
- Pros:
  - No new dependency, and it fits the raw-SQL codebase.
  - Upgrades existing volumes automatically.
  - The SQL can be reviewed as it is.
- Cons: about 60 lines of our own runner, and no automatic down-migrations.

### Option B: Alembic
- Pros: an industry standard, with down-migrations and tooling.
- Cons:
  - Adds SQLAlchemy and Alembic to a codebase that uses neither.
  - Autogenerate is useless without models, so the migrations would be raw `op.execute` SQL anyway.

### Option C: edit the init SQL and reset dev databases
- Pros: no mechanism needed.
- Cons: every existing deployment would have to wipe its Postgres volume. That is unacceptable once any deployment holds real data.

## Decision

Option A. The existing `digitaltwins_schema.sql` remains the **baseline** and is not edited. Migrations are applied on top of it, both on fresh installs (after the init SQL) and on existing volumes.

## Consequences

- Schema changes ship with the API code that needs them, in the same PR.
- Every migration must be safe to apply on top of the baseline, and should use `IF NOT EXISTS` where possible.
- There are no automatic rollbacks. A reverse change is a new forward migration.
- If an init-time baseline change is ever needed, it has to be made as a migration too, or fresh installs and upgraded installs will diverge.
- The runner needs DDL rights. The API currently connects as the admin user; if that is ever reduced, migrations will need a separate privileged connection.
