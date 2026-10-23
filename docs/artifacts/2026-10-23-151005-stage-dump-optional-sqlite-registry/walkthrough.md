# Walkthrough: stage-dump.sh no longer requires the builder's SQLite registry

## Problem

`util/stage-dump.sh` step 5 ran `docker cp <builder>:/data/plugin_registry.db` unconditionally under `set -e`.
The builder only creates that SQLite file when `BUILDER_DB_HOST` is unset, so a source **installed** on or after
2026-09-28 (registry in the `portal` schema of the `digitaltwins` DB from day one) never has it, and the whole
dump aborted at step 5 with `Could not find the file /data/plugin_registry.db`.

## Change

`util/stage-dump.sh` step 5 still tries `docker cp` (which, unlike `docker exec`, also works on a stopped builder). If the copy fails:

| `digitaltwins.sql` (step 1) | Action |
|---|---|
| contains `CREATE TABLE portal.plugins` | Skip: the live registry is already in the dump. Prints why. |
| has no portal tables | `FATAL` with docker's own error, exit 1: the dump would otherwise carry no registry at all (e.g. a wrong `BUILDER_C`). |

The check is the same `CREATE TABLE portal.plugins` match `portal-restore.sh` step 5 uses, and `portal-restore.sh`
already skips step 5 when the dump has no `plugin_registry.db`. The step 5 comment and the "Plugin registry" note in
`util/README.md` now mention this.

## Verification

Throwaway Docker sandbox: `--internal` network, everything labelled and prefixed; Postgres 16 with the repo's
`services/postgres` init scripts, MySQL 8.4, MinIO, an alpine SEEK stand-in, and the real builder image running this
branch's `services/builder/app` with no Docker socket; a `docker` guard first on PATH that refuses `docker compose`, any prune,
and any live container, volume or network name. `stage-dump.sh` ran end to end against it.

| Case | Before fix | After fix |
|---|---|---|
| New install (builder on Postgres, no SQLite file) | **exit 1 at step 5** (bug reproduced) | exit 0, skip message, no `plugin_registry.db` in the dump, portal tables in `digitaltwins.sql` |
| Old source (builder on SQLite, no portal tables) | exit 0, file copied | exit 0, file copied |
| Old source, builder stopped | exit 0, file copied | exit 0, file copied |
| Wrong builder name, no portal tables | exit 1, docker error only | exit 1, docker error + `FATAL`, dump not finished |

Also: `bash -n`; shellcheck clean; gitleaks finds nothing in the changed files. Sandbox removed by label and exact
name; no prune.
