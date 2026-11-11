# Walkthrough: the portal backend moves into services/api as the `builder` service

Plan: [implementation_plan.md](implementation_plan.md) · Tasks: [tasks.md](tasks.md) · ADR: [2026-10-20-merge-portal-backend-into-api-codebase](../../decisions/2026-10-20-merge-portal-backend-into-api-codebase.md)

Branch: `refactor/merge-portal-backend-into-api`, from `refactor/api-prefix-and-rename` (unmerged). The two deploy together.

## Baseline (`make test`, before any change)

| Suite | Result |
|---|---|
| test-api | 361 passed, 1 skipped, 214 deselected |
| test-portal-backend | 208 passed, 7 skipped |
| test-frontend | 33 files, 162 passed |
| test-jupyterhub | 5 passed |
| lint-python | 136 findings, all pre-existing |

## Commits

| # | Commit | Tests after |
|---|---|---|
| 1 | `refactor(api)!: move the portal backend into services/api as the builder service` | api 579 passed (8 skipped) = 361 API + 208 builder + 10 new; frontend 162; hub 5 |
| 2 | `refactor!: serve the builder at /api/builder` | api 579, frontend 162 |
| 3 | `refactor!: rename portal-backend env vars to BUILDER_*/PLATFORM_DOMAIN/KEYCLOAK_PUBLIC_URL` | api 582 (3 new) |
| 4 | `docs: …` (docs, ADR, these artifacts) | |

## Decisions made during implementation

- **The inner package is `builder/engine/`, not `builder/build/`.** `services/api/.gitignore` ignores every `build/` directory, so `build/` would have silently dropped out of git.
- **The tests live in `tests/builder_tests/`, not `tests/builder/`.** `services/api/tests` has no `__init__.py`, so pytest puts it on `sys.path`. A `tests/builder` package would then be imported as the top-level `builder` package and hide the real one.
- **`make test-api` mounts two more files read-only:** the portal-frontend nginx template and the root `docker-compose.yml`. Neither holds secrets. The builder's template test and the service-separation tests read them. CI's `api` path filter now covers both files.
- **`requirements-builder.txt` holds the builder's dependencies:**
  - It adds SQLAlchemy 2.0.44, httpx 0.28.1, python-keycloak 3.9.0 and PyYAML 6.0.2 to the API's.
  - These are the versions from the old `uv.lock`. FastAPI moves from 0.119.1 to the API's pinned 0.116.1, and every builder test passes on it.
  - The imaging packages (`simpleitk`, `scikit-image`, `nibabel`, `pynrrd`, `pandas`, …) are dropped: nothing imports them.
- **The builder's base definition is `services/api/docker-compose.builder.yml`.** The root compose extends it. It isn't validated on its own, because its network and volumes are declared at the root, as they were for `portal-backend`.
- **portal-frontend's `depends_on: builder` moved to the root compose,** so the standalone portal compose stays valid without a backend.
- **The builder container keeps `WORKDIR /api`,** like the API image. `portal_datasets` is now mounted at `/api/data` (it was `/app/data`). Every other mount path is unchanged.
- **Two scripts change in commit 1, not commit 3.** `util/stage-dump.sh` and `util/portal-restore.sh` address the container by name, so they would break as soon as the service is renamed. Their variable is now `BUILDER_C`.
- **The builder's route test is stricter.** It now allows only `/`, `/health`, the docs routes and `/api/builder/*`; before, it only checked the `/api` routes.
- **New tests in commit 3:** the metadata URL host and the CORS origin both come from `PLATFORM_DOMAIN`. Neither had a test before.
- **The upgrade notes say plugin backends must be redeployed.** On shutdown the builder stops every plugin backend it started and marks it down. At startup it only reattaches backends that are still running, so it doesn't start them again. That was true for every `portal-backend` restart too.
- **The `/digitaltwins-api` upgrade section in `docs/deployment.md` now covers both moves,** because both branches deploy together.

## Phase 7: docs, tests, scripts and examples

