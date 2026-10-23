# Walkthrough: portal-restore.sh migrates the SQLite plugin registry

## Problem

Since 2026-09-28 the builder keeps its plugin registry in the `portal` schema of the `digitaltwins` Postgres DB.
When the dump comes from an **older** source, its `digitaltwins.sql` has no portal tables, and the registry exists
only in `plugin_registry.db`. `portal-restore.sh` step 5 copied that file into the builder, but under the platform the builder
ignores SQLite (`BUILDER_DB_HOST` is set). So the restore finished with `done.` and the target's registry was empty,
with no warning.

## Change

`util/portal-restore.sh` step 5, after the existing copy + builder restart:

| Condition | Action |
|---|---|
| `digitaltwins.sql` contains `CREATE TABLE portal.plugins` (post-2026-09-28 source) | Skip. The registry came across in step 1. Prints the manual CLI command in case the source never migrated its SQLite file. |
| Target portal tables already hold rows (counted in the builder with its own model metadata, the same tables the CLI checks) | Skip, printing the row count. |
| Otherwise (pre-2026-09-28 source, empty target) | `migrate_sqlite_to_postgres --dry-run`, then the real run, then restart the builder so its startup reconcile sees the migrated deployments. |
| Count, dry run or real run fails | `WARN: plugin registry NOT migrated ... run: docker exec <builder> python -m app.cli.migrate_sqlite_to_postgres --sqlite-path /data/plugin_registry.db`, printed at step 5 and repeated after `portal-restore: done.`. The restore continues. |

The skip decision never relies on the CLI's "refused" exit code (2).

**Detecting a post-2026-09-28 source by its portal tables, not by an empty target alone:** a source on new code with an empty Postgres registry
and a stale pre-upgrade SQLite file would otherwise have its deleted plugins brought back. The check looks for tables rather than
`CREATE SCHEMA portal` because an old-code source on which someone ran `05_portal.sh` by hand has the schema but no tables.

**Warn, don't abort:** this matches step 10. Steps 6–10 don't depend on the registry. The CLI runs in one transaction and rolls back on
failure, and the SQLite file stays in `/data`, so the printed command can be rerun once the cause is fixed. Aborting would leave
Orthanc, plugin nginx configs, Jupyter volumes and the SEEK re-stamp undone.

Comments in `util/stage-dump.sh` step 5 and its header, and the "Plugin registry" note in `util/README.md`, now say that on a
source older than 2026-09-28 `plugin_registry.db` is the live registry and is migrated automatically.

## Verification

A throwaway Docker sandbox: `--internal` network; Postgres 16 with the repo's `services/postgres` init scripts; the real builder image
running this branch's `services/builder/app`, with no Docker socket; a `docker` guard on PATH that refuses `docker compose`, any prune, and any
live container, volume or network name. `plugin_registry.db` was built from the pre-Postgres model (`git show bf7a3325^`) with one row in each of
the 8 copied tables. The old-source `digitaltwins.sql` is a `pg_dump --clean --if-exists` of a DB holding only the platform schema.

| Case | Before fix | After fix |
|---|---|---|
| Old source, fresh target | exit 0, **0/8 rows** (bug reproduced) | exit 0, dry run then `Migrated: 8 rows`, `up=True` deployment reconciled to down after the restart |
| New source (registry in `digitaltwins.sql`) + stale SQLite | — | skipped, CLI not run, 8 rows from the dump intact |
| New source with an empty registry + stale SQLite with rows | — | skipped, 0 rows (stale rows not brought back) |
| Old source, target already holding rows | — | skipped ("already hold 8 row(s)"), rows unchanged |
| Old SQLite with an orphan `plugin_builds` row | — | dry run fails with the CLI's FK error; WARN with the manual command at step 5 and after `done.`; later steps ran; exit 0; 0 rows |
| No `plugin_registry.db` in the dump | — | step 5 skipped as before |

Also: `bash -n` on both scripts; shellcheck adds no new findings; gitleaks finds nothing in the changed files.
