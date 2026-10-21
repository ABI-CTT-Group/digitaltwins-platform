# Plan: one migration runner for `public` and `portal`, and keep the Keycloak secret out of plugin builds

## Context

The [2026-10-20 ADR](docs/decisions/2026-10-20-merge-portal-backend-into-api-codebase.md) lists two consistency follow-ups: one migration runner for `public` and `portal`, and one Keycloak verifier. You chose **migrations first**. The verifier comes later, as its own plan, and will be **tightened**: check the issuer and `azp`, verify TLS, retry when the key rotates, answer 503 when Keycloak is down, and send a generic 401 message.

**Today:**
- **API (`public`):** numbered SQL files, run by [migrate.py](services/api/src/digitaltwins/postgres/migrate.py) at startup.
  - `public.schema_migrations` records what has run.
  - A Postgres advisory lock stops two processes migrating at once.
  - Each file runs in its own transaction.
- **Builder (`portal`):** [database.py](services/builder/app/database/database.py) `init_db()` runs on every start.
  - It runs `create_all`, then four hand-written functions that inspect the tables and ALTER what is missing.
  - Nothing records what has run, and there is no lock.
  - It can only add things, not rename or change types.
  - It also runs on SQLite.

**What "one runner" means here:**
- It means the same mechanism, run separately by each service, with a `schema_migrations` table in each schema.
- It can't mean a single process. The API connects as the superuser and must never touch `portal`, and the `portal` role can't write to `public`.

