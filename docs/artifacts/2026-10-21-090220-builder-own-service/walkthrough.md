# Walkthrough: the builder in its own service folder, services/builder

Plan: [implementation_plan.md](implementation_plan.md) · Tasks: [tasks.md](tasks.md) · ADR: [2026-10-21-builder-as-its-own-service](../../decisions/2026-10-21-builder-as-its-own-service.md)

Branch: `refactor/merge-portal-backend-into-api`. The work comes as new commits on top of the four from [2026-10-20-153503-merge-portal-backend-into-api](../2026-10-20-153503-merge-portal-backend-into-api/walkthrough.md); those weren't rewritten.

## Why

A review of the branch found that the builder shared nothing with the API it sat inside:

- no code: it imports neither `app` nor `digitaltwins`
- no image contents
- only the API's dependency pins, including packages it never imports

The layout also broke the repo's one-folder-per-service convention. See the ADR.

## Before → after

| Before (in `services/api`) | After |
|---|---|
| `services/api/builder/` (package `builder`) | `services/builder/app/` (package `app`, `app.main:app`), as in `services/api/app` and the old portal backend |
| `services/api/tests/builder_tests/` | `services/builder/tests/` (package `tests` again) |
| `services/api/Dockerfile`, target `builder` | `services/builder/Dockerfile` (single stage, `WORKDIR /app`) |
| `services/api/docker-compose.builder.yml` | `services/builder/docker-compose.yml` (root compose extends it) |
| `services/api/requirements-builder.txt` (`-r requirements-prod.txt` + 4) | `services/builder/requirements.txt`: the builder's own pins only |
| `services/api/docs/builder.md` | `services/builder/README.md` |
| `make test-api` / "api unit tests" ran both | `make test-builder` / "builder unit tests" |

The API is back to how it was before the builder arrived: single-stage Dockerfile, `requirements-test.txt`, `.gitignore`, and the original `make test-api` mounts. The only remaining API change from this branch is `BUILDER_URL` and `HOSTNAME: ${PLATFORM_DOMAIN}` in its compose file.

## Decisions made during implementation

- **The builder pins `sparc-me`'s spreadsheet stack** (`openpyxl==3.1.5`, `pandas==2.3.3`, `styleframe==4.2`). Without the API's pins, the resolver picked pandas 3 and styleframe 3. With those, 19 test modules failed at import (`openpyxl.styles`). The pinned versions are the ones the tests ran on inside the API's venv.
- **Separation tests keep only the compose checks:**
  - only `builder` has the socket
  - the builder gets no API credentials
  - the builder connects as the `portal` role
  - the root compose extends `services/builder/docker-compose.yml`

  The Dockerfile-target and cross-import checks were dropped: separate folders and build contexts make those failures impossible.
- **`make test-builder` mounts three files read-only:** the portal-frontend nginx template and the root and API `docker-compose.yml`. CI's `builder` filter covers the same files.
- **The live-DB guard test went back to the portal backend's original form,** with only the `BUILDER_DB_HOST` rename: it runs from the service root again.
- **Removed my own leftovers:** the ignored runtime files that yesterday's builder test runs left in `services/api` (`app.log`, `tmp/`, the empty `datasets_tool/` and `datasets_workflow/`). All were created during those runs.

## Verification

| Check | Result |
|---|---|
| `make test` | ✓ api 362 passed (1 skipped); builder 216 passed (7 skipped); frontend 33 files / 162; hub 5 |
| `make lint-python` (now includes `services/builder`) | ✓ 136 findings, unchanged |
| `make gitleaks` over the new commits | ✓ no leaks; the pre-commit hook passed on both commits |
| `docker compose config -q` | ✓ |
| CI filters | ✓ tested against sample paths: builder code → builder only; API code → api only; `services/api/docker-compose.yml` → both; root compose → builder |
| `docker compose build api builder` | ✓ `api` has no Docker CLI, git or Node, and holds `app/`, `src/` only. `builder` has `docker`, `git`, `node` and `yarn`, works in `/app`, imports `app.main`, and has no `digitaltwins` package |
| Live: `docker compose up -d api builder` | ✓ healthy. The builder starts in `/app` with `portal_datasets` at `/app/data` and reconciles; no API credentials in its environment; it has the socket and the API doesn't |
| Live: `/api/health`; unauthenticated `/api/builder/tools/` | ✓ 200; 401 |
| Live: authenticated `/api/builder/{tools/,workflow/,tools/metadata,workflow/gui-tools}` | ✓ 200 |
| Live: build logs, SSE stream, upload-source with no file | ✓ 200 `text/plain`, 200 `text/event-stream`, 422 |
| Live: GUI assay launch through the API | ✓ `{"type":"gui","data":"/tool-view?assay=…"}` |
| Live: `python -m app.cli.migrate_sqlite_to_postgres --dry-run`, `python -m app.cli.purge_legacy_tools --dry-run` | ✓ connects as `portal`, refuses as designed (target has rows); nothing to purge |
| Gate: `git grep` for `services/api/builder`, `docker-compose.builder`, `requirements-builder`, `builder_tests`, `api/docs/builder`, `builder.<subpackage>`, `target: builder` and the merge ADR's name (excluding artifacts and decisions) | ✓ no hits |
| Relative links in edited markdown | ✓ 19 checked; the one broken link (`RemoteComponentApp.vue`) was already broken |

## Flagged

- **Before merge:** the ruleset "CI required checks" must swap "portal-backend unit tests" for "builder unit tests". An admin runs:
  ```bash
  R=repos/ABI-CTT-Group/digitaltwins-platform/rulesets/25213776
  gh api "$R" | jq '{name, target, enforcement, conditions, bypass_actors,
      rules: [.rules[] | if .type == "required_status_checks"
        then .parameters.required_status_checks |= map(if .context == "portal-backend unit tests"
                                                        then .context = "builder unit tests" else . end)
        else . end]}' > ruleset.json
  gh api -X PUT "$R" --input ruleset.json
  ```
- Builds are still not sandboxed. The other follow-ups from the 2026-10-20 ADR stand.
