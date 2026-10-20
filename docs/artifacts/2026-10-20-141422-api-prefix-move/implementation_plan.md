# Plan: serve the platform REST API at `/api` (portal builder moves to `/api/portal`)

## Context

The REST API (`services/api`) is served at `/digitaltwins-api`. The goal is a short `/api` prefix. `/api/` is already owned by portal-backend, so freeing it requires the following (decided in interview):

- **API** → `/api` (hard cut-over: no alias or redirect for `/digitaltwins-api`).
- **Portal-backend `/api/dashboard`** (mostly a proxy to the API) → **moves into the API** at the same public path `/api/dashboard/*`.
- **Dead portal-backend routes** (`/api/login`, `/api/refresh`, `/api/auth/*`, `/api/test`, `/api/report_viewer`, disabled dashboard stubs) → deleted.
- **Portal-backend builder** (`/api/tools`, `/api/workflow`) **stays a separate container** (it needs docker.sock and runs untrusted builds), re-prefixed to `/api/portal/tools` and `/api/portal/workflow`.
- **GUI-tool lookup** (the dashboard needs `portal.workflows`) → the API calls a new portal-backend endpoint over the Docker network, forwarding the user's token.
- **Stored FHIR URLs** → migrated by re-pushing every stale measurement dataset with the existing `run_fhir_push_job`.

- **Every `digitaltwins-api` identifier → `api`.** This covers:
  - the compose service, Docker DNS host and container label
  - the image workdir
  - the JupyterHub service name
  - the gateway upstream
  - env vars `DIGITALTWINS_API_{BASE_URL,PORT,PUBLIC_URL,URL}` → `API_{BASE_URL,PORT,PUBLIC_URL,URL}` (checked: no collisions)
  - comments and prose

  Links to the old standalone repo `github.com/ABI-CTT-Group/digitaltwins-api` are **repointed to this monorepo** (`github.com/ABI-CTT-Group/digitaltwins-platform/blob/main/services/api/...`).

**Unchanged:**
- historical `docs/artifacts` / `docs/decisions` and release notes
- already-applied SQL migrations (`0001_*.sql` comment)
- the PyPI package name `digitaltwins`
- JS identifiers `dtApi`/`dtApiAxios`

The prefix stays **outside** the app (nginx strips it, uvicorn `--root-path`), so the API's TestClient tests keep root-relative paths.

## Housekeeping (on approval)
- **All work goes on a new branch**, `refactor/api-prefix-and-rename`, created from up-to-date `origin/main` (`git fetch && git switch -c refactor/api-prefix-and-rename origin/main`).
  - `origin/main` already includes everything on `dev_chinchien`; it's 1 commit ahead.
  - The untracked `docs/artifacts/...` folders in the current worktree aren't part of this change and stay untracked. They are not committed on this branch.
  - Nothing is committed to `dev_chinchien` or `main`.
  - Run `make test` on the fresh branch to record a baseline.
- Sync this plan to `docs/artifacts/<YYYY-MM-DD-HHMMSS>-api-prefix-move/` immediately. Re-sync it after each update, with repo-relative paths only and no secrets.
- Write the ADR `docs/decisions/2026-10-20-api-prefix-and-portal-builder-split.md` (from `docs/decisions/TEMPLATE.md`) with the decisions above and the alternatives rejected:
  - `/api/v1`
  - moving everything into the API
  - the same codebase in two containers
  - sharing paths under `/api`
  - the API reading the portal schema
  - an in-place FHIR rewrite
- Commit artifacts and the ADR in the same branch.

## Phase 1: portal-backend → `/api/portal`, dead routes removed
**Tests first:** in `services/portal/backend/tests/` (`test_tools_auth.py`, `test_workflow_*.py`, `test_tool_*.py`, `test_*_handoff.py`, `tool_app.py` docstrings), switch paths to `/api/portal/tools|workflow`. Add a test that `/metadata` `path` is `{proto}://{host}/api/portal/workflow/{expose}/primary`.

