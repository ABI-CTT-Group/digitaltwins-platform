# Plan: move the portal backend into the API codebase as the `builder` service

## Context

`services/portal/backend` (compose service `portal-backend`) is a second FastAPI app beside the platform API (`services/api`). The user wants it folded into the API.

The interview settled the shape: **option 2, one codebase with two containers.**
- The code, the image definition and the tests move into `services/api`.
- The privileged part runs as its own service, **`builder`**, built from the same Dockerfile.

Why it isn't one container:
- The builder clones user repos, runs `npm install` and plugin build commands, and runs plugin `docker compose` against the **host** Docker socket.
- Build steps inherit the whole service environment except `PORTAL_DB_*` (`app/builder/proc_stream.py:39`).
- **There is no sandboxing today.** Builds run as root next to the host socket. Option 2 keeps that exposure confined to `builder`, exactly as `portal-backend` is now, and adds none to `api`. Build sandboxing is out of scope; it's recorded as a follow-up.

This branch reverses option D ("same codebase in two containers"), which the decision record `docs/decisions/2026-10-20-api-prefix-and-portal-builder-split.md` rejected, so a new ADR records the change.

### Decisions from the interview
- **Shape:** option 2, with four separations, each enforced by a test:
  1. **Image targets:** one Dockerfile with targets `api` and `builder`. The `api` image keeps today's contents: no git, Node or Docker CLI, and no builder code. The `builder` image holds only the builder package plus its tools.
  2. **Entry points:** `app.main:app` serves the API routes only. `builder.main:app` serves the builder routes only.
  3. **Environment:** `builder` gets an explicit, minimal set. It has no `POSTGRES_PASSWORD`, `JUPYTERHUB_API_TOKEN`, Airflow credentials or `API_PUBLIC_URL`, and it keeps the `portal` DB role, not the superuser.
  4. **Docker socket:** mounted on `builder` only.
- **Branch:** `refactor/merge-portal-backend-into-api`, from `refactor/api-prefix-and-rename` (unmerged, unpushed). Its PR targets `main` after the first one merges, or targets the first branch until then.
- **GUI-tool lookup:** stays an HTTP call from the API to `builder` (URL renamed). The API never reads the `portal` schema.
- **CI:** the builder tests fold into `make test-api` and the job "api unit tests". The `portal-backend` job and `make test-portal-backend` are removed. A repo admin must remove "portal-backend unit tests" from ruleset "CI required checks" (id 25213776) **before** the PR merges. I'll print the `gh api` command and won't run it.
- **Service name:** `builder` (compose service, DNS, container `${PROJECT_NAME}-builder-1`).
- **Public path:** `/api/portal/{tools,workflow}` becomes **`/api/builder/{tools,workflow}`**. `/api/portal` has never shipped, so this costs nothing beyond the first branch's cut-over.
- **Rename every `portal-backend` name, env vars included.** Names that hold data stay as they are:
  - Postgres schema and role `portal`
  - the volumes `portal_workspace`, `portal_datasets`, `plugin_database` and `nginx_plugin_configs`
- **Scope:** every doc, test, script and example is updated and verified (see Phase 7).

### Env var renames
| Old | New | Note |
|---|---|---|
| `PORTAL_BACKEND_URL` | `BUILDER_URL` (`http://builder:8000`) | read by the API dashboard |
| `BACKEND_PORT` | `BUILDER_PORT` | portal-frontend nginx envsubst |
| `PORTAL_BACKEND_HOST` | `PLATFORM_DOMAIN` | already in `.env` with the same value; the alias is dropped. Used by the builder, the API (`HOSTNAME`) and `util/renew-cert.sh` |
| `PORTAL_KEYCLOAK_BASE_URL` | `KEYCLOAK_PUBLIC_URL` | already in `.env` with the same value; the alias is dropped |
| `PORTAL_DB_{HOST,PORT,NAME,USER,PASSWORD}` | `BUILDER_DB_*` | still the `portal` role and schema. `PORTAL_DB_PASSWORD` lives in the hand-filled `secrets.env`, so the upgrade must **rename the key and keep its value** |
| `PORTAL_TEST_DB_HOST` | `BUILDER_TEST_DB_HOST` | |
| `PORTAL_BE_C` (util scripts) | `BUILDER_C` | |

