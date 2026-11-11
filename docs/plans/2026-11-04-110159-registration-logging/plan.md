# Plan: log every dataset registration error and step

## Context

Registering a GUI tool at `/catalogue/tools` showed "No tool CWL file detected", although the builder
had found and served the CWL (HTTP 200). The portal's js-yaml rejected a duplicated input key. The
JSON fallback in `parseCwlText` replaced that error with `Unexpected token 'c'`, and the tool branch of
`BaseAnnotateStep.vue` didn't catch the error. Nothing was logged anywhere. (The user has since fixed
that CWL.)

Investigating showed that registration errors are lost across the platform:

- **Error reasons:** both backends log 4xx responses only as uvicorn's status line, without `detail`.
- **Build failures:**
  - The builder writes each failure reason to `.error` / `.error_message`, but the column is
    `error_messages` (`services/builder/app/utils/builder_utils.py:328,341`). The reason is never
    saved.
  - The unexpected-exception path writes no traceback to the container log.
- **API logging:** the API never configures logging, so its own INFO lines are dropped.
  `dataset_uploads.py` and `dataset_fhir.py` have no logger.
- **Successful steps:** most steps log nothing when they succeed.
- **Portal:** failed requests aren't logged, and some calls swallow errors (`.catch(() => undefined)`).

**Goal:** every registration error, and one line per registration step, appears in the container
logs (builder, API) and the browser console. The CWL parse error is shown on the page.

## Decisions settled with the user

| # | Decision |
|---|---|
| Scope | All four categories: tools, workflows, measurements, models |
| Registration | From the first upload request until the dataset is committed and its FHIR push has finished, successfully or not. DAG deploy, GUI backend start/stop and delete are outside it and keep their current logging |
| What is logged | Errors with reasons, plus one INFO milestone per step. Upload *parts* are not logged per part (too many) |
| User | `user=<preferred_username>` (never email) on milestones raised in a request. Milestones raised in background jobs carry ids only, and grep links them to the request line |
| Severity | Both layers: 4xx → WARNING / `console.warn`; 5xx or network failure → ERROR / `console.error`. No 404 special case |
| Polling | Log every failed poll; no deduplication |
| Format | Milestones: `Registration <category> <step>: key=value ...`, for example `Registration tools create: plugin_id=<id> name=<name> user=<u>` |
| Correlation | No request id; milestones log the ids that join steps (the handoff logs both the build id and the dataset uuid) |
| Browser errors | Console and page only; not sent to the backend |
| Build failure reason in UI | Not part of this change |

## First step of implementation: update the docs

- `docs/artifacts/2026-11-04-110159-registration-logging/plan.md`: replace it with this plan.
  Refresh the timestamp, and sync the folder name if needed.
- `docs/decisions/2026-11-04-central-registration-logging.md` (Proposed → Accepted on approval): add the
  severity split, the username-on-milestones choice, the line format and the definition of
  registration. Copy it to the artifacts folder.
- `docs/glossary.md`: add **Registration** (upload → commit → FHIR push finished; excludes deploy and
  delete), with no implementation detail.

## Changes

### Builder (`services/builder/app`)

1. **Request error handler** (`main.py`): exception handlers for `HTTPException` and
   `RequestValidationError` log `<METHOD> <path> -> <status>: <detail>`, WARNING for 4xx and ERROR for
   5xx, then delegate to `fastapi.exception_handlers.http_exception_handler` /
   `request_validation_exception_handler`, so responses don't change. The log has the path only, with
   no query string. The existing PAT masking filter (`engine/logger.py`, `_PatMaskingFilter`) still
   applies.
2. **Build failure reason** (`utils/builder_utils.py`, `execute_build_in_background`):
   - write it to `error_messages`;
   - log `Registration <category> build failed: build_id=... reason=...` at ERROR;
   - use `logger.exception` in the `except` path.
3. **Milestones**:
   - `router/workflow_tool_plugin.py` and `router/workflow_router.py`: create, annotation saved,
     build requested, approval requested. Each adds `user: dict = Depends(get_current_user)`; FastAPI
     caches the dependency per request, so the role check's Keycloak userinfo call isn't repeated.
   - `upload-source`: keep the existing line and give it the same prefix.
   - Build finished: in the runner (category from the build type).
   - Handoff completed: `services/tool_handoff.py`, `services/workflow_handoff.py`, with the build id
     and dataset uuid.
4. **CWL check**: `cwl_parse_error(text) -> Optional[str]` in `engine/tool_layout.py`, using a strict
   `yaml.SafeLoader` subclass that raises on duplicate mapping keys.
   - `read_tool_cwl` calls it on its CWL.
   - `read_workflow_cwl` (`engine/workflow_layout.py`) calls it on the workflow CWL and each
     `tool_cwls` entry.
   - Each failure logs `Invalid CWL <file>: <error>` at WARNING.
   - Return values are unchanged, and uploads are not rejected.

### API (`services/api/app`, `services/api/src/digitaltwins`)

5. **Logging setup** (`app/main.py`): configure the root logger at INFO with a stdout handler and the
   builder's line format. Keep `botocore` and `urllib3` at WARNING (botocore logs a credentials line at
   INFO). The `uvicorn.*` loggers don't propagate, so access lines aren't duplicated.
6. **Request error handler**: same as step 1.
7. **Milestones**:
   - `routers/dataset_uploads.py`: session created (category, upload_id, user), finalized (staged),
     approval requested, cancelled, annotation saved.
   - `routers/dataset_fhir.py`: annotation saved, FHIR push requested.
   - `routers/datasets.py`: `POST /datasets` registered (uuid, user).
   - `measurements/jobs.py`: add the prefix to the existing commit and push lines, and add
     `logger.exception` for the failed tool push in `_push_workflow`.
   - The category comes from the session or dataset row.

