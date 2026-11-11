# Walkthrough: API at /api, portal builder at /api/portal, digitaltwins-api renamed to api

Plan: [implementation_plan.md](implementation_plan.md) · ADR: [2026-10-20-api-prefix-and-portal-builder-split](../../decisions/2026-10-20-api-prefix-and-portal-builder-split.md)

Branch: `refactor/api-prefix-and-rename` (from `origin/main`).

## Baseline (before any change, `make test`)

| Suite | Result |
|---|---|
| test-api | 298 passed, 1 skipped, 213 deselected |
| test-portal-backend | 224 passed, 7 skipped |
| test-frontend | 30 files, 155 tests passed |
| test-jupyterhub | 4 passed |
| lint-python (report-only) | 154 findings, all pre-existing |

## Commits

| # | Commit | Tests after |
|---|---|---|
| 0 | `refactor(portal)!: remove unused login/auth/test/report_viewer routes` | portal 225 passed |
| 1 | `refactor(portal)!: move builder routes to /api/portal` | portal 232 passed |
| 2 | `feat(api): serve the portal dashboard from the API` | api 345 passed |
| 3 | `feat(api)!: serve the API at /api` | api 346, portal 208, frontend 162 passed |
| 4 | `refactor!: rename digitaltwins-api to api` | api 351, portal 208, frontend 162, hub 5 passed |
| 5 | `feat(api): add CLI to re-push FHIR file URLs after the API moved` | api 361 passed, plus the integration query test on a throwaway Postgres 16 |
| 6 | `docs: ...` (docs, ADR, these artifacts) | |

Portal tests fall from 232 to 208 because the three dashboard test files and `test_workflow_type.py` moved to the API as `tests/test_dashboard_api.py`.

## Decisions made during implementation

- **How the dashboard reaches the API's logic (refines plan Phase 3).**
  - **SEEK reads** (programmes, category children, assays, workflows, datasets, sample types) call the caller's `Querier` directly. The API's own routes for these are one-line wrappers around the same `Querier` calls, so this is equivalent. It also avoids the FastAPI trap where a route function called directly gets `Query`/`Depends` placeholder objects for any argument left out.
  - **Assay operations** call the `assays` route functions in-process through the module, so their validation and side effects stay in one place. These are configure (with workflow link), run, gui-inputs, input-file key check, workspace upload and download.
- **Dashboard seek-id parameters are typed `int`**, matching the API routes they used to proxy to. A non-numeric id is a 422, as it already was when the API rejected it.
- **`/dashboard/health` was not ported.** Nothing calls it, and the API's `/health` covers it.
- **The gateway's portal hop moved to a shared snippet.** Its directives (no buffering, unlimited body, WebSocket upgrade) are now in `services/nginx/snippets/portal-proxy.conf`, included by both `location /` and `location /api/portal/`, so they can't drift.
- **Portal helpers that lost their only caller were removed** along with the dashboard: `assay_type` and `get_workflow_type` in `app/utils/utils.py`, and `app/client/digitaltwins_api.py`. `get_workflow_type`'s tests moved to the API with it.
- **Prose wording for the rename.** Where code comments meant the service as a thing ("hands the build to digitaltwins-api"), they now say "the platform API". Container, service and DNS names say `api`.
- **The CONTRIBUTING link** in the API README pointed at a file the monorepo doesn't have. It now points at the repo's Contributing section (`digitaltwins-platform#contributing`).
- **The FHIR re-push CLI only re-pushes `completed` datasets.** It reports `pending` and `pushing` ones as skipped. Datasets in `none` or `failed` state get the new URLs on their next push.

## Phase 9 verification

| Item | How | Result |
|---|---|---|
| Unit and component tests | `make test` | ✓ api 361, portal 208 (7 skipped), frontend 33 files / 162, hub 5 |
| FHIR CLI candidate query | integration test on a throwaway `postgres:16` (isolated network, removed after) | ✓ 1 passed |
| Python lint | `make lint-python` | ✓ 136 findings, down from 154; none in changed lines |
| Frontend lint and type-check | `make lint-frontend` | Already failing on `main` (report-only in CI). The 11 TS errors and 22 eslint warnings are all in untouched code: `tool_api.ts:7` is a pre-existing unused import, and `vite.config.ts:36` is outside the edited proxy block |
| Secrets | `make gitleaks` (commit range) | ✓ no leaks |
| Gateway nginx | `nginx -t` in a throwaway `nginx:1.30.3-alpine` with the http conf | ✓ syntax ok. The ssl conf includes the same snippets but needs certificates, so it wasn't run |
| Portal nginx template | `tests/test_frontend_nginx_template.py` | ✓ only `/api/portal/` reaches portal-backend |
| `import-dataset.sh`, `.command`, `populate-cpu-burn-assay.sh`, `generate-compute-env.sh`, `ufw_for_remote_compute.sh` | `shellcheck -S warning` (v0.10.0) + `bash -n` | ✓ clean |
| `import-dataset.ps1` | PowerShell 7.4 parser (`Parser::ParseFile`) | ✓ parses. No Windows host to run it on |
| `import-dataset.bat` | static review: it only calls the `.ps1` | ✓ no change needed |
| `generate-compute-env.sh` | ran against a dummy env file | ✓ emits `API_PORT=8010`, no `DIGITALTWINS_*` |
| `services/api/examples/*.py`, `examples/workflow/*/code/*.py`, `services/airflow/dags/workflow_9000.py`, the new CLI | `py_compile` (Python 3.11) | ✓ 18 compiled, 0 failed |
| `upload_measurement_dataset.py` arguments | ran `parse_args` | ✓ default `http://localhost/api`; `API_URL` overrides it |
| Rewritten GitHub links (23) | `curl` | ✓ 22 return 200. `/stargazers` returns 404 without a GitHub login, for the old repo too |
| Rename gate | `git grep -iE "digitaltwins[-_]api\|DIGITALTWINS_API_"` over the live tree (excluding artifacts, decisions, release notes, applied migrations) | ✓ only intentional mentions remain: the upgrade notes, the JupyterHub legacy-name cleanup and its test, and the re-push CLI and its test |