Plugin compose files interpolate against the builder's environment. The documented plugin contract (`MINIO_SERVER_*`, `PROJECT_NAME`, `SSL`) is unchanged. No plugin in the repo uses `PORTAL_*`. An external plugin that reads `${PORTAL_BACKEND_HOST}` would fall back to its own default; this is flagged.

### My calls (not discussed; the user can override at review)
- **Code location:** `services/api/builder/` is a top-level package beside `app/` and `src/`.
  - It is not inside `src/digitaltwins`, so the pip/PyPI package doesn't ship Docker-builder code.
  - The internal layout is kept. Imports change from `app.` to `builder.`.
  - The inner `app/builder/` subpackage (build_tool, deploy_tool, …) becomes `builder/engine/`, to avoid `builder.builder`. (Not `build/`: `services/api/.gitignore` ignores every `build/` directory.)
- **Ported as-is:** the SQLAlchemy models, the `portal` schema, `init_db`'s own migrations and its own Keycloak verifier. Two follow-ups are noted but not done here: unifying migrations, and unifying auth with `app/routers/auth.py`.
- **Python:** the builder moves from 3.9 to the API's 3.11. Its dependencies go in a new `requirements-builder.txt` (`-r requirements-prod.txt` plus SQLAlchemy, httpx, python-keycloak, …). `requirements-test.txt` includes it. Pinned imaging packages that nothing imports (`simpleitk`, `scikit-image`, `nibabel`, `pynrrd`, `pandas`, …) are dropped, after an import grep confirms they're unused. The stale `requirements.txt` and `uv.lock` go with the old directory.
- **Gateway chain kept:** gateway → portal-frontend nginx → builder. The upload-source and SSE tuning stays where it is.
- **Compose:**
  - The builder's base definition goes in a separate `services/api/docker-compose.builder.yml`, which isn't included.
  - The root `docker-compose.yml` defines `builder:` by `extends` and adds `BUILDER_DB_*` and `depends_on: database`, exactly as it does for `portal-backend` today. The included `services/api/docker-compose.yml` can't see `database`.
- **Standalone portal-only stack:** `services/portal/docker-compose.yml` no longer defines a backend. Standalone frontend development uses the Vite proxy to a locally run builder. This is flagged.
- **Pre-existing bugs found, ported unchanged and flagged:**
  - Writes to the nonexistent columns `error` and `error_message` are silently lost.
  - `/tools/test-build` calls a missing method.
  - The CORS origin list grows on every request.
  - The Keycloak key is cached forever.
  - Blocking subprocess calls inside `async` handlers.

## Housekeeping (on approval)
- `git switch -c refactor/merge-portal-backend-into-api refactor/api-prefix-and-rename`. Record a baseline with `make test` (expected: api 361, portal 208, 7 skipped, frontend 162, hub 5).
- Sync this plan to `docs/artifacts/<YYYY-MM-DD-HHMMSS>-merge-portal-backend-into-api/implementation_plan.md` immediately, and again after each update. Use repo-relative paths, no secrets, and no local live-operation details.
- Write the ADR `docs/decisions/2026-10-20-merge-portal-backend-into-api-codebase.md` from `TEMPLATE.md`:
  - It records options 1, 2 and 3, the four separations, and the fact that builds aren't sandboxed (with sandboxing as a follow-up).
  - Add a "superseded in part by …" line to the 2026-10-20 split ADR.
- The six unrelated untracked artifact folders stay untracked.

## Phase 1: move the code (git mv, so history follows)
- `git mv services/portal/backend/app services/api/builder` and `git mv services/portal/backend/tests services/api/tests/builder_tests` (not `tests/builder`: pytest would import that as the top-level `builder` package and hide the real one). Then move `app/builder` to `builder/engine`.
- Rewrite imports (`app.` → `builder.`, `app.builder.` → `builder.engine.`, `tests.` → `builder_tests.`), including `patch("app....")` strings in tests.
- Fix the test harness:
  - `tests/builder_tests/__init__.py` keeps the live-DB guard, renamed to `BUILDER_DB_HOST`.
  - `tool_app.py` keeps its fakes.
  - Module basenames that clash with `services/api/tests` get a `test_builder_` prefix.
  - Tests that read `../frontend/nginx.conf.template` resolve the path from the repo root.