**Code:**
- Change the router prefixes at `app/router/workflow_tool_plugin.py:60` and `app/router/workflow_router.py:56`.
- Update the generated URL at `workflow_router.py:248` and the messages at `:478,:488,:602`.
- In `app/main.py`, delete the inline `/api/test|login|refresh|auth/*` routes and the report_viewer include, and remove the imports that become unused. This goes in a separate commit (see Commit structure, item 0). The routes are being removed rather than moved because:
  - they can't stay under `/api` once the API takes it over;
  - none has a caller anywhere in the repo, since the SPA uses keycloak-js;
  - `/api/login` would collide with the API's own `POST /login` once that is served at `/api/login`.
- Delete `app/router/clinical_report_viewer.py` and `app/models/dashboard.py`.

**Verify:** `make test-portal-backend`

## Phase 2: portal-backend `GET /api/portal/workflow/gui-tool?workflow_seek_id=`
**Tests first:** new `tests/test_workflow_gui_tool_lookup.py`. It reuses the `add_gui_workflow` fixture from `test_dashboard_assay_gui_launch.py`.

| Case | Expected |
|---|---|
| Matching gui build | `{name,path,expose}` |
| Approved build exists | approved build preferred |
| No build, not gui, or mismatched id | 404 |
| No token | 401 |
| Any valid token | 200 |

**Code:**
- Move `_resolve_gui_tool` (`dashboard.py:475`) into `workflow_router.py`.
- Add the route next to `/gui-tools`, **before** `GET /{workflow_id}`.

## Phase 3: dashboard moves into the API
**Tests first:** new `services/api/tests/test_dashboard_api.py`, reusing the `FakeQuerier`/`FakeDownloader` from `test_assay_gui_launch.py` and overriding `validate_credentials`, `get_querier`, etc.

Port every case from the portal tests `test_dashboard_assay_{download,gui_launch,workflow_link}.py`:
- programmes, category-children, workflows, workflow-detail, datasets, dataset-detail, `assays/{id}`
- assay-details GET and POST
- assay-launch: gui with tool, gui without tool, script, notebook, bad tags
- assay-gui-context: assert `/api/dashboard/...` file URLs via `TestClient(app, root_path="/api")`
- input-files: token from header, then cookie; 401 with neither; 403 for a foreign key
- assay-results-submit, assay-download

New cases:
- A bad cookie token returns 401.
- An invalid save payload returns 422.
- `_fetch_gui_tool`:
  - calls `{PORTAL_BACKEND_URL}/api/portal/workflow/gui-tool` with the Bearer token
  - 404 → `None`
  - empty seek id → no call
  - connection error or 5xx → 502
- Dropped stubs return 404.
- No API route path starts with `/api`.

**Code:** new `services/api/app/routers/dashboard.py` (`prefix="/dashboard"`). It keeps the same paths and response shapes, so the frontend and the VolView cookie path `/api/dashboard/assays/{id}/input-files` stay as they are.
- It calls the API's own route functions **in-process** (`assays.run_assay(...)`, `datasets.get_datasets(...)`, …) through the module, so tests can monkeypatch them. Pass **every** argument explicitly, because left-out ones arrive as `Query`/`Depends` placeholder objects. Use sync `def` handlers for blocking calls.
- `assay-details` POST validates `AssayDataModel` itself and returns 422 on failure.
- The input-files token comes from the header, then the `dt_assay_file_token` cookie. It is verified with `auth_bearer` and then used in `Querier(api_token=token)`.
- File URLs are built from `request.scope["root_path"]`.
- The GUI lookup uses `requests` (already a runtime dependency) and runs only on the gui branch.
- Drop the stubs `/workflow-cwl`, `/workflow`, `/assay-project` and `/dashboard/health`, which have no callers. Dropping `/dashboard/health` is my call.
- Register the router in `app/main.py`.
- Add `PORTAL_BACKEND_URL: ${PORTAL_BACKEND_URL:-http://portal-backend:8000}` in `services/api/docker-compose.yml` and `.env.template`. Both services are already on the `digitaltwins-platform` network.