| Item | How | Result |
|---|---|---|
| Unit tests | `make test` | ✓ api 582 passed (8 skipped), frontend 33 files / 162, hub 5 |
| Python lint | `make lint-python` | ✓ 136 findings, unchanged; none in changed lines |
| Secrets | `make gitleaks` over this branch's commits | ✓ no leaks; the pre-commit hook passed on each commit |
| Both image targets | `docker compose build api builder` | ✓ built. `api` has no `docker`, `git`, `node`, `npm` or `yarn`, and holds `app/` and `src/` only. `builder` has all of those tools, imports `builder.main`, and has no `app` module |
| Resolved compose | `docker compose config` with `BUILDER_DB_PASSWORD` set in the shell; key names printed, not values | ✓ the builder's env has no `POSTGRES_*`, `JUPYTERHUB_*`, `AIRFLOW_*` or `SEEK_*`. The socket is on `builder` only. `api` has `BUILDER_URL` |
| Gateway nginx | `nginx -t` in a throwaway `nginx:1.30.3-alpine`, http conf | ✓ syntax ok |
| Portal nginx template | rendered by the stock entrypoint with `BUILDER_PORT`, then `nginx -t` | ✓ syntax ok; three `proxy_pass http://$up_builder:8000` |
| `util/renew-cert.sh`, `stage-dump.sh`, `portal-restore.sh`, `services/postgres/portal_init.sh` | `shellcheck -S warning` (v0.10.0) | ✓ clean |
| `util/gen-env.sh` | dummy `env` and `secrets.env` in a scratch directory | ✓ writes `BUILDER_PORT`, `BUILDER_URL`, `BUILDER_DB_PASSWORD`, `PLATFORM_DOMAIN` and `KEYCLOAK_PUBLIC_URL`, and none of the old names. With the old `PORTAL_DB_PASSWORD` key it stops: "template needs these vars but they are unset/empty: BUILDER_DB_PASSWORD" |
| Builder, `services/api/examples`, `examples/workflow` Python | compiled in memory (Python 3.11) | ✓ 58 files, 0 failures |
| Relative links in edited markdown | script over 21 links | ✓ all resolve, except two that were already broken before this branch (see Flagged) |
| Rename gate | `git grep` for `portal-backend`, `PORTAL_BACKEND_*`, `PORTAL_DB_*` (except `PORTAL_DB_SCHEMA`), `PORTAL_KEYCLOAK_BASE_URL`, `BACKEND_PORT`, `/api/portal`, `services/portal/backend` over the live tree (excluding artifacts, decisions and release notes) | ✓ only intentional mentions: the upgrade notes, the ADR's file name, and the plugin FAQ that names the ADR |

## Phase 8: live checks (full stack, rebuilt and started locally)

Setup:
- Backed up `.env`, `env` and `secrets.env`.
- In `secrets.env`, renamed `PORTAL_DB_PASSWORD` to `BUILDER_DB_PASSWORD`, keeping the value.
- Regenerated `.env` with `util/gen-env.sh`. Compared by name: `BACKEND_PORT`, `PORTAL_BACKEND_HOST`, `PORTAL_BACKEND_URL`, `PORTAL_DB_PASSWORD` and `PORTAL_KEYCLOAK_BASE_URL` are gone, and `BUILDER_DB_PASSWORD`, `BUILDER_PORT` and `BUILDER_URL` are new. Every other value is unchanged, and each renamed variable carries its old value.
- `docker compose build api builder portal-frontend`, `docker compose up -d --remove-orphans`, then the gateway `nginx -t` and reload.

`database` was recreated too, because its environment names `BUILDER_DB_PASSWORD`; its volume was untouched. The host was later restarted and the stack brought down. `docker compose up -d` brought it back, and the checks after the CLI row ran on that fresh start.