- Move the builder's `readme.md` content into `services/api/docs/builder.md`. Delete the leftover `services/portal/backend` (`Dockerfile`, `pyproject.toml`, `uv.lock`, `requirements.txt`). Ignored local junk (`app.log`, `tmp/`, `*.db`) isn't tracked.
- **Verify:** builder tests pass under Python 3.11 in `make test-api`.

## Phase 2: image, compose and separation (tests first)
**Separation tests (red first)**, in new `services/api/tests/test_service_separation.py`:
- Parse `docker compose config` output (or the YAML files):
  - `builder` mounts `/var/run/docker.sock` and `api` doesn't.
  - `builder`'s environment has none of `POSTGRES_PASSWORD`, `POSTGRES_USER`, `JUPYTERHUB_API_TOKEN`, `AIRFLOW_*`, `API_PUBLIC_URL`.
  - `builder` has `BUILDER_DB_USER=portal`.
- Build both apps:
  - `app.main.app` has no `/tools/plugin`, `/workflow/...` or other builder routes.
  - `builder.main.app` has only `/`, `/health`, the docs routes and routes under `/api/builder/`. This updates `test_route_prefixes.py`.
  - Importing `app.main` doesn't import `builder`, and the reverse holds too.
- Dockerfile targets:
  - The `api` stage installs no `docker-ce-cli`, git or node, and doesn't copy `builder/`.
  - The `builder` stage doesn't copy `app/`.

**Code:**
- **`services/api/Dockerfile`** becomes multi-stage:
  - `api` target: today's steps, with `WORKDIR /api`.
  - `builder` target: `python:3.11-slim` plus git, curl, gnupg, libpq-dev, gcc, Volta with node 22 and yarn, and `docker-ce-cli` with the compose plugin. It installs `requirements-builder.txt`, copies `builder/`, and runs `uvicorn builder.main:app --proxy-headers --forwarded-allow-ips *`.
  - `services/api/docker-compose.yml` sets `build.target: api`.
- **New `services/api/docker-compose.builder.yml`** holds the builder service, with `target: builder`. It carries over portal-backend's environment, volumes (same volume names), docker.sock, `stop_grace_period: 60s`, healthcheck, network, ports and `depends_on: minio`, with the env renames applied.
- **Root `docker-compose.yml`:**
  - `portal-backend:` becomes `builder:`, which extends the file above and keeps its comments.
  - `portal-frontend`'s `depends_on` points at `builder`.
- Remove `portal-backend` from `services/portal/docker-compose.yml`.
- **API compose:** `PORTAL_BACKEND_URL` → `BUILDER_URL: ${BUILDER_URL:-http://builder:8000}`, and `HOSTNAME: ${PLATFORM_DOMAIN:-localhost}`.
- **Portal-frontend nginx:** `$up_backend` → `$up_builder` (`set $up_builder builder`), `${BACKEND_PORT}` → `${BUILDER_PORT}`, and the envsubst filter is updated.
- **Verify:** `make test-api`, plus `docker compose config -q`.

## Phase 3: `/api/portal` → `/api/builder` (tests first)
**Tests (red first):**
- The builder tests switch to `/api/builder/...`.
- The `/workflow/metadata` URL becomes `{proto}://{PLATFORM_DOMAIN}/api/builder/workflow/{expose}/primary`.
- The API dashboard test expects `{BUILDER_URL}/api/builder/workflow/gui-tool`.
- Frontend specs:
  - `http.spec.ts`: `baseURL === "/api/builder"`.
  - `tool_logs.spec.ts`: `/api/builder/tools/...`.
- `test_frontend_nginx_template.py`: only `/api/builder/` reaches `$up_builder`, plus the exact upload-source and SSE regexes.

**Code:**
- The router prefixes in `builder/router/workflow_tool_plugin.py` and `workflow_router.py`, and the generated URLs and messages.
- `services/api/app/routers/dashboard.py` `_fetch_gui_tool`.
- Frontend:
  - `src/bootstrap/http.ts` (axios default baseURL)
  - `tool_api.ts` `_logPath`
  - comments in `models/types.ts`
  - `vite.config.ts` (proxy `/api/builder` → `:8000`, listed first)