**Then delete from portal-backend:**
- `app/router/dashboard.py` and its include
- `app/client/digitaltwins_api.py` (fix the comment at `services/tool_handoff.py:36`)
- `app/models/assay_model.py`
- the three dashboard test files

**Add** `tests/test_route_prefixes.py`: every portal route is `/`, `/health`, a docs route, or under `/api/portal/`.

**Verify:** `make test-api && make test-portal-backend`

## Phase 4: API prefix → `/api`
**Tests first:** `jobs.public_base()` with the env var unset returns `http://localhost/api`. Update the arbitrary bases in `test_upload_client.py:130,133` and `test_dataset_fhir_api.py:26,32`.

**Code:**
- `services/api/docker-compose.yml:6`: `--root-path /api`; also the `:55` default.
- `src/digitaltwins/measurements/jobs.py:147`
- `.env.template:293`
- `examples/upload_measurement_dataset.py:32`
- `util/populate-cpu-burn-assay.sh:69`
- the `client.py:3` docstring
- The Dockerfile CMD stays prefix-less (direct `:8010` access).

## Phase 4b: rename `digitaltwins-api` → `api` (separate commit)
**Tests first:**
- `services/jupyterhub/tests/test_service_token.py:45,74`: expect service `api`. Add a case: a leftover `'from config'` token on the legacy `digitaltwins-api` service is deleted at startup.
- Update API and portal tests that set or read `DIGITALTWINS_API_*` env vars to use `API_*`.

**Code:**
- **Compose:**
  - service key `digitaltwins-api:` → `api:` (`services/api/docker-compose.yml:2`)
  - workdir mount `/api/configs.ini`
  - `API_PUBLIC_URL`
  - `services/portal/docker-compose.yml:39`, `services/airflow/docker-compose.yml:90-91`, `airflow/compute-worker/docker-compose.yml:55-56`
  - root `docker-compose.yml:81` comment
- **Env templates:**
  - `.env.template:108,293`: `API_BASE_URL=http://api`, `API_PORT`, `API_PUBLIC_URL`
  - `services/portal/.env.template:9`
  - `secrets.env.template:25` comment
  - `util/generate-compute-env.sh:57`
  - `util/ufw_for_remote_compute.sh`
- **Image:** `services/api/Dockerfile` `WORKDIR /api` and comments.
- **Gateway:** `platform-routes.conf` `set $up_dtapi api;` (the upstream variable may also be renamed to `$up_api`).
- **JupyterHub:** in `services/jupyterhub/jupyterhub_config.py:157`, set `_API_SERVICE = 'api'` and extend the token-cleanup `DELETE` to cover the legacy name (`name IN ('api', 'digitaltwins-api')`), so the old service's token can't stay valid. Update the comment at `services/jupyterhub/docker-compose.yml:29`.
- **Code reading the env vars:**
  - API: `measurements/jobs.py:145-147` `API_PUBLIC_URL`; `examples/upload_measurement_dataset.py` `API_URL`
  - portal-backend: `services/tool_handoff.py:37`, `workflow_handoff.py`, builder/cli modules; any `DIGITALTWINS_API_*` reads
- **Container lookup in scripts:** `services/api/scripts/import-dataset.{sh,command,ps1}` label filter `com.docker.compose.service=api`, plus messages.
- **Docs:**
  - `docker compose exec api` in `util/BUILD-FULL-SYSTEM.md:384` and `util/INSTALL-BUNDLE.md:70`; also fix the stale path at `:71`
  - `services/api/docs/import-dataset.md`
  - READMEs (root, airflow, portal, `services/keycloak/REALM.md`)
  - `docs/future_refactoring.md`
  - `examples/workflow/...`
- **Comments and prose** naming `digitaltwins-api` in API, portal and frontend code → `api`.
- **GitHub links:** `pyproject.toml:22`, `services/api/README.md`, root `README.md:84`, and tutorials (`.md` and `.ipynb`) → this monorepo's `services/api/...` paths. Point a link at the repo root when the target file doesn't exist under `services/api` (e.g. `CONTRIBUTING.md`).

