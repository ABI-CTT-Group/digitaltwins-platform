# Implementation Plan — Move the Portal Database into the Platform Postgres

- **Created:** 2026-09-28 14:13
- **Status:** Approved 2026-09-28, in progress
- **ADR (draft):** [docs/decisions/2026-09-28-portal-database-in-platform-postgres.md](../../decisions/2026-09-28-portal-database-in-platform-postgres.md)

## Goal

The portal backend currently keeps its data in its own SQLite file. Move that data into the platform's shared Postgres (the `database` service), and copy the existing rows across without losing any. The migration must also be repeatable on every other deployment.

## Current state (verified 2026-09-28)

| Item | Finding |
|---|---|
| Portal DB | SQLite at `DATABASE_PATH=/data/plugin_registry.db`, on the `${PROJECT_NAME}_plugin_database` volume. Configured in [db_model.py](../../../services/portal/DigitalTWINS-Portal/backend/app/models/db_model.py). |
| Portal tables (10) | `plugins`, `plugin_builds`, `plugin_deployments`, `plugin_annotations`, `workflows`, `workflow_builds`, `workflow_annotations`, `workflow_plugin_association`, `measurements`, `measurement_annotations` |
| Schema management | No Alembic. `init_db()` runs `create_all` and then `migrate_add_missing_columns()` ([database.py](../../../services/portal/DigitalTWINS-Portal/backend/app/database/database.py)). |
| Platform Postgres | `postgres:16`. Databases: `digitaltwins` (API tables in `public`), `airflow`, `keycloak`, `hapi`. The init scripts in `services/postgres/` run **only on an empty data volume**. |
| Name collisions | None. The `public` tables in `digitaltwins` are `assay*`, `dataset*`, `subject`, `sample`, and so on. |
| Driver | `psycopg2 2.9.10` and `libpq-dev` are already in the portal image, and it imports fine under `uv run`. No image changes are needed. |
| Live data | 6 rows in total (1 each in plugins, builds, deployments, plugin annotations, measurements, measurement annotations). |
| SQL portability | The code uses only the ORM, apart from the `ALTER TABLE ADD COLUMN` in `migrate_add_missing_columns`, which also works on Postgres. There is no SQLite-specific SQL. |

### Blockers found during investigation

