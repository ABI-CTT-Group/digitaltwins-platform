# Tasks: move the portal backend into services/api as the `builder` service

Plan: [implementation_plan.md](implementation_plan.md)

Legend: `[x]` done · `[ ]` to do · `[~]` in progress · `[!]` blocked or flagged

## Housekeeping
- [x] Branch `refactor/merge-portal-backend-into-api` from `refactor/api-prefix-and-rename`
- [x] Sync the plan to `docs/artifacts/`
- [x] Baseline `make test`: api 361 passed (1 skipped), portal 208 passed (7 skipped), frontend 162, hub 5
- [x] Create this task list
- [ ] Sync artifacts to `docs/artifacts/` after every task-list or plan change

## Phase 1: move the code
- [x] `git mv` `services/portal/backend/app` → `services/api/builder`
- [x] Inner `app/builder/` → `builder/engine/` (not `build/`: `services/api/.gitignore` ignores `build/`)
- [x] `git mv` `services/portal/backend/tests` → `services/api/tests/builder_tests/` (not `tests/builder/`: pytest would import it as the top-level `builder` package and shadow the real one)
- [x] Rewrite imports: `app.` → `builder.`, `app.builder.` → `builder.engine.`, `tests.` → `builder_tests.`, plus the `mock.patch` strings
- [x] Fix test paths (`BACKEND_ROOT`, the live-DB guard subprocess, the nginx template path)
- [x] `requirements-builder.txt`: prod requirements plus sqlalchemy, httpx, python-keycloak, pyyaml. The unused imaging packages are dropped. Include it from `requirements-test.txt`
- [x] Ignore the builder's runtime junk (`tmp/`, `app.log`, `*.db`) in `services/api/.gitignore`
- [x] Remove the rest of `services/portal/backend` (the readme was only uv instructions; `services/api/docs/builder.md` is written in Phase 6). Your untracked local leftovers there are excluded via `.git/info/exclude`, not deleted
- [x] Builder tests pass on Python 3.11 in `make test-api`

## Phase 2: image, compose, separation
- [x] Red: `tests/test_service_separation.py` checks the docker.sock mount, builder env secrets, route sets, cross-imports and Dockerfile targets
- [x] Multi-stage `services/api/Dockerfile` with `api` and `builder` targets
- [x] `services/api/docker-compose.builder.yml`. The root compose changes `portal-backend:` to `builder:`, and portal-frontend `depends_on` points at `builder`
- [x] Remove `portal-backend` from `services/portal/docker-compose.yml`
- [x] API compose: `target: api`, `BUILDER_URL`
- [x] Portal-frontend nginx: `$up_builder` and `BUILDER_PORT`
- [x] Green: `make test-api`, `docker compose config -q`

- [x] Also done for commit 1, so it works on its own:
  - the util scripts' container name (`BUILDER_C`)
  - `docs/testing.md`
  - service-name comments
- [x] Both image targets built. `api` has no Docker CLI, git or Node and no builder code; `builder` has them and no `app/`
- [x] Commit-1 state: `make test` gives api 579 passed (8 skipped), frontend 162, hub 5. `lint-python` is at 136 findings (unchanged), none in changed files

## Phase 3: `/api/portal` → `/api/builder`
- [x] Red: builder route tests, metadata URL, API dashboard lookup URL, frontend specs, nginx template test
- [x] Builder router prefixes and generated URLs
- [x] API `dashboard._fetch_gui_tool`
- [x] Frontend `http.ts`, `tool_api.ts`, `types.ts` comments, `vite.config.ts`
- [x] Portal-frontend nginx template; gateway `platform-routes.conf` and snippet comments
- [x] Green: `make test-api test-frontend`; `nginx -t` passes on the gateway config and on the rendered portal template