**Gate:** `grep -rIiE "digitaltwins[-_]api|DIGITALTWINS_API_"` over the live tree, excluding `docs/artifacts`, `docs/decisions`, release notes, applied migrations, logs and `*.egg-info`, returns **nothing**.

**Verify:** `make test` (api, portal-backend, jupyterhub).

## Phase 5: portal frontend
**Tests first (vitest):**
- `bootstrap/__tests__/http.spec.ts`: default axios `baseURL === "/api/portal"`, `dtApiAxios.baseURL === "/api"`.
- `dashboard_api.spec.ts`: calls go through `dtApi` to `/dashboard/...`.
- `tool_api` logs/SSE fetch `/api/portal/tools/...`.

**Code:**
- `src/bootstrap/http.ts:25` → `/api/portal`; `:174` → `/api`.
- `dashboard_api.ts` switches to `dtApi`/`dtApiAxios`. The interceptors are shared; only the `descriptions` key handling differs, and the dashboard doesn't use that key.
- Update the `tool_api.ts:240` URL.
- `vite.config.ts:142-152`: `/api/portal` → `:8000` (listed first); `/api` → `:8010` with the `^/api` prefix stripped; remove `/digitaltwins-api`.
- Update comments in `platform_api.ts`, `measurement_api.ts`, `tool_api.ts`, `workflow_api.ts` and `models/types.ts`.

**Verify:** `make test-frontend`

## Phase 6: nginx
**Portal-frontend template.** Test first in `backend/tests/test_frontend_nginx_template.py`:
- every `$up_backend` location is under `/api/portal/`
- there is no bare `location /api/`
- the exact upload-source and SSE regexes are present

Then edit `services/portal/frontend/nginx.conf.template:53-84`.

**Gateway** `services/nginx/snippets/platform-routes.conf`:
- Replace the `/digitaltwins-api/` block with `location /api/`: strip the prefix, set `X-Forwarded-Prefix /api`, and keep the 20G limit with no buffering.
- Add `location /api/portal/` → portal-frontend, preserving the URI.
- Move the directives of `portal-fallback.conf` into a new `snippets/portal-proxy.conf`, included by both `/` and `/api/portal/`, so they can't drift.
- Fix the header comment (`:13`) and the stale root-path comment.

**Verify** in a throwaway container:
```
docker run --rm --network none --add-host k3s-node:127.0.0.1 \
  -v $PWD/services/nginx/conf/http:/etc/nginx/conf.d:ro \
  -v $PWD/services/nginx/snippets:/etc/nginx/snippets:ro \
  nginx:1.30.3-alpine nginx -t
```
The gateway has no CI tests.

## Phase 7: FHIR URL migration CLI
**Tests first:** `services/api/tests/test_repush_fhir_urls_cli.py`.
- `is_stale(descriptions, uuid, base)`: True for the old prefix or a mix; False for the current base or no URLs.
- `--dry-run` pushes nothing.
- Re-pushes `completed`; skips and reports `pending`/`pushing`.
- Continues past errors, exits 1, and prints a correct summary.
- An integration-marked query test runs against the real schema.

**Code:** new `src/digitaltwins/cli/repush_fhir_urls.py`, modelled on `cli/import_dataset.py` (`main(argv) -> int`, argparse, ✓/✗ lines).
- Select measurement datasets (`workflow_type` empty, category not tools/models) joined to `dataset_fhir_annotation`.
- Filter with `is_stale` against `jobs.public_base()`, so it's idempotent.
- Call `jobs.run_fhir_push_job` for each dataset, then read back `fhir_status`/`fhir_failure_message` for the summary.

## Phase 8: docs (live docs only)
- Update to `/api`:
  - `docs/deployment.md:224`
  - `docs/gateway-pathway-access.md`
  - `docs/workflow-dag-authoring.md`
  - `docs/populating_data.md`
  - `docs/diagnostics.md`
  - `util/README.md`
  - `services/api/README.md`
