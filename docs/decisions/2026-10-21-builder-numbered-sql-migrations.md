# The builder migrates the `portal` schema with the API's numbered SQL runner

- **Date:** 2026-10-21
- **Status:** Accepted. Done as a follow-up of [2026-10-20-merge-portal-backend-into-api-codebase](2026-10-20-merge-portal-backend-into-api-codebase.md) ("one migration runner for both `public` and `portal`"). Supersedes, in part, [2026-09-28-portal-database-in-platform-postgres](2026-09-28-portal-database-in-platform-postgres.md): its `create_all` plus catch-up columns approach is replaced.

## Context

The platform's two Python services changed their tables in two different ways:

- **The API (`public`):** numbered SQL files run by `digitaltwins/postgres/migrate.py` at startup ([2026-09-28-platform-schema-migrations](2026-09-28-platform-schema-migrations.md)).
  - `public.schema_migrations` records what has run.
  - An advisory lock serialises concurrent starts.
  - Each file runs in its own transaction.
- **The builder (`portal`):** `init_db()` ran `create_all` and then four hand-written functions on every start. Each inspected the tables and ran an ALTER for whatever was missing.
  - Nothing recorded what had run.
  - The functions could add columns, constraints and enum values, but a rename or a type change needed new one-off code.
  - Their order mattered and wasn't checked. The `is_sds` backfill read `workflow_type`, so a schema created before 2026-10-02 failed at startup.

"One runner for both" can't mean one process:
- The API connects as the superuser and must never touch `portal`.
- The builder's `portal` role can't write to `public`.

So it means one mechanism, run by each service against its own schema.

The two services share no code. They have separate folders, build contexts and dependency sets ([2026-10-21-builder-as-its-own-service](2026-10-21-builder-as-its-own-service.md)).

## Alternatives Considered

### Option A: a shared internal package
Move the runner into a small package that both images install.
- Pros: a single source file.
- Cons:
  - More build plumbing than the roughly 70 lines it shares: a package folder, `additional_contexts` in both compose files, an install step in both Dockerfiles and both Makefile test images.
  - The runner is part of the published `digitaltwins` package, which would then depend on, or have to vendor, the new package.

### Option B (chosen): the same file in both services, kept identical by a test
- Pros:
  - No build changes.
  - The file needs only the standard library and a DB-API connection.
- Cons:
  - A runner change must be made in both copies.
  - Only the test keeps them together.

### Option C: Alembic for the builder
- Pros: the usual tool for SQLAlchemy models; it can autogenerate migrations.
- Cons: a second mechanism beside the API's, the opposite of the goal. The API chose numbered SQL over Alembic in 2026-09-28-platform-schema-migrations.

### Option D: leave it as it was
- Cons:
  - Renames and type changes stay impossible without one-off code.
  - Nothing records what ran.
  - The order bug above stays.

## Decision

Option B.

- **The runner:**
  - `services/api/src/digitaltwins/postgres/migration_runner.py` holds `discover` and `apply_migrations(conn, migrations_dir, schema, lock_key)`. `migrate.py` keeps its functions as wrappers for `public`.
  - The builder's copy is `services/builder/app/database/migration_runner.py`.
  - `tests/test_shared_with_api.py` checks that the copy matches byte for byte. `make test-builder` mounts the API's file, and CI runs the builder job when that file changes.
- **The builder's migrations:**
  - They live in `services/builder/app/database/migrations/NNNN_<name>.sql` and are recorded in `portal.schema_migrations`.
  - They run under the builder's own advisory-lock key (`"dtpm"`), so the API's and the builder's runs don't wait for each other.
  - They connect as the `portal` role, as before.
- **`0001_baseline.sql`:** today's schema, written to be idempotent, plus catch-up for any `portal` schema created since 2026-09-28. That covers 2026-09-28 (commit `bf7a3325`), the first Postgres schema the builder ever created, and every later shape.
  - `workflow_type` is added before the one-time `is_sds` backfill reads it.
  - Tables the models no longer define (`measurements`, `measurement_annotations`) are left alone.
- **SQLite:** used only by tests and a standalone builder. It gets its tables from `create_all` and runs no migrations.
- **Model changes:** a change to `app/models/db_model.py` that changes the schema now needs a new numbered migration.

## Consequences

- **Models and migrations must be kept in step by hand.**
  - `test_postgres_integration.py` compares the schema the migrations build with the one `create_all` builds. It also checks that the 2026-09-28 schema (`tests/fixtures/portal_2026_09_28.sql`) catches up and keeps its rows.
  - Those tests need Postgres, so CI doesn't run them, which is the same gap as the API's integration tests. Run them by hand when adding a migration (`docs/testing.md`).
- **Renames, type changes and data fixes** are now ordinary numbered migrations.
- **Schemas that the old startup code brought up to date** keep a `DEFAULT false` on `workflows.has_backend`, which that code added and `create_all` doesn't. Nothing depends on it.
- **The two copies of the runner** must change together.
