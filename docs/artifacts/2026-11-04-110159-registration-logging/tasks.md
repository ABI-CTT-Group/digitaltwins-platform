# Tasks: log every dataset registration error and step

Plan: [plan.md](plan.md). ADR: [2026-11-04-central-registration-logging](../../decisions/2026-11-04-central-registration-logging.md).

## Docs

- [x] Replace `plan.md` with the approved plan
- [x] Sync artifacts to `docs/artifacts/`
- [x] ADR: Proposed → Accepted, with severity, user, line format and the definition of registration
- [x] Sync artifacts to `docs/artifacts/` (`adr-draft.md`)
- [x] Glossary: add **Registration**

## Builder (`services/builder`)

- [x] Tests first: request error handler, create, annotate, build requested (tools and workflows)
      (`tests/test_registration_logging.py`)
- [x] Tests first: build completed, failed (reason saved to `error_messages`) and crashed (traceback)
      (`tests/test_workflow_build_executor.py`)
- [x] Tests first: approval requested, handoff completed and failed (`tests/test_tool_handoff.py`,
      `tests/test_workflow_handoff.py`)
- [x] Tests first: `cwl_parse_error` and invalid-CWL warnings for tool and workflow CWLs
      (`tests/test_tool_layout.py`, `tests/test_workflow_layout.py`)
- [x] Red confirmed: 12 milestone and runner tests fail without the implementation
- [x] Request error handler (`app/utils/request_logging.py`, installed in `app/main.py`)
- [x] Build runner: save the reason to `error_messages`; log completed, failed and crashed builds
- [x] Milestones in both routers and in `tool_handoff.run`
- [x] Strict CWL check in `read_tool_cwl` and `read_workflow_cwl`
- [x] `make test-builder`: 244 passed, 11 skipped

## API (`services/api`)

- [x] Tests first: logging setup, request error handler, upload session steps, dataset annotate and
      push requested, one-shot upload, commit, FHIR push, failed workflow tool push
      (`tests/test_registration_logging.py`)
- [x] Red confirmed: 9 milestone and job tests fail without the implementation
- [x] Logging setup (`app/logging_setup.py`) and request error handler (`app/request_logging.py`)
- [x] Milestones in `dataset_uploads.py`, `dataset_fhir.py` and `datasets.py`; prefixed lines in
      `measurements/jobs.py`
- [x] `make test-api`: 407 passed, 1 skipped
- [x] Integration tests for the touched routes and jobs, against a throwaway Postgres and MinIO:
      67 passed (`test_dataset_fhir_api`, `test_dataset_uploads*_api`, `test_measurement_jobs`,
      `test_datasets_oneshot_api`)

## Portal (`services/portal/frontend`)

- [x] Tests first: interceptor logs failed requests (`bootstrap/__tests__/http.spec.ts`)
- [x] Tests first: `parseCwlText` throws the YAML error (`workflow_cwls.spec.ts`)
- [x] Tests first: the tool annotation step shows and logs a CWL parse error, for local and public
      GitHub sources (`BaseAnnotateStep.spec.ts`)
- [x] Red confirmed: 8, then 1 (GitHub path) failing before the implementation
- [x] Interceptor in `attachInterceptors` (`bootstrap/http.ts`): logs once, after any token refresh
- [x] `parseCwlText` rethrows the YAML error
- [x] `BaseAnnotateStep.vue`: catch, log and show the tool CWL error, naming the file; log in the
      workflow branch
- [x] Found during the work: `getRepoRootCWLContent` (`utils.ts`) never rejected, so a public
      GitHub tool's parse or fetch error left the step stuck. It now returns the raw text and
      rejects on failure; the caller parses it
- [x] `make test-frontend`: 180 passed

## Wrap-up

- [x] `make test`: api 407 (1 skipped), builder 244 (11 skipped), frontend 180, jupyterhub 5
- [x] `make lint`: all checks passed (ruff, eslint, vue-tsc)
- [x] `make docs-check` (new docs marked intent-to-add): 0 problems
- [x] gitleaks in directory mode over every changed area: no leaks; no local paths in the artifacts
- [x] Rebuild `api`, `builder`, `portal-frontend` images
- [x] Restart `api` and `portal-frontend`. Live check: the API now writes its own INFO lines, and an
      unauthenticated request logs `app.request - WARNING - GET /api/datasets/uploads/<id> -> 401: ...`
      without the query string
- [x] Restart `builder` (user approved; its shutdown hook stopped the running GUI tool backend). Live
      check: `app.request - WARNING - GET /api/builder/tools/plugin/<id>/cwl -> 401: Missing Authorization header`
- [ ] Manual check in the portal (user): bad-CWL tool package (scratch copy), valid tool trail,
      measurement upload trail
- [x] Update `plan.md` (Outcome section); the ADR still matches
- [x] Sync artifacts to `docs/artifacts/`
- [x] Commits, on the user's request: one per layer (builder fix, builder, API, portal), then these docs