- Update to `/api/portal/`:
  - `docs/production.md`
  - `services/nginx/README.md:120`
  - `services/portal/docs/deployment-guide.md`
  - `services/portal/docs/plugin-system-architecture.md`
- Add a one-off **"Upgrading: `/digitaltwins-api` → `/api`"** section to `docs/deployment.md`:
  1. Regenerate `.env` (`util/gen-env.sh`), because the `DIGITALTWINS_API_*` vars are renamed to `API_*`. Also regenerate compute-worker envs on remote VMs (`util/generate-compute-env.sh`).
  2. Rebuild the services and reload the gateway. Remove the orphaned old `digitaltwins-api` container (`docker compose up -d --remove-orphans`), then restart JupyterHub so it re-registers the `api` service.
  3. Run the CLI with `--dry-run`, then for real.
  4. Note that old URLs and the old builder paths no longer work.

## Phase 9: prove every script, test, doc and example still works
**Scope:** everything this change touches, plus everything that calls the API or the portal builder over HTTP or by service name.

Pre-existing legacy material that doesn't touch either is **out of scope** and gets listed in the walkthrough as "not verified, pre-existing":
- Gen3/iRODS examples (`services/api/examples/{gen3,irods}`)
- the `vph` tutorials

Each item has a recorded result in the walkthrough artifact (`docs/artifacts/<ts>-api-prefix-move/walkthrough.md`): **ran ✓**, **parse/static-checked only** (and why), or **failed** (with output). Nothing is reported as working unless it was run.

| Item | How it's verified |
|---|---|
| **Automated tests** | `make test` (test-api, test-portal-backend, test-frontend, test-jupyterhub), `make lint`, `make gitleaks`: all green, compared with the Phase-0 baseline |
| **Gateway nginx** | `nginx -t` in a throwaway container (Phase 6), then the live curl matrix below |
| `services/api/scripts/import-dataset.sh` | **Run live** against the rebuilt stack. Import a small sample dataset; confirm it reaches the `api` container by label and the dataset appears via `GET /api/datasets` |
| `import-dataset.command` (macOS) | `bash -n` + `shellcheck` (Docker `koalaman/shellcheck`), and a diff-review against `.sh`. No macOS available |
| `import-dataset.ps1` | Parse-check in `mcr.microsoft.com/powershell` (`[System.Management.Automation.Language.Parser]::ParseFile`) and review the label filter. No Windows host |
| `import-dataset.bat` | Static review only (it delegates to `.ps1`) |
| `util/populate-cpu-burn-assay.sh` | `shellcheck` + **run live**: the assay is created and runs through `/api` |
| `util/generate-compute-env.sh`, `util/ufw_for_remote_compute.sh` | `shellcheck` + run `generate-compute-env.sh` into the scratchpad; check that the output has `API_BASE_URL`/`API_PORT` and no `DIGITALTWINS_API_*`. The remote VM itself isn't available |
| `services/api/examples/upload_measurement_dataset.py` | **Run live** with its default URL (`.../api`) and `API_URL` override; the upload completes and FHIR URLs use `/api/` |
| Other `services/api/examples/*.py` | Run with `python -I -m py_compile`. Run live only those that call the HTTP API or read renamed env vars |
| `examples/workflow/workflow_image_conversion` | `py_compile` + check its env-var reads. A live run only happens as part of the Airflow script-assay check below |
| **Tutorials** (`services/api/tutorials/*.md`, `.ipynb`) | Every URL/path/env-var mention updated. Execute notebook cells that hit the API (`jupyter nbconvert --execute` in a throwaway container against the live stack) where they don't need external data. Otherwise do a link check only |
| **Doc snippets** (every `curl`/`docker compose exec`/`python -m` command in the docs edited in Phase 8 + 4b, e.g. `util/BUILD-FULL-SYSTEM.md`, `util/INSTALL-BUNDLE.md`, `docs/deployment.md` upgrade section, `services/api/README.md`, `services/api/docs/import-dataset.md`) | Copy each command and **run it** against the live stack (non-destructive ones), or mark why it was skipped |
| **Doc links** | Link-check the rewritten GitHub URLs (`curl -sI` → 200) and the relative links in edited markdown |
| **FHIR CLI** | `--dry-run`, then a real run (verification step 5 below) |

