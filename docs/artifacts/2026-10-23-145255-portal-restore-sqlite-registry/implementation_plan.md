# Plan: portal-restore.sh migrates the builder's SQLite plugin registry automatically

## Context

Since 2026-09-28 the builder keeps its plugin registry in the `portal` schema of the `digitaltwins` Postgres DB.
`util/stage-dump.sh` still copies the builder's old SQLite file (`plugin_registry.db`). `util/portal-restore.sh` step 5
copies that file back into the builder and restarts it. Under the platform the builder ignores SQLite
(`BUILDER_DB_HOST` is set), so when the **source predates 2026-09-28** its `digitaltwins.sql` has no `portal`
schema, and the registry ends up **silently empty** on the target. The one-off CLI
`python -m app.cli.migrate_sqlite_to_postgres` ([migrate_sqlite_to_postgres.py](services/builder/app/cli/migrate_sqlite_to_postgres.py))
already does the move. Step 5 should run it when it applies.

## Branch

`git fetch origin && git switch -c fix/portal-restore-sqlite-registry origin/main`. The untracked artifact folders on
`dev_chinchien` stay untracked and are not touched. No commit or push until asked.

## Change: `util/portal-restore.sh` step 5

After the existing `docker cp` + `docker restart`:

1. **Explicit emptiness check.** It runs inside the builder and uses the app's own model metadata, so it covers exactly the
   tables the CLI refuses on (`Base.metadata.sorted_tables`). It excludes `schema_migrations`, and a table that doesn't exist yet counts as empty:
   ```bash
   rows=$(docker exec "$BUILDER_C" python -c '
   from sqlalchemy import func, inspect, select
   from app.models.db_model import Base, engine
   insp = inspect(engine)
   with engine.connect() as c:
       print(sum(c.execute(select(func.count()).select_from(t)).scalar_one() for t in Base.metadata.sorted_tables if insp.has_table(t.name)))')
   ```
2. **Skip (two cases, neither relies on the CLI's exit code 2):**
   - **The dump has the builder's portal tables** (`grep -q '^CREATE TABLE portal\.plugins ' "$IN/digitaltwins.sql"`): the source's builder ran on
     Postgres. (Tables, not `CREATE SCHEMA portal`: an old-code source on which someone ran `05_portal.sh` by hand has the schema but no tables,
     and its SQLite is still the live registry.) Its live registry
     came across in step 1 and the SQLite file is only a stale rollback copy → `source is post-2026-09-28: registry came across in digitaltwins.sql; not migrating plugin_registry.db`.
     This guards the edge case where the source's Postgres registry is empty but a pre-upgrade SQLite file still has rows. Migrating it then would bring back
     plugins deleted after the upgrade. (A source that upgraded but never ran the CLI can still run it by hand. The skip message names the command.)
   - **The target's portal tables already hold rows** (the explicit count from 1.; the target wasn't fresh) → `portal tables already hold N row(s); not migrating`.
   Order: schema grep first (no docker call needed), then the count.
3. **Empty → migrate:** `MIGRATE="python -m app.cli.migrate_sqlite_to_postgres --sqlite-path /data/plugin_registry.db"`.
   Run `$MIGRATE --dry-run`, then `$MIGRATE` for real. The CLI's own stdout/stderr (per-table counts, `✗ <error>`) goes straight to the terminal.
4. **After a successful real migration, restart the builder once more.** At startup the builder reconciles deployment rows that are marked up (marks vanished
   plugins down, regenerates or removes nginx confs). This gives the migrated rows the same treatment that registry rows arriving in `digitaltwins.sql` already get from
   the existing restart. Without it, migrated `up=True` deployments for containers that don't exist on the target stay "up" until the next restart.
5. **Failure (count error, dry run, or real run) → loud WARN, continue.** The message says the registry is NOT migrated and empty, the
   cause is printed above it, and it ends with the exact manual command (`docker exec <builder> $MIGRATE`). The same WARN is **repeated after the
   final `portal-restore: done.` block**, because steps 6–10 (SEEK reindex, enable-features) would otherwise push it off-screen.

**Why warn rather than abort:** this matches how the script handles a step whose fix can be rerun on its own (step 10). Steps 6–10 don't depend on the registry. The
CLI runs in a single transaction and rolls back on failure. The SQLite file is already at `/data/plugin_registry.db`, so the manual
command can be rerun later as it stands. Aborting at step 5 would leave Orthanc, nginx configs, Jupyter volumes and the SEEK re-stamp undone, which is a
worse half-restored state than one empty table set with a loud, actionable warning.

