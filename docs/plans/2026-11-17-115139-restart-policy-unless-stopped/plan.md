# Plan: `restart: unless-stopped` for every long-running platform service

## Context

Restart policies across the compose files are inconsistent. `api` and `minio` have **none**, so after a
crash or a host reboot they stay down while the rest of the stack comes back. Airflow and redis use
`always` (copied from Airflow's upstream compose file), hapi-fhir uses `on-failure`, and the rest use
`unless-stopped`. For production we chose **`unless-stopped`** everywhere: services recover from crashes
and reboots, but a service an operator stopped on purpose stays stopped across a reboot.

**Exception (required, not optional):** one-shot jobs must **not** get `unless-stopped`. That policy
also restarts a container that exits cleanly, so an init job would re-run in an endless loop. These keep
no policy or `"no"`: `airflow-init`, `airflow-cli` (debug profile), `minio-init` (both files),
`minio-logs-init`, and `singleuser` (its command is `echo "Image built successfully"`).

**Branch:** `dev_chinchien` (exists locally and on origin; 0 commits ahead of `origin/main`, 22 behind).
Check it out and fast-forward it to `origin/main`, then PR into `main`. Merging into `prototype` happens later.

## Changes

Pattern: set `restart: unless-stopped` on each long-running service; leave one-shots alone.

| File | Service(s) | Now → New |
|---|---|---|
| `services/api/docker-compose.yml` | api | none → `unless-stopped` |
| `services/minio/docker-compose.yml` | minio | none → `unless-stopped` |
| `services/airflow/docker-compose.yml` | redis, airflow-apiserver, -scheduler, -dag-processor, -worker, -triggerer, flower | `always` → `unless-stopped` |
| `services/airflow/compute-worker/docker-compose.yml` | airflow-worker (remote compute node) | `always` → `unless-stopped` |
| `services/hapi-fhir/docker-compose.yml` | hapi-fhir | `on-failure` → `unless-stopped` (still retries until Postgres is up; update the inline comment) |
| `services/hapi-fhir/README.md:65` | – | reword the "`restart: on-failure` retries…" note to `unless-stopped` |
| Leftover/unused files, for consistency: `services/portal/docker-compose.yml` (minio, hapi-fhir, hapi-fhir-postgres), `services/api/docker/orthanc/…` (orthanc), `services/api/docker/postgres/…` (digitaltwins_postgres) | as listed | → `unless-stopped` |

Left alone: the commented-out Airflow postgres block (`#   restart: always`), already-`unless-stopped`
services, `services/portal/docker-compose.override.yml` (port publish only), and the SEEK submodule
`services/seek/ldh-deployment` (a separate repo whose services are already `unless-stopped`).

## TDD: regression test (written first, fails red)

New `util/tests/test_restart_policy.sh`, which `make test-util` picks up automatically (same style as
`util/tests/test_compose_file.sh`; bash + awk, no Docker needed):
- Scans `services/**/*compose*.yml`, skipping `*override*` files and `services/seek/ldh-deployment/`.
- For each service under `services:`: one-shots in an allowlist (above) must **not** be `unless-stopped`;
  every other service must have `restart: unless-stopped`. Failures print `file service got-value`.
- `Makefile` `test-util`: mount each tracked service compose file read-only
  (`COMPOSE_FILES := $(shell git ls-files 'services/*compose*.yml')`), replacing the single airflow
  compose mount. *Revised during implementation:* mounting all of `services/` would also expose the
  untracked, rendered Keycloak realm (`services/keycloak/import/`), which can hold client secrets.

Red: the test fails on api, minio, airflow, hapi-fhir, etc. Green after the edits.

## Docs and process

- `docs/plans/2026-11-17-115139-restart-policy-unless-stopped/` → `plan.md` (this plan) + `tasks.md` checklist, ticked as I go.
- ADR `docs/decisions/2026-11-17-restart-policy-unless-stopped.md` (template: `docs/decisions/TEMPLATE.md`):
  options `always` / `unless-stopped` / mixed (status quo); decision `unless-stopped` for long-running,
  `"no"`/none for one-shots; consequences: deviates from upstream Airflow compose, stopped services stay
  down after reboot, a restart policy doesn't restart hung-but-running containers.

## Steps

1. `git checkout dev_chinchien && git merge --ff-only origin/main` → verify: `git log -1` shows `55b59f42`
2. Write plan.md + tasks.md + ADR in `docs/plans/…` / `docs/decisions/`
3. Write `test_restart_policy.sh` + Makefile mount → verify: `make test-util` **fails** listing the gaps
4. Edit the compose files + hapi-fhir README → verify: `make test-util` passes
5. `make lint`, `make docs-check` (after `git add`), `make gitleaks`
6. `docker compose config --format json | jq` restart table → only one-shots lack `unless-stopped`
7. Commit (conventional: `fix(compose): use restart unless-stopped for all long-running services`), then
   on your go-ahead push and open the PR into `main`

## Applying to the running local stack

A restart-policy change needs no rebuild. To apply it to running containers **without restarting them**:
```bash
docker update --restart unless-stopped <container names of the changed services>
```
I'll only run this on the local stack after asking. Note for staging, demo and production: the next
`docker compose up -d <svc>` will recreate each changed service once, because compose sees the config change.

## Verification

- `make test-util` red → green; `make test`, `make lint` and `make docs-check` pass.
- `docker compose config` shows `unless-stopped` for every service except the one-shots.
- Optional, after merge: reboot staging and confirm the whole stack comes back by itself.