**Found during review, and folded into this branch as its own commit:**
- The builder receives `KEYCLOAK_CLIENT_SECRET`, but uses it only to create a `KeycloakAdmin` that nothing calls.
- Plugin builds inherit every variable except `BUILDER_DB_*` ([proc_stream.py:42](services/builder/app/engine/proc_stream.py#L42)), so untrusted build code can read the secret.

## Decisions

- **Sharing: one runner file in two places, kept identical by a test.**
  - The runner's core (`discover`, `apply_migrations`) moves into a stdlib-only module in the API, with the schema name and lock key as parameters.
  - The builder gets a byte-identical copy.
  - A builder unit test compares the two files. `make test-builder` already mounts API files read-only, so this needs no new CI check.
  - Not chosen:
    - a shared package: it needs more build plumbing than the code it shares, and the published `digitaltwins` package would gain a dependency
    - installing `digitaltwins` in the builder: it brings back the dependency coupling the 2026-10-21 ADR removed
    - Alembic: a second mechanism, which is the opposite of the goal
- **SQLite: tests only.**
  - On SQLite, `init_db` keeps using `create_all` and runs no migrations.
  - Migrations run on Postgres only.
  - The SQLite-to-Postgres copy tool only reads SQLite, so it is unaffected.
- **Older deployments may exist** (your answer). So the first migration both creates today's schema and brings any schema created since 2026-09-28 up to date.
- **Lock keys:** the builder uses its own advisory-lock key, so the API's and the builder's runs don't wait for each other.

## Steps

The work goes on a new branch, `feat/builder-sql-migrations`, cut from `main`. Each numbered step is one atomic commit, and each is written test-first.

0. **Sync this plan** to `docs/artifacts/<YYYY-MM-DD-HHMMSS>-builder-sql-migrations/plan.md`.
   - Use repo-relative paths only, with no secrets.
   - Check: `gitleaks detect --source docs/artifacts/ --no-git`.

1. **`fix(builder)`: keep the Keycloak client secret out of the builder.**
   - Red: in [test_service_separation.py](services/builder/tests/test_service_separation.py), extend `API_ONLY` to cover `^KEYCLOAK_CLIENT_SECRET$`. The test should fail.
   - Green:
     - Remove the variable from [services/builder/docker-compose.yml:55](services/builder/docker-compose.yml#L55).
     - In [keycloak.py](services/builder/app/client/keycloak.py), remove `client_secret`, the `client_secret_key` argument and the `KeycloakAdmin` block (lines 23, 45-67) and its import. `verify_token` only needs the realm's public key.
     - Update [test_keycloak_config.py](services/builder/tests/test_keycloak_config.py) if it still sets the variable.
   - Check: `make test-builder`. Grep the repo for builder-side uses of `KEYCLOAK_CLIENT_SECRET`, including the README and `.env` templates.

2. **`refactor(api)`: move the runner core into `digitaltwins/postgres/migration_runner.py`.**
   - Its signature becomes `discover(dir)` and `apply_migrations(conn, migrations_dir, schema, lock_key)`. The table name is `{schema}.schema_migrations`.
   - [migrate.py](services/api/src/digitaltwins/postgres/migrate.py) keeps `MIGRATIONS_DIR`, `run()` and `main()`. It also keeps thin wrappers, `discover(migrations_dir=MIGRATIONS_DIR)` and `apply_migrations(conn, migrations_dir=MIGRATIONS_DIR)`, which pass `"public"` and the existing key. So `app/main.py`, `tests/conftest.py` and `tests/test_migrate.py` don't change.
   - Check: `make test-api`, plus the API tests marked `integration`, against a throwaway `postgres:16` (the recipe in `docs/testing.md`). The existing ordering, idempotence, rollback and concurrency tests must still pass.

3. **`feat(builder)`: numbered SQL migrations for the `portal` schema.**
   - **Runner copy:**
     - Copy the file to `services/builder/app/database/migration_runner.py`.
     - Red/green: a unit test compares it byte for byte with the API's file.
     - The Makefile's `test-builder` mounts `services/api/src/digitaltwins/postgres/migration_runner.py` read-only, the way it already mounts the API compose file.
     - The test uses the same repo-relative path when it runs from a checkout.
   - **`0001_baseline.sql`** goes in `services/builder/app/database/migrations/`. The Dockerfile already copies `app/`.
     - (a) Today's schema, made idempotent and qualified with `portal.`. To produce it, run today's `init_db` on an empty `postgres:16` and take `pg_dump --schema-only --schema=portal`, then edit:
       - drop the `SET` and `OWNER` lines
       - make it `CREATE TABLE IF NOT EXISTS`
       - wrap `CREATE TYPE` in `DO` blocks
     - (b) Catch-up steps for schemas created since 2026-09-28 (commit `bf7a3325`), ported from the four functions in this order:
       1. `is_sds`, added and backfilled only when the column is missing (a `DO` block on `information_schema`), and before anything else adds it
       2. `ADD COLUMN IF NOT EXISTS` for each column added since `bf7a3325`. To find them, diff the model file since that commit; the path then was under `services/portal/backend/`.
       3. on `plugin_deployments`: `DROP NOT NULL`, plus the foreign key and the one-build check when they are missing
       4. `ALTER TYPE … ADD VALUE IF NOT EXISTS` for the enum values (Postgres 16 allows this inside a transaction)
   - **`init_db`:**
     - On Postgres: create the schema if it is missing (as today), then `apply_migrations(bind.raw_connection().driver_connection, MIGRATIONS_DIR, "portal", <builder key>)`, closing the connection afterwards.
     - On SQLite: `create_all` only.
     - Delete the four `migrate_*` functions, and the SQLite-only tests of them: `test_workflow_is_sds_migration.py` and the matching part of `test_db_constraints.py`. They are orphaned by this change, and the Postgres tests below replace them.
   - **Postgres tests** go in [test_postgres_integration.py](services/builder/tests/test_postgres_integration.py), using its existing fixtures. A snapshot helper captures tables, columns (type, nullability, default), primary keys, foreign keys, unique and check constraints, indexes and enum labels.
     - **Models match the migrations:** a snapshot after migrating an empty database equals a snapshot after `create_all`.
     - **Re-running does nothing**, and `portal.schema_migrations` lists `0001`.
     - **Old schemas catch up:**
       - Load `tests/fixtures/portal_2026_09_28.sql`, which is `create_all` at `bf7a3325` dumped once and committed.
       - Insert a workflow that has `workflow_type` set.
       - After migrating, the snapshot equals the fresh one, with enum labels compared as sets, and `is_sds` is backfilled.
     - **A schema `init_db` already brought up to date** is left unchanged; `0001` is just recorded.
     - **Works as the `portal` role** (owns the schema, has no CREATE on the database). Rework the existing test.
     - **The copy tool still works.** The existing end-to-end test must still pass.
   - Check: `make test-builder` (unit tests, including the identity test), plus the builder's Postgres tests against a throwaway `postgres:16`, with `BUILDER_TEST_DB_HOST` and the other `BUILDER_TEST_DB_*` variables set to that container.

4. **`docs`: decisions and README.**
   - **New ADR**, `docs/decisions/2026-10-21-builder-numbered-sql-migrations.md` (draft below).
   - **Existing ADRs:**
     - [2026-10-20](docs/decisions/2026-10-20-merge-portal-backend-into-api-codebase.md): point the migration follow-up bullet at the new ADR.
     - `2026-09-28-portal-database-in-platform-postgres.md`: its status becomes "superseded in part".
   - **[services/builder/README.md](services/builder/README.md):** how to add a migration, and that the runner file must match the API's.
   - Sync the updated plan and a walkthrough to the artifacts folder, then run gitleaks.

5. **Check against the live data without touching it.**
   - `pg_dump --schema-only --schema=portal` of the live database (read-only) into a throwaway `postgres:16`, then run the builder's migrations there and compare snapshots.
   - Never run the builder's tests in the live container.

6. **Rebuild and restart: ask you first.**
   - `docker compose up -d --build api builder`.
   - Restarting the builder stops every plugin backend, and they stay down until an admin redeploys them, so I'll ask before running it.
   - Then check the logs: `0001` applied, the API reports no migrations pending, and `/api/builder/...` is healthy.

## Draft ADR: `2026-10-21-builder-numbered-sql-migrations.md`

- **Context:** the two mechanisms described above. The follow-up from the 2026-10-20 ADR. The two services can't import each other's code.
- **Options:**
  - A: shared package
  - B (chosen): identical copy enforced by a test
  - C: Alembic for the builder
  - D: leave as is
- **Decision:**
  - same runner, parameterised by schema and lock key
  - a `0001` baseline with catch-up steps
  - SQLite is for tests only, with `create_all` and no migrations
  - separate lock keys
- **Consequences:**
  - The models and the SQL files must be kept in step by hand. The "models match the migrations" test enforces this, but only when the Postgres tests run, and CI doesn't run them; the API has the same gap.
  - A runner change means editing both copies.
  - Renames and type changes become possible.

## Verification summary

- `make test-api` and `make test-builder` pass. Starting baselines: api 362 passed (1 skipped); builder 216 passed (7 skipped). The builder's count changes by the tests added and removed.
- The API and builder Postgres tests pass against a throwaway `postgres:16`.
- Migrating a dump of the live `portal` schema leaves its snapshot unchanged.
- After the rebuild, with your go-ahead: the logs show both services started and `portal.schema_migrations` contains `0001`.