- `nginx.conf.template`: the regexes and the generic location.
- **Gateway:** in `services/nginx/snippets/platform-routes.conf`, `location /api/portal/` becomes `location /api/builder/`; also update its comments and the `portal-proxy.conf` and `portal-fallback.conf` comments.
- **Verify:** `make test-api test-frontend`, plus `nginx -t` in a throwaway `nginx:1.30.3-alpine` (as on the last branch).

## Phase 4: env var renames (tests first)
**Tests:** builder DB-config, subprocess-env-scrub (which now strips `BUILDER_DB_*`), Keycloak-config and live-DB-guard tests switch to the new names. Add one case: the builder falls back to `KEYCLOAK_PUBLIC_URL` when `KEYCLOAK_BASE_URL` is unset.

**Code** (apply the rename table everywhere):
- **Env templates:** `.env.template`, `secrets.env.template`, `services/portal/.env.template`, `services/api/.env.template`.
- **Compose:** root, builder, API and postgres compose files.
- **Postgres init:** `services/postgres/portal_init.sh` reads `BUILDER_DB_PASSWORD`. The role and schema stay `portal`.
- **Builder code:**
  - `builder/models/db_model.py`, `database/database.py`, `engine/proc_stream.py`
  - `client/keycloak.py`, `main.py` (CORS), `router/workflow_router.py` (host)
  - `cli/migrate_sqlite_to_postgres.py`
- **Scripts:**
  - `util/renew-cert.sh`: read `PLATFORM_DOMAIN` from `.env`.
  - `util/stage-dump.sh` and `util/portal-restore.sh`: `BUILDER_C="${PROJECT}-builder-1"`, plus their messages.
- **Rename gate:** `git grep -nE "portal-backend|portal_backend|PORTAL_BACKEND_|PORTAL_DB_|PORTAL_KEYCLOAK_BASE_URL|PORTAL_TEST_DB|\bBACKEND_PORT\b|/api/portal"` over the live tree returns only intentional mentions:
  - the upgrade notes
  - `PORTAL_DB_SCHEMA`-style references to the kept `portal` schema and role
  - volume names

  `docs/artifacts`, `docs/decisions`, release notes and applied migrations are excluded.

## Phase 5: Makefile and CI
- **`Makefile`:**
  - Remove `test-portal-backend`, and drop it from `test` and `.PHONY`.
  - `test-api` also mounts `services/portal/frontend` read-only.
  - `lint-python` lints `services/api` (which now includes the builder) and drops `services/portal/backend`.
- **`.github/workflows/ci.yml`:**
  - Remove the `portal-backend` job and its `portal_backend` filter.
  - The `api` filter also matches `^services/portal/frontend/nginx\.conf\.template$`.
  - Keep the "don't rename" comment accurate.
- **Ruleset command for the admin** (written into the PR description and walkthrough, not run): `gh api repos/{owner}/{repo}/rulesets/25213776` GET, then PUT with "portal-backend unit tests" removed from `required_status_checks`.

## Phase 6: docs
- **Live docs to update:**
  - `docs/{deployment,testing,diagnostics,domain-change,production,gateway-pathway-access}.md`
  - `services/nginx/README.md`
  - `services/portal/docs/{deployment-guide,plugin-system-architecture}.md` (CLI commands become `docker compose run --rm builder python -m builder.cli.migrate_sqlite_to_postgres`)
  - `services/api/README.md` (a builder section and the two-container layout)
  - `services/keycloak/REALM.md`
  - `util/README.md` and `util/BUILD-FULL-SYSTEM.md`
  - root `README.md`
- **Upgrade section:** add "Upgrading: portal-backend → builder" to `docs/deployment.md`:
  1. In `secrets.env`, rename `PORTAL_DB_PASSWORD` to `BUILDER_DB_PASSWORD`, **keeping the value**. A new value would lock the builder out of the existing `portal` role.
  2. Re-run `util/gen-env.sh`.
  3. Build: `docker compose build api builder portal-frontend`.
  4. `docker compose up -d --remove-orphans`. This removes `portal-backend`, whose shutdown hook stops plugin backends; the builder's startup reconcile brings them back (verified live in Phase 8).
  5. Gateway: `nginx -t`, then reload.
  6. Old `/api/portal/...` URLs stop working.