## Phase 4: env var renames
- [x] Red: DB config, env scrub, Keycloak config (`KEYCLOAK_PUBLIC_URL` fallback), live-DB guard
- [x] Templates: `.env.template`, `secrets.env.template`, `services/portal/.env.template`, `services/api/.env.template`
- [x] Compose: root, builder, API, postgres; `services/postgres/portal_init.sh`
- [x] Builder code: `db_model`, `database`, `proc_stream`, `keycloak`, `main` (CORS), `workflow_router` (host), the CLI
- [x] Scripts: `util/renew-cert.sh`, `util/stage-dump.sh`, `util/portal-restore.sh`
- [x] Rename gate: `git grep` returns only intentional mentions

## Phase 5: Makefile and CI
- [x] Makefile: drop `test-portal-backend`; `test-api` mounts `services/portal/frontend` read-only; update the `lint-python` paths
- [x] `ci.yml`: drop the `portal-backend` job and its filter; the `api` filter also covers the nginx template
- [x] Write the ruleset `gh api` command for an admin (in `walkthrough.md`; not run)

- [x] Added tests: the metadata URL host and the CORS origin both come from `PLATFORM_DOMAIN`
- [x] Compose resolves (`BUILDER_DB_PASSWORD` supplied in the shell): the builder's env has no `POSTGRES_*`, `JUPYTERHUB_*`, `AIRFLOW_*` or `SEEK_*`; the socket is mounted on the builder only
- [x] shellcheck is clean: `renew-cert.sh`, `stage-dump.sh`, `portal-restore.sh`, `portal_init.sh`
- [x] Local commits: `4954fb9a` (1), `a036e2c3` (2), `844cbe23` (3)

## Phase 6: docs
- [x] `docs/{deployment,testing,diagnostics,domain-change,production,gateway-pathway-access}.md`
- [x] `services/api/docs/builder.md` (new), `services/nginx/README.md`, `services/portal/docs/*`, `services/api/README.md`, `services/keycloak/REALM.md`, `util/README.md`, `util/BUILD-FULL-SYSTEM.md`, root `README.md`
- [x] Upgrade section in `docs/deployment.md`
- [x] ADR `docs/decisions/2026-10-20-merge-portal-backend-into-api-codebase.md`; "superseded in part" line on the split ADR
- [x] Sync artifacts to `docs/artifacts/`

## Phase 7: docs, tests, scripts and examples verified
- [x] `make test`, `make lint`, `make gitleaks`
- [x] `nginx -t` (gateway); portal nginx template test
- [x] shellcheck and `bash -n`: `stage-dump.sh`, `portal-restore.sh`, `renew-cert.sh`
- [x] `gen-env.sh` against dummy inputs
- [x] `py_compile` of the examples; the import-dataset scripts
- [x] Doc snippets and relative links
- [x] Record the results in `walkthrough.md`; sync artifacts

## Phase 8: live end-to-end (ask before mutating steps)
- [x] Back up `.env` and `secrets.env`, rename the secret key, regenerate `.env`, build, `up -d --remove-orphans`, reload the gateway
- [x] Separation checked live: no Docker, git or Node in `api`; no socket in `api`; no API secrets in `builder`
- [x] curl matrix
- [x] Authenticated flows: Tool Hub, logs and SSE, upload-source, GUI assay launch, plugin backends after the cut-over
- [x] Builder CLIs (`--dry-run` / `--help`); stage-dump live
- [x] Record the results in `walkthrough.md`; sync artifacts

## Commits (only when asked)
- [x] 1 `refactor(api)!: move the portal backend into services/api as the builder service`
- [x] 2 `refactor!: serve the builder at /api/builder`
- [x] 3 `refactor!: rename portal-backend env vars to BUILDER_*/PLATFORM_DOMAIN/KEYCLOAK_PUBLIC_URL`
- [x] 4 `docs: document the builder service and the move out of services/portal/backend`

## Flagged
- The ruleset must drop "portal-backend unit tests" before merge
- Builds are still not sandboxed (follow-up)
- Pre-existing bugs ported unchanged: `error`/`error_message` columns, `/tools/test-build`, CORS list growth, Keycloak key cached forever, blocking calls in `async`