### Live checks (full stack rebuilt and started locally)

Setup steps:
- `.env` regenerated with `util/gen-env.sh`. Only `DIGITALTWINS_API_*` → `API_*` changed, plus `PORTAL_BACKEND_URL` added.
- Built `api`, `portal-backend` and `portal-frontend`.
- `docker compose up -d --remove-orphans`, then the gateway `nginx -t` and reload.

| Check | Result |
|---|---|
| All services healthy; no `digitaltwins-api` container left | ✓ |
| `/api/health`, `/api/docs`, `/api/openapi.json` | ✓ 200 (Swagger finds its spec under `/api`) |
| Unauthenticated `/api/dashboard/*`, `/api/tools` | ✓ 401 from the API |
| Unauthenticated `/api/portal/tools/`, `/api/portal/workflow/gui-tool` | ✓ 401 from portal-backend |
| `/digitaltwins-api/health` | SPA HTML with status 200 (hard cut-over, as flagged) |
| Authenticated dashboard (programmes, the full category-children walk down to assays, workflows, datasets, assay-details) | ✓ 200 |
| Authenticated `/api/portal/tools/`, `/api/portal/workflow/`, `/api/portal/tools/metadata` | ✓ 200 |
| Dropped stubs `/api/dashboard/health`, `/api/dashboard/workflow-cwl` | ✓ 404 |
| gui assay launch: the API asks portal-backend for the tool over the Docker network | ✓ `{"type":"gui","data":"/tool-view?assay=…"}` |
| gui context file URLs | ✓ `/api/dashboard/assays/…/input-files/…` |
| VolView-style download of an input file with only the `dt_assay_file_token` cookie | ✓ 200 (41 MB streamed). A bad cookie or no token gets 401 |
| JupyterHub after restart | ✓ only service `api` with its one config token. The API's token authenticates as service `api` |
| Airflow worker environment | ✓ `API_BASE_URL=http://api`, `API_PORT=8000`, no `DIGITALTWINS_API_*`; `/health` reachable through them |
| Builder build logs, SSE log stream, upload-source through the gateway's `/api/portal/` | ✓ 200 text, 200 `text/event-stream`, 422 from portal-backend (no file sent) |
| Served SPA bundle | ✓ uses `/api/portal` and `/api`; no `/digitaltwins-api` |
| `services/api/scripts/import-dataset.sh` (run in a pty with a password login, test fixture `example_sds_dataset`) | ✓ imported, and listed by `GET /api/datasets` |
| `services/api/examples/upload_measurement_dataset.py --fhir auto` against `http://localhost/api` | ✓ uploaded, FHIR completed. The stored annotation and all 8 HAPI Endpoint addresses use `/api/datasets/…`. A file URL under them streams (200) |
| `repush_fhir_urls --dry-run` | ✓ lists exactly the completed datasets whose annotation still has `/digitaltwins-api/` (4, matching a direct SQL count) |
| `repush_fhir_urls` (real run) | ✓ 4 re-pushed, 0 failed. Afterwards no completed annotation has the old prefix; every HAPI Endpoint is under `/api/datasets/`, none under `/digitaltwins-api`. A second run reports nothing to re-push |
| `DELETE /api/datasets/{uuid}` for the two test datasets created above | ✓ 200 each; neither is listed afterwards |
| `util/populate-cpu-burn-assay.sh` | ✓ it registered its dataset and configured its assay through `/api`; the assay's details load through `/api/dashboard`. The run itself wasn't triggered, because it needs the remote compute node |
| Notebook assay launch through `/api/dashboard/assay-launch` | ✓ the hub started the user's server through the `api` service token and returned the lab URL for the assay workspace |

**Pre-existing, not changed here:** `util/populate-cpu-burn-assay.sh` defaults `BASE_DIR` to `$HOME/digitaltwins-platform` and runs from there. A checkout anywhere else needs `BASE_DIR=<repo>`; otherwise it reads another tree's `.env` and fails without any message.

**Pre-existing, not changed here:** subject- and sample-level FHIR Endpoint addresses (folder URLs) return 404 ("File not found") from `GET /datasets/{uuid}/files/{path}`, which streams files only. The route is unchanged on this branch.

**Not verified, pre-existing:** the Gen3/iRODS examples (`services/api/examples/{gen3,irods}`) and the `vph` tutorials. This change doesn't touch them.

## Flagged

- Old `/digitaltwins-api/...` URLs now fall through to the portal SPA (HTML, status 200), not a 404.
- External DAG code that reads `DIGITALTWINS_API_BASE_URL` / `DIGITALTWINS_API_PORT` must switch to `API_BASE_URL` / `API_PORT`. Nothing in this repo reads them.
- Pre-existing dead code left alone:
  - the `/measurement/check-name` call in `api_helpers.ts`
  - the stale `/api/measurement/upload-source` mention in `models/types.ts`
  - `keycloak.authenticate_with_credentials` in portal-backend, now unused
- Commits 1 to 3 should be deployed together. After commit 1 the portal-backend serves the builder at `/api/portal/...`, but the portal frontend and nginx only switch in commit 3. Each commit keeps `make test` green.