## Phase 7: prove every doc, test, script and example works
The walkthrough artifact records each item as **ran ✓**, **static-checked only** (with the reason), or **failed** (with output). Nothing counts as working unless it was run.

| Item | How |
|---|---|
| Unit tests | `make test`, `make lint`, `make gitleaks`, compared with the baseline |
| Gateway and portal nginx | `nginx -t` in a throwaway container, plus the template test |
| `util/stage-dump.sh`, `util/portal-restore.sh`, `util/renew-cert.sh` | `shellcheck` + `bash -n`. stage-dump runs live (read-only dump into the scratchpad). portal-restore and renew-cert are static only: they're destructive and need certificates, respectively |
| `util/gen-env.sh` | run against dummy env and secrets files in the scratchpad; the output has the `BUILDER_*` names and no `PORTAL_BACKEND_HOST`, `PORTAL_KEYCLOAK_BASE_URL` or `PORTAL_DB_*` |
| Builder CLIs (`migrate_sqlite_to_postgres --dry-run`, `purge_legacy_*` with `--help` or `--dry-run`) | run in the live `builder` container |
| `services/api/scripts/import-dataset.*`, `services/api/examples/*.py`, `examples/workflow/*` | `py_compile`/`shellcheck`. `import-dataset.sh` and `upload_measurement_dataset.py` run live (they don't touch the builder, but they confirm the API image target still works). Any test datasets get deleted afterwards |
| Doc snippets in the docs edited in Phase 6 | run the non-destructive ones live, or record why each was skipped |
| Doc links | relative links resolve |

## Phase 8: end-to-end (live stack, with the user's approval before the mutating steps)
1. Back up `.env` and `secrets.env`, rename the secret key, `gen-env.sh`, `docker compose build api builder portal-frontend`, `up -d --remove-orphans`, then the gateway `nginx -t` and reload.
2. **Separation, checked live:**
   - No `portal-backend` container.
   - `docker exec <api> sh -c 'command -v docker git node'` finds nothing.
   - The API container has no socket.
   - The builder's environment has no `POSTGRES_PASSWORD` or `JUPYTERHUB_API_TOKEN`.
3. **curl matrix:**

   | Request | Expected |
   |---|---|
   | `/api/builder/tools/`, `/api/builder/workflow/gui-tool` unauthenticated | 401 from the builder |
   | `/api/portal/tools/` | not routed to the builder (SPA fallback, as flagged) |
   | `/api/health` | 200 |
   | API container → `builder:8000/api/builder/workflow/gui-tool` | 401 (reachable) |

4. **Authenticated:**
   - Tool Hub list and metadata.
   - Build logs plus the SSE stream.
   - Upload-source.
   - A GUI assay launch (the API calls the builder for the tool).
   - Running plugin backends survive the cut-over (reconcile). If they don't, flag it and add an upgrade note.
5. Revert nothing on the live stack without asking. Local live details stay out of committed artifacts.

## Commits (atomic, conventional)
1. `refactor(api)!: move the portal backend into services/api as the builder service` (Phases 1–2 and 5: code move, image targets, compose, separation tests, Makefile/CI).
2. `refactor!: serve the builder at /api/builder` (Phase 3).
3. `refactor!: rename portal-backend env vars to BUILDER_*/PLATFORM_DOMAIN/KEYCLOAK_PUBLIC_URL` (Phase 4).
4. `docs: …` (Phase 6, ADR, artifacts and walkthrough).

Each commit leaves `make test` green. Nothing is committed or pushed until the user asks.

## Known consequences, flagged
- **Breaking changes:**
  - `/api/portal/...` becomes `/api/builder/...` with a hard cut-over. Commits 1–3 and the first branch must deploy together.
  - Every deployment must rename the `secrets.env` key, keeping its value, and regenerate `.env`.
  - An external plugin compose file that reads `${PORTAL_BACKEND_HOST}` or `${PORTAL_KEYCLOAK_BASE_URL}` would fall back to its own default.
  - The standalone portal-only compose no longer includes a backend.
- **Still needs doing:**
  - The CI ruleset must drop "portal-backend unit tests" before merge.
  - Untrusted builds are still unsandboxed in `builder` (follow-up).
  - Two migration systems and two Keycloak verifiers remain in one codebase (follow-ups).
- **Pre-existing bugs ported unchanged:** listed under "My calls".