| Check | Result |
|---|---|
| All services healthy; no `portal-backend` container left | ✓ (also after the fresh start) |
| Builder startup | ✓ `init_db` on Postgres as role `portal` (`postgresql+psycopg2`, user `portal`, db `digitaltwins`); reconcile found no deployed plugins (none were deployed before the cut-over) |
| `api` container | ✓ no `docker`, `git`, `node`, `npm` or `yarn`; no Docker socket; no builder code |
| `builder` container | ✓ no `POSTGRES_*`, `JUPYTERHUB_*`, `AIRFLOW_*`, `SEEK_*` or `API_PUBLIC_URL` in its environment; has the socket; no `app/` |
| `/api/health` | ✓ 200 |
| Unauthenticated `/api/builder/tools/`, `/api/builder/workflow/gui-tool`, `/api/builder/tools/builds/<id>/logs/stream` | ✓ 401 from the builder ("Missing Authorization header") |
| Unauthenticated `/api/dashboard/programmes` | ✓ 401 from the API |
| `/api/portal/tools/` | 404 JSON from the API. Expected after the hard cut-over: the gateway's `/api/` block takes it (the plan had guessed the SPA fallback) |
| API container → `BUILDER_URL` (`http://builder:8000`) `/api/builder/workflow/gui-tool` | ✓ 401, so it is reachable over the Docker network |
| Authenticated `/api/builder/tools/`, `/workflow/`, `/tools/metadata`, `/workflow/gui-tools`, `/workflow/gui-tool`, `/tools/builds` | ✓ 200 |
| `/api/builder/workflow/metadata` | ✓ component paths are `http://<PLATFORM_DOMAIN>/api/builder/workflow/<expose>/primary` |
| GUI assay launch through `/api/dashboard/assay-launch` (the API asks the builder for the tool) | ✓ `{"type":"gui","data":"/tool-view?assay=…"}` |
| Build logs, `/api/builder/tools/builds/<build_id>/logs`, for a tool build and a workflow build | ✓ 200 `text/plain` |
| SSE `/api/builder/tools/builds/<build_id>/logs/stream` | ✓ 200 `text/event-stream` (a finished build ends with `event: end`) |
| `POST /api/builder/{tools,workflow}/upload-source` with no file | ✓ 422 from the builder, through portal-frontend's upload-source location |
| `python -m builder.cli.{migrate_sqlite_to_postgres,purge_legacy_measurements,purge_legacy_tools} --help` in the builder container | ✓ |
| `migrate_sqlite_to_postgres --dry-run`, both `docker exec` and the deployment guide's `docker compose run --rm builder ...` | ✓ connects as `portal`; refuses because the target already has rows, as designed |
| `purge_legacy_measurements --dry-run`, `purge_legacy_tools --dry-run` | ✓ reach MinIO and FHIR; nothing to purge |
| `util/stage-dump.sh`, builder step only (`docker cp ${PROJECT}-builder-1:/data/plugin_registry.db`) | ✓ copied. The full dump wasn't run: it copies every database, bucket and volume |
| `util/portal-restore.sh`, `util/renew-cert.sh` | static only (shellcheck): restore is destructive, and renew needs a real domain and ACME |

**Note:** while checking the resolved compose config, one command (`docker compose config builder`) also printed the `database` service's environment, which includes its password, into the local session output. Nothing was written to a file or an artifact.

## Flagged

- **Before merge:** the repo ruleset "CI required checks" must drop "portal-backend unit tests", or PRs wait for a check that never reports. An admin runs:
  ```bash
  R=repos/ABI-CTT-Group/digitaltwins-platform/rulesets/25213776
  gh api "$R" | jq '{name, target, enforcement, conditions, bypass_actors,
      rules: [.rules[] | if .type == "required_status_checks"
        then .parameters.required_status_checks |= map(select(.context != "portal-backend unit tests"))
        else . end]}' > ruleset.json
  gh api -X PUT "$R" --input ruleset.json
  ```
  The current required checks, read on 2026-10-20: `api unit tests`, `portal-backend unit tests`, `frontend unit tests`, `jupyterhub unit tests`, `gitleaks (PR commits)`.
- Builds are still not sandboxed (see the ADR). This is a follow-up.
- Two migration systems and two Keycloak verifiers now sit in one codebase (follow-ups).
- **Pre-existing bugs, ported unchanged:**
  - Writes to the nonexistent columns `error` and `error_message` are lost.
  - `/api/builder/tools/test-build` calls a missing method.
  - The CORS origin list grows on every request.
  - The Keycloak key is cached forever.
  - Blocking subprocess calls run inside `async` handlers.
- **Pre-existing, left alone:**
  - In `docs/diagnostics.md`, section (b) says portal-frontend's nginx uses a literal `proxy_pass`. The template has used a `set` variable with a resolver for some time, so that failure mode mostly no longer applies.
  - Two broken relative links: `api_examples.md` in `docs/diagnostics.md`, and `RemoteComponentApp.vue` in `plugin-system-architecture.md`.
  - The builder still publishes host port 8000, as `portal-backend` did.