Implementation sketch (one `if/elif` chain; `REGISTRY_WARN` defaults to empty and is echoed at the end when it is set):
```bash
if grep -q '^CREATE TABLE portal\.plugins ' "$IN/digitaltwins.sql" 2>/dev/null; then echo "  ... post-2026-09-28 source, skip (manual: docker exec $BUILDER_C $MIGRATE) ..."
elif ! rows=$(docker exec ... count ...); then  REGISTRY_WARN="could not count ... registry NOT migrated; run: docker exec $BUILDER_C $MIGRATE"
elif [ "$rows" != 0 ]; then                  echo "  ... skip ..."
elif docker exec "$BUILDER_C" $MIGRATE --dry-run && docker exec "$BUILDER_C" $MIGRATE; then docker restart "$BUILDER_C" >/dev/null
else                                         REGISTRY_WARN="plugin registry NOT migrated (error above) — the target's registry is EMPTY. Fix the cause, then run: docker exec $BUILDER_C $MIGRATE"
fi
[ -z "$REGISTRY_WARN" ] || echo "  WARN: $REGISTRY_WARN"
```

## Comments + docs

- `util/portal-restore.sh`: rewrite the step 5 comment. From a source on or after 2026-09-28, the registry comes across in step 1 and this file is only the rollback copy.
  From an older source, this file IS the live registry, and it is migrated automatically when the portal tables are empty.
- `util/stage-dump.sh` step 5 comment (and the header "Covers" line): same correction. The file is the live registry on a pre-2026-09-28 source.
- `util/README.md` "Plugin registry" note (around line 503): from a source older than 2026-09-28, `plugin_registry.db` is the live registry and
  `portal-restore.sh` migrates it automatically. It does so with a dry run first, and only when the dump has no portal tables and the target's `portal` tables are empty. On failure the restore
  warns at the end with the command to rerun. A source that upgraded but never migrated its SQLite is skipped. The note gives the manual command for that case.
- No ADR: the warn-vs-abort choice follows the script's existing step 10 convention, not a new architectural decision.

## Test first (sandbox, never the live stack)

**The harness stays in the session scratchpad and is not committed.** A committed harness that drives a *destructive* script is a standing hazard: run on a
real box with one env override missing, it would overwrite live data. The walkthrough describes the cases instead.

**Safety layers** (all of them, before portal-restore.sh ever runs):
- A unique `restore-test-` prefix on every container, volume and network, and everything labelled `sandbox=restore-test`. The network is `--internal` (no egress).
- **Preflight assert:** every name-carrying var passed to portal-restore.sh (`PROJECT NETWORK DB_C SEEKDB_C SEEK_C BUILDER_C MINIO_C GATEWAY_C
  PLUGIN_CONF_VOL ORTHANC_MAP`) must start with `restore-test`, and `BASE_DIR` must be an empty dir under the scratchpad. Otherwise the harness exits.
- **`docker` wrapper** first on PATH. It refuses: `compose`; any `prune` (`system|volume|container|image|network prune`); any argument
  matching `digitaltwins-platform*` / `hapi-fhir*`; and any argument equal to a live container, volume or network name, from a snapshot of
  `docker ps -a`, `docker volume ls` and `docker network ls` taken at harness start (excluding `restore-test*`). Otherwise it execs the real docker.
- The builder gets no Docker socket, so the code under test can't reach the daemon.

Everything is labelled `sandbox=restore-test`, and names are prefixed `restore-test-`.

- **Network:** `docker network create --internal restore-test-net`.
- **Postgres 16:** `restore-test-db`, with `services/postgres/*` init scripts mounted read-only exactly as in `services/postgres/docker-compose.yml`,
  throwaway `POSTGRES_PASSWORD` / `BUILDER_DB_PASSWORD` (generated, never printed or written to the repo), so the `portal` role exists.
