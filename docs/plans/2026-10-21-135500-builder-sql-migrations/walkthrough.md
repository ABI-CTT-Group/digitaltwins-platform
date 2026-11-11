# Walkthrough: one migration runner for `public` and `portal`

Branch `feat/builder-sql-migrations`. Plan: [plan.md](plan.md). Decision: [ADR 2026-10-21-builder-numbered-sql-migrations](../../decisions/2026-10-21-builder-numbered-sql-migrations.md).

## What changed

### 1. `fix(builder)`: the builder no longer receives the Keycloak client secret
- `KEYCLOAK_CLIENT_SECRET` is removed from `services/builder/docker-compose.yml`. Plugin builds and deploys inherit the builder's environment, so untrusted plugin code could read the `api` client's secret.
- `app/client/keycloak.py` loses the secret, the unused `KeycloakAdmin`, and `authenticate_with_credentials`.
  - Nothing called `authenticate_with_credentials`.
  - It used the password grant, which a confidential client can't do without the secret.
- Token checks still use the realm's public key, exactly as before.
- `tests/test_service_separation.py` now treats `KEYCLOAK_CLIENT_SECRET` as an API-only variable.

### 2. `refactor(api)`: the runner core is its own module
- `services/api/src/digitaltwins/postgres/migration_runner.py` holds `discover` and `apply_migrations(conn, migrations_dir, schema, lock_key)`. It needs only the standard library and a DB-API connection.
- `migrate.py` keeps its functions as wrappers for `public` and the existing lock key, so callers and tests are unchanged.
- A new integration test checks that the runner records migrations in the schema it is given.

### 3. `feat(builder)`: numbered SQL migrations for `portal`
- **The runner:**
  - `services/builder/app/database/migration_runner.py` is a verbatim copy of the API's.
  - `tests/test_migration_runner.py` checks the copies match.
  - `make test-builder` mounts the API's file read-only.
- **`app/database/migrations/0001_baseline.sql`:**
  - It creates today's schema idempotently.
  - It catches up any `portal` schema built since 2026-09-28 (`bf7a3325`), the first Postgres schema the builder created.
  - `workflow_type` is added before the one-time `is_sds` backfill reads it. Today's catch-up code got this order wrong and would fail at startup on a schema from before 2026-10-02.
  - The `measurements` tables, which the models no longer define, are left alone.
- **`init_db`:**
  - On Postgres, it applies the migrations under the builder's own advisory-lock key and records them in `portal.schema_migrations`.
  - On SQLite (tests, or a standalone builder), it runs `create_all`.
  - The four catch-up functions are deleted, along with the SQLite-only tests of them.
- **New Postgres tests** in `tests/test_postgres_integration.py`:
  - The migrations build the schema `create_all` builds (a snapshot of tables, columns, keys, constraints, indexes and enum labels).
  - A second start changes nothing.
  - A schema the old startup code built is only recorded.
  - The 2026-09-28 schema (`tests/fixtures/portal_2026_09_28.sql`) catches up and keeps its rows.
  - Workflows typed before `is_sds` existed are marked SDS, once.

### 4. `ci`: the builder job runs when the API's runner changes
- A PR that changed only the API's runner would have skipped the identity test. The builder's path filter in `.github/workflows/ci.yml` and the table in `docs/testing.md` now include the runner.

### 5. `docs`
- A new ADR.
- The 2026-10-20 ADR's follow-up is marked done.
- The 2026-09-28 portal database ADR is superseded in part.
- The builder README explains how to add a migration and lists `KEYCLOAK_CLIENT_SECRET` among the credentials the builder never gets.

## Deviations from the plan
- `authenticate_with_credentials` was removed with the secret. It had no callers and couldn't work without the secret.
- The CI path-filter commit (4) was added, because without it a runner-only change would bypass the identity test.

## Verification
- `make test-api`: 362 passed, 1 skipped.
- `make test-builder`: 214 passed, 11 skipped.
  - Previously 216 passed and 7 skipped. Four SQLite tests of the deleted functions were removed, two unit tests were added, and four Postgres tests were added net, which CI skips.
- API integration tests against a throwaway `postgres:16`: 11 passed. The rest need MinIO or other services and skip.
- Builder Postgres tests against a throwaway `postgres:16`, with the `portal` role setup: 11 passed.
  - Breaking `0001` on purpose made them fail: a dropped catch-up column, and a wrong nullability.
- Pre-commit `gitleaks`: passed on every commit.
- Still open: the Postgres tests don't run in CI, the same gap the API's integration tests have.