### Portal (`services/portal/frontend/src`)

8. **Interceptor** (`bootstrap/http.ts`, `attachInterceptors`, which serves both `axios` (builder) and
   `dtApiAxios` (API)):
   - for each request that finally fails, log `[HTTP] <METHOD> <url> -> <status>: <detail>` with
     `console.warn` for 4xx and `console.error` for 5xx or network errors;
   - skip cancelled requests and a 401 that succeeds after the token refresh;
   - leave the existing catch sites unchanged.
9. **`parseCwlText`** (`views/upload-dataset/components/workflow_cwls.ts`): when both parses fail,
   rethrow the YAML error.
10. **`BaseAnnotateStep.vue`**:
    - tool branch: add `try/catch` with `console.error`, and show `Failed to parse <file>: <message>`
      in a `v-alert`, reusing the existing `loadError` ref. Keep the "No tool CWL" view only for when
      no CWL exists;
    - workflow branch: add `console.error` to its existing `catch`.

## Not changed (noted)

The deploy runner (`utils/workflow_tool_utils.py:186,197`) has the same `.error` / `.error_message`
bug. `PluginDeployment` has no error column at all, and deploy is outside registration, so fixing it
needs a migration and belongs in a separate change.

## Tests (each written first and seen failing)

| Suite | File | Cases |
|---|---|---|
| builder | new `tests/test_registration_logging.py` (uses `tests/tool_app.py` `make_client`, `bearer`) | 4xx → WARNING with method, path, status and detail; 5xx → ERROR; no query string in the log; response body unchanged; create, annotation and approval log `Registration tools ...` with `user=`; same for workflows |
| builder | `tests/test_workflow_build_executor.py` | a failed build saves `error_messages` and logs ERROR; a raising build logs a traceback |
| builder | `tests/test_tool_layout.py`, `tests/test_workflow_layout.py`, `tests/test_tool_sds_source.py` | `cwl_parse_error` cases; a bad tool or workflow CWL still returns 200 and logs `Invalid CWL` |
| api | new `tests/test_registration_logging.py`; extend `test_dataset_uploads_api.py`, `test_dataset_fhir_api.py`, `test_measurement_jobs.py` | an app INFO record reaches the root handler; no duplicated uvicorn lines; error handler as for the builder; session, finalize, approve, cancel, annotation and push lines; failed tool push logged |
| frontend | `bootstrap/__tests__/http.spec.ts` | 400 → `console.warn`; 500 or network → `console.error`; cancelled → nothing; a 401 that succeeds after refresh → nothing |
| frontend | `views/upload-dataset/components/__tests__/workflow_cwls.spec.ts`, `BaseAnnotateStep.spec.ts` | a duplicated-key CWL throws a YAML error; the tool page shows the parse error and the file name, and calls `console.error` |

## Commits (one PR from `dev_chinchien`)

1. `fix(builder): save build failure reasons to error_messages`
2. `feat(builder): log request errors, registration steps and invalid CWL`
3. `feat(api): configure logging; log request errors and registration steps`
4. `feat(portal): log failed requests and show CWL parse errors`
5. `docs: registration logging plan, ADR and glossary entry`

Check for secrets before staging (`make gitleaks`), and keep local paths and live ids out of the
artifacts.

## Verification

1. `make test-builder`, `make test-api`, `make test-frontend` (each in a throwaway container, never a
   live one): red first, then green.
2. `make lint`: no new findings compared with `main`. `make docs-check` after `git add` of the new docs.
3. Rebuild and restart only the changed services:
   `docker compose build api builder portal-frontend && docker compose up -d api builder portal-frontend`.
4. Manual checks:
   - At `/catalogue/tools`, register a scratch copy (outside the repo) of a tool package with a
     duplicated input key. Expect the parse error on the page, `console.error`, and `Invalid CWL` in
     `docker logs digitaltwins-platform-builder-1`.
   - Register a valid tool and check that `docker logs ... | grep Registration` shows the whole trail
     from upload to FHIR push.
   - Upload a measurement and see its session, finalize, approve and push lines in the API log.

## Outcome (2026-11-04)

Implemented as planned. Progress and test counts are in [tasks.md](tasks.md). Differences from the plan:

- **Public GitHub tools** (portal): `getRepoRootCWLContent` in `views/upload-dataset/components/utils.ts`
  parsed the CWL inside a nested `.then` and never rejected. A parse or fetch error left the
  annotation step on "No tool CWL file detected", with nothing logged. It now returns the raw text and
  rejects on failure, and `BaseAnnotateStep.vue` parses it, so the error names the file and appears
  on the page and in the console like the other sources.
- **`put_annotation`** (API, `routers/dataset_fhir.py`): its body moved into `_annotate` so that the
  milestone is logged once instead of on three return paths. Behaviour is unchanged; the integration
  tests for that route pass.
- **API logging setup** also keeps `boto3` and `s3transfer` at WARNING, alongside `botocore` and
  `urllib3`.
- **The invalid-CWL warning** is tested on `read_tool_cwl` and `read_workflow_cwl` directly (the
  endpoints only call them), not through `GET /plugin/{id}/cwl` in `test_tool_sds_source.py`.
- **The upload line** in both builder routers now has the `Registration <category> upload` prefix.
- **Restarting the builder** stops every running GUI tool backend (its shutdown hook), so the user
  approved that restart separately.

The ADR still matches what was built.