- **Builder:** the real builder image, retagged once as `restore-test-builder:sandbox` (`docker tag`, untagged at cleanup). The current branch's
  `services/builder/app` is mounted read-only at `/app/app`, so the CLI under test is the branch's code, not the 2-day-old image's. The env is
  `BUILDER_DB_HOST=restore-test-db`, `BUILDER_DB_USER=portal`, `BUILDER_DB_PASSWORD`, `DATABASE_PATH=/data/plugin_registry.db`,
  `PYTHONPATH=/app`, with an anonymous `/data` volume. **No Docker socket** (the builder's startup reconcile tolerates this: it logs and continues).
- **Dummy SEEK:** `restore-test-seek` (alpine `sleep`). Step 9's `docker compose` is refused by the wrapper, so it falls back to `docker restart $SEEK_C`, which needs a container.
- **portal-restore.sh env:** `PROJECT=restore-test NETWORK=restore-test-net BASE_DIR=<empty dir> DB_C=restore-test-db
  BUILDER_C=restore-test-builder SEEK_C=restore-test-seek SEEKDB_C/MINIO_C/GATEWAY_C=restore-test-absent
  ORTHANC_MAP="restore-test_o1=restore-test-o1" PLUGIN_CONF_VOL=restore-test_plugin_conf`, with `yes` piped to the prompt.
  The dump dir holds only `digitaltwins.sql` (+ `plugin_registry.db`), so the SEEK, MinIO, nginx and Jupyter steps skip. The empty BASE_DIR has no `.env` or realm
  template, so step 10 just WARNs.
- **`docker` wrapper** first on PATH: it refuses `docker compose` and any argument matching `digitaltwins-platform*` or `hapi-fhir*`, then execs the real docker.
- **Old-source dump:**
  - `digitaltwins.sql` = `pg_dump --clean --if-exists` of a scratch DB `oldsrc` in the sandbox Postgres (one table and one row, no `portal` schema), like a pre-2026-09-28 source.
  - `plugin_registry.db` = **old-schema SQLite**. The repo fixture `services/builder/tests/fixtures/portal_2026_09_28.sql` is a Postgres
    schema dump, not SQLite, and the CLI's tests build SQLite from the *current* models. So take the real pre-Postgres model with
    `git show bf7a3325^:services/portal/backend/app/models/db_model.py` (self-contained: SQLAlchemy + pydantic), run it in the sandbox builder
    image with `DATABASE_PATH` pointing at the output file, `create_all`, and insert one row in every table (a plugin, a workflow linked to it, a build, an
    `up=True` deployment, annotations), with FKs consistent.
- **Cleanup:** `docker rm -f -v $(docker ps -aq --filter label=sandbox=restore-test)`, `docker network rm restore-test-net`,
  `docker rmi restore-test-builder:sandbox` (untag only). No prune of any kind.

**Cases** (fresh sandbox each; assertions in the harness):
1. **RED (unmodified script):** old-source dump → restore exits 0 but the portal row count is 0. This reproduces the bug. The expected count (N > 0) fails.
2. **GREEN, old source:** the same dump with the fixed script → the output shows the dry run, then `Migrated`. Per-table counts equal the SQLite counts. The builder restarted and the
   migrated `up=True` deployment is reconciled to down.
3. **New source:** a `digitaltwins.sql` that contains the `portal` schema with rows (made by `pg_dump` of the sandbox DB after case 2) + a stale
   `plugin_registry.db` → post-2026-09-28 skip message, the CLI is not run, the restored counts are unchanged, exit 0.
3b. **New source, empty registry, stale SQLite** (the edge case): portal tables with zero rows in the dump + a SQLite file with rows → still skipped, portal stays empty.
3c. **Old source, non-fresh target:** no portal tables in the dump, but the target's portal is pre-seeded → "already hold N row(s)" skip, counts unchanged.
4. **Migration failure:** SQLite with an orphan `plugin_builds` row → the dry run fails → the CLI's error is printed, the WARN with the manual command appears at step 5 **and** after
   `done.`, steps 6–10 still run, the portal is still empty, exit 0.
5. **No `plugin_registry.db` in the dump:** step 5 skipped entirely, as before.

Also: `bash -n` + `shellcheck` (if available) on the changed scripts, and `make gitleaks`. No Python changes, so `make test-builder` is not
required. No live containers are rebuilt or restarted (only the shell scripts change, and none of them is baked into an image).

## Artifacts

On approval, sync this plan to `docs/artifacts/2026-10-23-<HHMMSS>-portal-restore-sqlite-registry/implementation_plan.md` right away, then add a
`walkthrough.md` at the end. Verification will list the automated sandbox cases only: no local paths, no local ops log, no secrets (gitleaks-checked).

## Noticed, not fixing (out of scope)

`stage-dump.sh` step 5 runs `docker cp $BUILDER_C:/data/plugin_registry.db` unconditionally. A source **installed** after 2026-09-28 never
creates that file (the builder only creates SQLite when `BUILDER_DB_HOST` is unset), so under `set -e` the dump would abort there. Worth a separate fix.