1. **Wrong foreign-key target, hidden by SQLite.** `PluginDeployment.build_id` is declared as `ForeignKey("plugin_builds.id")`. However, the code writes the business key `latest_build.build_id` into it ([workflow_tool_plugin.py:576](../../../services/portal/DigitalTWINS-Portal/backend/app/router/workflow_tool_plugin.py#L576)) and reads it back by the same key (line 669). SQLite doesn't enforce foreign keys, and `PRAGMA foreign_key_check` already reports the live row as an orphan. On Postgres, **every plugin deploy would fail** with an FK violation, and the migration would reject the existing row.
2. **Plugin subprocesses inherit the whole backend environment.** `PluginDeployer._compose_execute` ([deploy_tool.py:156](../../../services/portal/DigitalTWINS-Portal/backend/app/builder/deploy_tool.py#L156)) and `builder_utils.py:56` pass `os.environ` to third-party plugin `docker compose` and build commands. If the backend's environment holds a DB password, every plugin can read it. The password must be removed from those subprocess environments.

## Decisions (recommended; details in the ADR)

| # | Decision | Recommendation | Main alternatives |
|---|---|---|---|
| D1 | Where the tables go | A new **`portal` schema inside the `digitaltwins` database** | A separate `portal` database, or the `public` schema of `digitaltwins` |
| D2 | DB credentials | A dedicated **`portal` role** that owns only the `portal` schema | Reuse the `POSTGRES_USER` admin superuser |
| D3 | Connection config | Separate `PORTAL_DB_HOST/PORT/NAME/USER/PASSWORD` variables, with the URL built by `sqlalchemy.engine.URL.create` (which escapes special characters in passwords). **Stay on SQLite when `PORTAL_DB_HOST` is unset**, so standalone dev and unit tests are unchanged. | A single `DATABASE_URL` (breaks on unescaped `@`/`:` in passwords), or dropping SQLite completely |
| D4 | Schema management | Keep `create_all` + `migrate_add_missing_columns`. Adopting Alembic is out of scope. | Introduce Alembic now |
| D5 | Moving existing data | A **one-off CLI that the operator runs explicitly**, with pre-flight checks and row-count verification | Migrating automatically at startup |
| D6 | FK fix | Point `plugin_deployments.build_id` at `plugin_builds.build_id`, which is already `unique`. That matches what the code writes and reads, so existing data stays valid without rewriting it. | Change the writers and readers to store `plugin_builds.id` and rewrite existing rows |

Tables go into the `portal` schema through the connection's **`search_path`** (`options=-csearch_path=portal`), not through `MetaData(schema=...)`. With this approach the models don't change and still work on SQLite. The `plugin_label` enum type is also created in `portal` rather than `public`.

## Steps

The work spans two repositories. Portal code changes go in a PR to the `DigitalTWINS-Portal` submodule. Platform changes (compose, init script, secrets template, submodule bump, this plan, the ADR) go in a PR to `digitaltwins-platform`.

TDD applies throughout: write each test first and see it fail, then implement.

### Part A — Portal submodule

**A1. Fix the deployment → build foreign key (D6)**
- Test first: `tests/test_db_constraints.py`. With SQLite and `PRAGMA foreign_keys=ON`, create a plugin, a build and a deployment where `build_id=build.build_id`, then commit. This currently fails with an FK error (Red).
- Change: in `db_model.py`, `PluginDeployment.build_id` becomes `ForeignKey("plugin_builds.build_id")`. The `PluginBuild.deployments` and `PluginDeployment.build` relationships then join on that column automatically.
- Also test that deleting a plugin that has a build and a deployment succeeds while FKs are enforced. This covers the ORM cascade order.
- → verify: the new tests and the existing suite pass.

**A2. Choose the engine from configuration (D3)**
- Test first: `tests/test_db_config.py`
  - If `PORTAL_DB_HOST` is unset, the engine URL is `sqlite:///<DATABASE_PATH>`.
  - If it is set, the URL is `postgresql+psycopg2://…`, and a password like `p@ss:/w#rd` survives the round trip.
- Change in `db_model.py`: add a small `_build_engine()`.
  - SQLite keeps `check_same_thread=False`.
  - Postgres gets `pool_pre_ping=True` and `connect_args={"options": "-csearch_path=portal"}`.
- → verify: the unit tests pass, and the existing tests still run on SQLite unchanged.

**A3. Make `init_db()` work on both backends**
- On Postgres, run `CREATE SCHEMA IF NOT EXISTS portal` before `create_all`. This is a no-op when the role already owns the schema.
- Run `ensure_data_directory()` only for SQLite.
- `migrate_add_missing_columns()` stays as it is; it is covered by the integration test in A6.
- → verify: the A6 integration tests.

**A4. Remove DB credentials from plugin subprocess environments**
- Test first: `tests/test_subprocess_env_scrub.py`. Patch `stream_process` and the build runner, set `PORTAL_DB_PASSWORD` (and the other `PORTAL_DB_*` variables) in the environment, and assert they are absent from the env passed to `_compose_execute` and to the `builder_utils` subprocess.
- Change: add one helper, `plugin_subprocess_env(extra)`, that copies `os.environ` without the `PORTAL_DB_*` keys, and use it at both call sites.
- → verify: the test passes.
- *Existing issue, not fixed here:* MinIO keys already reach plugins the same way, but the compose comments say plugins intentionally rely on them.

**A5. Data-migration CLI `app/cli/migrate_sqlite_to_postgres.py` (D5)**
- Usage: `uv run python -m app.cli.migrate_sqlite_to_postgres --sqlite-path /data/plugin_registry.db [--dry-run]`. The target comes from the `PORTAL_DB_*` variables.
- Behaviour:
  1. Call `init_db()` on the target, which creates the schema and tables.
  2. **Pre-flight:** abort if any target table already has rows (so a rerun can't create duplicates). Also run `PRAGMA foreign_key_check` on the source (with the corrected FK from A1) and abort, listing the offending rows, if there are orphans.
  3. Copy each table in `Base.metadata.sorted_tables` order (parents before children) in a **single transaction**, using SQLAlchemy Core with the model `Table` objects. This keeps `id`, `created_at` and `updated_at` exactly as they are (`onupdate` doesn't fire), decodes and re-encodes JSON, and converts booleans. Only columns present in both source and target are copied, so older SQLite files still work.
  4. **Verify:** compare row counts per table. On any mismatch, roll back and exit non-zero. Print a summary.
  5. With `--dry-run`, do the pre-flight and report counts, then roll back.
- Test first: `tests/test_migrate_sqlite_to_postgres.py`. Unit tests run SQLite → SQLite, which the Core code allows. They check:
  - all 10 tables are copied
  - ids, timestamps and JSON are unchanged
  - it refuses a non-empty target
  - it aborts on an orphaned FK
  - a dry run writes nothing
- → verify: the unit tests pass; a Postgres run is in A6.

**A6. Postgres integration tests**
- Add `tests/test_postgres_integration.py`. It is **skipped unless `PORTAL_TEST_DB_HOST` is set**. Locally, point it at the platform `database` container on port 8003, using a throwaway database `portal_test` that the fixture creates and drops.
- It covers:
  - `init_db()` puts all 10 tables and the `plugin_label` enum in `portal` and nothing in `public`
  - `migrate_add_missing_columns()` puts back a dropped column
  - the migration CLI works end to end from SQLite to Postgres
  - deleting a plugin cascades correctly under FK enforcement
- → verify: `PORTAL_TEST_DB_HOST=localhost PORTAL_TEST_DB_PORT=8003 … python -m unittest` runs everything green.

**A7. Documentation**
- Update the database section of `docs/deployment-guide.md` in the portal repo (SQLite when standalone, Postgres under the platform).

### Part B — Platform repo

**B1. Portal role and schema: `services/postgres/portal_init.sh`**, mounted as `05_portal.sh`
- It is idempotent. It creates the `portal` role with `PORTAL_DB_PASSWORD` if the role doesn't exist, then runs `CREATE SCHEMA IF NOT EXISTS portal AUTHORIZATION portal` in `digitaltwins`.
- It is written as `.sh` so that it reads the password from the environment instead of hard-coding it in SQL.
- On fresh volumes it runs automatically. On **existing** volumes the operator runs it once: `docker exec -e PORTAL_DB_PASSWORD=<REDACTED> <db-container> bash /docker-entrypoint-initdb.d/05_portal.sh`.
- Add `PORTAL_DB_PASSWORD` to the `database` service environment.
- → verify: run it twice against the live DB and confirm no errors; `\dn+ portal` shows the owner is `portal`.

**B2. Root `docker-compose.yml`: `portal-backend` overrides**
- Add `PORTAL_DB_HOST=database`, `PORTAL_DB_PORT=5432`, `PORTAL_DB_NAME=${POSTGRES_DB:-digitaltwins}`, `PORTAL_DB_USER=portal` and `PORTAL_DB_PASSWORD=${PORTAL_DB_PASSWORD}`.
- Add `depends_on: database: condition: service_healthy`.
- Keep the `plugin_database` volume mounted for now: it is the migration source and the rollback path.
- → verify: `docker compose config` shows the merged env and `depends_on` for `portal-backend`.

**B3. `secrets.env.template`:** add `PORTAL_DB_PASSWORD=<REDACTED>` with a comment.

**B4.** Bump the submodule to the merged Part A commit. Commit this plan and the ADR in the same PR.

### Part C — Cut-over runbook (this deployment, then all the others)

1. **Back up:** copy `plugin_registry.db` aside, then run `pg_dump -d digitaltwins` from the `database` container.
2. Set `PORTAL_DB_PASSWORD` in `secrets.env`. Run the B1 script once, because this volume already exists.
3. `docker compose stop portal-backend`, then rebuild it with the new code.
4. `docker compose run --rm portal-backend uv run python -m app.cli.migrate_sqlite_to_postgres --sqlite-path /data/plugin_registry.db --dry-run`, then run it again without `--dry-run`.
5. `docker compose up -d portal-backend`. Smoke test in the UI:
   - list, build, deploy and delete a plugin
   - create a workflow
   - upload a measurement and save its annotation
   - restart and confirm the data is still there
6. Check with psql: `SELECT count(*) FROM portal.<table>` matches the migration summary.
- **Rollback:** unset `PORTAL_DB_HOST` for `portal-backend` and restart. It goes back to the untouched SQLite file, but anything written after the cut-over is lost.

## Changes made during implementation

- **A4:** `builder_utils.py:56` only runs `git clone`, which executes no plugin code, so it is unchanged. The second exposed site is actually `PluginBuilder._run_streaming` ([build_tool.py](../../../services/portal/DigitalTWINS-Portal/backend/app/builder/build_tool.py)), which runs the plugin's own install and build commands and used to inherit the whole environment. The scrub helper `plugin_subprocess_env()` lives in `app/builder/proc_stream.py`.
- **A5:** there is no `PRAGMA foreign_key_check` pre-flight. Existing SQLite files still carry the *old* FK definition, so the check would wrongly flag valid rows. Orphans are caught by the target's own FK enforcement instead: the insert fails, the single transaction rolls back, and the CLI exits 2. SQL `NULL` in JSON columns is kept as SQL `NULL` rather than JSON `null`. The source file is opened read-only (`mode=ro`).
- **A3/A5:** `init_db`, `create_tables` and `migrate_add_missing_columns` take an optional `bind` (default: the app engine) so the CLI and the tests can target any engine.
- **A3, found while doing B1:** Postgres checks the database-level CREATE privilege even for `CREATE SCHEMA IF NOT EXISTS`, so the least-privilege `portal` role got `permission denied` at startup. `init_db` now checks `has_schema` first and only creates the schema when it is missing. This is covered by an integration test that runs as a schema-owning role without database-level CREATE.
- **B1:** verified in a throwaway `postgres:16` container. The first-init run and a manual rerun both succeed, and the rerun rotates the password. `portal` owns its schema, can create tables there, and gets *permission denied* in `public` and for `CREATE SCHEMA`.
- **B1/B2:** `.env.template` gets `PORTAL_DB_PASSWORD=${PORTAL_DB_PASSWORD}` (the Airflow pattern). Both compose files use `${PORTAL_DB_PASSWORD:?…}`, so **every `docker compose` command fails until `.env` has it**. This is deliberate: the stack won't start with an empty DB password. Cut-over step 2 regenerates `.env` first.
- **Tests** run in a throwaway container from the `portal-backend` image, with `app/` and `tests/` mounted (the host `.venv` is incomplete). Result: 74 tests pass with Postgres enabled; without `PORTAL_TEST_DB_HOST`, the 5 Postgres tests are skipped.

- **A5/proc_stream, found by the cut-over dry run:** one `plugin_builds.build_logs` value contained a NUL byte. It comes from Rollup's `\0commonjsHelpers.js` virtual-module id in Vite output captured through the PTY. Postgres text cannot store NUL, so the dry run failed with nothing written.
  - The migration now removes NUL from text values and reports each affected column.
  - `proc_stream._emit` now drops NUL from every captured line. Without this, future plugin builds would have failed when saving their logs to Postgres.
  - Both have tests; the suite is now 77.

## Cut-over record (this deployment, 2026-09-28)

1. Added a generated `PORTAL_DB_PASSWORD` to `secrets.env` and ran `util/gen-env.sh -e env -s secrets.env`. The regenerated `.env` also changed `NODE_IP` (it is auto-detected, and the host network had changed). I restored the old value so the only change to `.env` was the new key.
2. Backups went to `./backup/portal-postgres-cutover-2026-09-28-145222/` in the repo (mode 700; git-ignored via `/backup/` in `.gitignore`):
   - a consistent SQLite snapshot taken with `sqlite3.backup`
   - `pg_dump -Fc digitaltwins`
   - `pg_dumpall --roles-only` (contains password hashes)
3. Ran the role/schema script on the existing volume by piping it into the *running* container (`docker exec -i -e PORTAL_DB_PASSWORD=<REDACTED> <db> bash -s < services/postgres/portal_init.sh`). This avoided recreating the shared `database` container.
4. Rebuilt `portal-backend` and stopped it.
   - The first dry run failed on the NUL (see above). After the fix and a rebuild, the dry run and the real run both reported 6 rows and 1 stripped value.
   - Started it with `docker compose up -d --no-deps portal-backend`. `--no-deps` stops compose from recreating `database` because its config changed.
5. Verification:
   - the backend uses `postgresql+psycopg2://portal:***@database:5432/digitaltwins`
   - ids and values match the SQLite backup, and nothing was created in `public`
   - the deployment's `up` flag was already `false` before the cut-over, so it is preserved
   - 10 read endpoints return 200, including build → deploys (the corrected FK path) and the build log (27,989 characters = 27,990 minus the NUL)
   - a throwaway write test as `portal` (plugin, build, deployment, annotation, workflow, workflow build, measurement, measurement annotation), then cascade deletes; 0 rows left and real data unchanged
   - data survived a restart, and the gateway returns 200 for `/api/tools/`
6. **Still pending:**
   - The `database` container still runs with its old config (no `05_portal.sh` mount, no `PORTAL_DB_PASSWORD` env). The next full `docker compose up -d` will recreate it, briefly restarting the shared Postgres. That is harmless: the init script only runs on an empty volume.
   - A UI build and deploy of a plugin still needs to be done manually.

## Commits

The portal submodule is on branch `feat/portal-postgres` (base `cc77c73`). Every commit passes the full suite on its own, Postgres tests included:

  - `4cba1b6` fix(db): reference plugin_builds.build_id from plugin_deployments
  - `52da717` feat(db): use Postgres when PORTAL_DB_HOST is set
  - `4a7d218` fix(builder): keep PORTAL_DB_* out of plugin subprocess environments
  - `4adf5b4` fix(builder): drop NUL bytes from captured process output
  - `e1b11bf` feat(cli): add SQLite-to-Postgres migration command

The platform commits are on `dev_chinchien`: the setup script and its wiring, the portal-backend compose override, these docs, and the `/backup/` ignore rule. The submodule pointer is bumped to the branch commit `e1b11bf` for now (`027925e`). Re-point it to the portal `main` merge commit once the PR is merged.

## Out of scope (follow-ups)

- Introducing Alembic.
- Cross-schema foreign keys from portal `uuid` columns to `digitaltwins.public.dataset`.
- Removing the `plugin_database` volume and the SQLite fallback. Do this after one release of running on Postgres.
- Stopping MinIO credentials from reaching plugin subprocesses (an existing, intentional contract).

## Task checklist

- [x] A1 FK fix (tests first)
- [x] A2 engine selection (tests first)
- [x] A3 `init_db` for both backends
- [x] A4 subprocess env scrub (tests first)
- [x] A5 migration CLI (tests first)
- [x] A6 Postgres integration tests
- [x] A7 portal docs
- [x] B1 `portal_init.sh` + database env
- [x] B2 root compose overrides
- [x] B3 secrets template
- [x] B4 submodule bump, temporary: points at `e1b11bf` on `feat/portal-postgres` (platform `027925e`). The portal branch must be pushed before the platform is. After the portal PR is merged, re-point to the merge commit on portal `main`.
- [x] C cut-over on this deployment (2026-09-28 14:57)
- [ ] Update the ADR if anything diverged; sync artifacts to `docs/artifacts/`