Any failure found here gets fixed with a test-first change. If it's a pre-existing bug unrelated to this change, it gets flagged instead of fixed.

## Verification (end-to-end)
1. `make test && make lint`; `docker compose config -q`.
2. Update `.env`. Then rebuild and restart:
   ```
   docker compose build api portal-backend portal-frontend
   docker compose up -d --remove-orphans api portal-backend portal-frontend jupyterhub airflow-worker
   docker exec digitaltwins-platform-gateway nginx -t && docker exec digitaltwins-platform-gateway nginx -s reload
   ```
   Check the Airflow service names and whether a `--remove-orphans` scope is right for the root compose before running these.

   Then confirm:
   - `docker ps` shows no `digitaltwins-api` container.
   - JupyterHub's `services` table has `api`, and no `'from config'` token remains on `digitaltwins-api`.
   - A notebook assay launch still works (exercises the JupyterHub service token).
   - An Airflow script assay can still call back to `API_BASE_URL`.
3. curl checks:

   | Request | Expected |
   |---|---|
   | `/api/health`, `/api/docs`, `/api/openapi.json` | 200 |
   | `/api/dashboard/programmes` | 401 (from the API) |
   | `/api/portal/tools/` | 401 (from portal-backend) |
   | API container → `portal-backend:8000/api/portal/workflow/gui-tool` | 401 (reachable) |

4. Browser:
   - dashboard tree
   - save and launch a script, a notebook and a gui assay
   - VolView loads input files through the cookie
   - Tool Hub build logs stream live
   - large upload-source upload
   - measurement upload
5. `docker compose exec api python -m digitaltwins.cli.repush_fhir_urls --dry-run`, then without the flag. Afterwards, `descriptions::text LIKE '%/digitaltwins-api/%'` matches 0 completed datasets.

## Commit structure (atomic, conventional)
0. `refactor(portal)!: remove unused login/auth/test/report_viewer routes` (the dead-route deletion from Phase 1, in its **own commit** so one revert restores them). Evidence that nothing in the repo calls them (frontend, scripts, docs, tests, other services) goes in the commit body and the ADR.
1. `refactor(portal)!: move builder routes to /api/portal` (the rest of Phase 1, and Phase 2)
2. `feat(api): serve the portal dashboard from the API` (Phase 3, adding the API router and the gui-tool call; the portal copy stays live)
3. `feat(api)!: serve the API at /api` (Phases 4, 5, 6, plus deleting the portal dashboard copy). This keeps the running stack working between commits.
4. `refactor!: rename digitaltwins-api to api` (Phase 4b)
5. `feat(api): add CLI to re-push stale FHIR URLs` (Phase 7)
6. `docs: ...` (Phase 8, plus the ADR and artifacts)

Each commit leaves `make test` green.

## Known consequences / flagged
- Old `/digitaltwins-api/...` URLs fall through to the portal SPA and get **HTML with status 200**, not 404, so old scripts fail with confusing errors. (A one-line `return 410` would fix this; it isn't included because a hard cut-over was chosen.)
- The re-push gives HAPI resources new ids and re-downloads each dataset from MinIO. Datasets in `failed`/`none` status keep their old URLs until their next push.
- The standalone portal stack (no gateway) loses `/api/dashboard`. Dev still works via the Vite proxy.
- External users of `/api/workflow/...` or `/api/tools/...` break (hard cut-over).
- Every existing deployment must regenerate `.env` and remote compute-worker envs (the `API_*` rename). An old `.env` leaves `API_PUBLIC_URL` empty, so the code default (`http://localhost/api`) would be written into FHIR URLs. Upgrade note step 1 covers this.
- Compute workers must be redeployed with the regenerated env, or Airflow tasks can't reach the API.
- Left untouched (pre-existing dead code): the `/measurement/check-name` call in `api_helpers.ts` and `keycloak.authenticate_with_credentials`.
