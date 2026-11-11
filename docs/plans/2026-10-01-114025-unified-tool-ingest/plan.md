# Plan: unify tool dataset ingest (portal GUI and REST API)

## Context

Tool datasets reach the platform in two inconsistent ways.

**Portal GUI.** The page is `/upload-tool-dataset`. It is backed by portal-backend `/api/tools/*` (`services/portal/backend/app/router/workflow_tool_plugin.py`).
- It is a build pipeline: clone or upload the source, `npm run build:plugin`, package a SPARC folder with sparc-me, and optionally `docker compose up` a backend.
- It writes only `portal.*` rows and MinIO `tools/<name>_<8hex>/`. It never reaches `public.*` or SEEK.
- Approval (`GET /plugin/{id}/approval`) is still a TODO. It pushes an `ActivityDefinition` keyed by the placeholder `sparc-tool-$<uuid4>` (note the stray `$`).
- The CWL I/O annotation is saved but never used.
- **The backend checks no token**, even though deploy runs `docker compose` on the host socket.
- Types are `GUI` / `Script`. GUI datasets have no CWL.

**REST API.** The endpoint is `POST /datasets?category=tools` (`services/api/app/routers/datasets.py:232`), plus chunked sessions `/datasets/uploads/*` (`dataset_uploads.py`), which already accept tools.
- Auth is Keycloak `admin` or `researcher`.
- It writes `public.dataset` (UUID from the DB) and MinIO `tools/<uuid>/`.
- It registers the tool in SEEK as a Workflow (`tools/pipeline.py:commit_tool`) with all-or-nothing rollback.
- It has no FHIR support and parses `subjects.xlsx` / `samples.xlsx` if they are present.
- `UploadClient` and `cli.import_dataset` don't support tools.
- **Latent bug:** `commit_tool` uploads to MinIO *before* calling SEEK with the token captured at finalize. Access tokens last 300 s, so a slow MinIO upload makes SEEK reject the call, and the whole dataset is rolled back.

**Goal:** one ingest implementation in digitaltwins-api, reachable from both the portal and REST, meeting these requirements:
- Keycloak auth on both paths
- optional FHIR keyed by the real `dataset_uuid`
- no subjects or samples
- metadata in `public.*`, files in MinIO `tools/<uuid>/`
- registration in SEEK

The portal keeps what only it can do: building and deploying GUI plugins.

## Decisions (from the interview)

| # | Decision |
|---|---|
| D1 | **The portal builds and the API ingests.** Build/test/deploy stays in portal-backend. The built SPARC folder is handed to the API at Approval. |
| D2 | **Handoff:** the user clicks Approve, and portal-backend runs a background job. It drives the chunked session API (`commit_mode=on_finalize`, because the portal's Approval is already the gate) against `http://digitaltwins-platform:8000` over the internal network, with the user's Bearer token. |
| D3 | **Token relay:** the job keeps the newest user token in memory only. Each status poll from the portal page provides a fresh one. If a part PUT gets a 401, the job pauses as `awaiting_reauth` and resumes on the next poll, with no user click. *Deferred alternative: a shared staging volume with zero-copy adopt (recorded in the ADR).* |
| D4 | **SEEK first:** `commit_tool` registers in SEEK before the Postgres/MinIO write, and deletes the SEEK workflow if the write fails. This fixes the latent bug for every client. |
| D5 | **Exactly one CWL for all tools.** The portal requires one root `.cwl` for GUI, Script and Notebook, and copies it to `primary/tool_<slug>.cwl`. The API rule is unchanged. |
| D6 | **The portal adds Notebook.** Label mapping: GUI→`gui`, Script→`script`, Notebook→`notebook`. |
| D7 | **Tool FHIR works like measurement FHIR.** `fhir=none\|auto` plus optional `fhir_descriptions` (`{"workflow_tool": {model, software, input, output, description}}`). The server owns `uuid=dataset_uuid`, `name`, `title` and `version`. The annotation is stored in `dataset_fhir_annotation`, and one `ActivityDefinition` (identifier = dataset_uuid) is pushed after commit. A failure leaves the dataset committed with `fhir_status=failed`, and it can be retried with `POST /datasets/{uuid}/fhir/push`. |
| D8 | **The tool I/O annotation lives in the API**, keyed by dataset_uuid. Portal workflow annotation reads it from `GET /datasets/{uuid}/fhir/annotation`. |
| D9 | **Portal auth:** every `/api/tools/*` endpoint needs a valid token. Writes need `admin` or `researcher`. Backend deploy is `admin` only. The frontend route guard is relaxed to `admin` or `researcher`. |
| D10 | **Tool Hub** lists API tools (`/datasets?categories=tools`) joined with the portal's build state. A REST-uploaded GUI tool can be launched if it ships `primary/my-app.umd.js`. |
| D11 | **Re-approval overwrites.** The new build is committed as a new dataset and SEEK workflow, because the API has no in-place update and SEEK has no versioning. Only after that succeeds is the previous dataset deleted through `DELETE /datasets/{uuid}` (Postgres, MinIO, SEEK and FHIR). A failed re-approval leaves the previous version in place. The Plugin has exactly one live `dataset_uuid`. **Consequence:** the tool's dataset_uuid and SEEK id change on each re-approval, so workflows or assays that point at the old ids have to be re-linked. |
| D12 | **Test builds** go to a new portal-owned, public-read `tool-builds` bucket, served by nginx at `/tool-builds/`. The `tools` bucket then maps 1:1 to `public.dataset` rows. |
| D13 | **For tools, subjects/samples are ignored:** no `subject`, `sample` or `dataset_mapping` rows are written. The xlsx files stay in the stored folder. |
| D14 | **Legacy:** Plugin and build rows are kept, placeholder uuids are cleared, and users re-approve to migrate. A purge CLI removes legacy `tools/<expose_name>/` objects and `sparc-tool-` ActivityDefinitions. |
| D15 | `UploadClient` and `cli.import_dataset` get tool support. |

| D16 | **Deleting a portal tool** also deletes its platform dataset through the API's `DELETE /datasets/{uuid}` with the user's token. That removes Postgres, MinIO, the SEEK workflow and FHIR. It replaces the portal's current direct MinIO and FHIR cleanup. |

## Implementation (TDD: failing test first in each step)

### A. digitaltwins-api (`services/api`)

1. **SEEK-first `commit_tool`** (`src/digitaltwins/tools/pipeline.py`)
   - New order: `find_tool_cwl` → `Writer.register_tool` → `Uploader.upload_dataset` → `_set_seek_id`.
   - Rollback: if the upload or link fails, delete the SEEK workflow and the dataset if one was created, then raise `SeekRegistrationError`.
   - Also stop a failure inside `Deleter` from masking the 502.
   - Tests in `tests/test_datasets_tools_api.py` / `test_dataset_uploads_tools_api.py`, using `FakeSeek` from `conftest.py`:
     - call order
     - a MinIO failure after SEEK deletes the workflow and stores nothing

2. **Skip subjects/samples for tools** (`src/digitaltwins/core/uploader.py:upload_dataset`)
   - Add a keyword such as `skip_tables=("subject", "sample")`, which also skips `dataset_mapping`. `commit_tool` passes it.
   - Test: uploading `tests/data/tool_dicom_to_nifti` writes no subject, sample or mapping rows, while `subjects.xlsx` stays in MinIO.

3. **Persist `tool_type` on `dataset`**
   - Migration `postgres/migrations/0003_dataset_tool_type.sql` adds a nullable `tool_type varchar(20)`, set by `commit_tool` together with `seek_id`.
   - `GET /datasets` uses `SELECT *`, so the Tool Hub gets the field for free.
   - Test: `test_migrate.py`, plus an assertion in the tool upload tests.

4. **Tool FHIR** (new `src/digitaltwins/tools/fhir.py`)
   - `build_descriptions(root, dataset_uuid, dataset_name, client)`:
     - fills `uuid`, `name`, `title` (CWL `label`), `version` (from `dataset_description`, else `"1.0.0"`) and `description` (from CWL `doc`, unless the client supplied one)
     - validates that `input`/`output` ids exist in the CWL
     - rejects unknown keys
   - `push(descriptions)` wraps `digitaltwins_on_fhir` `adapter.digital_twin().workflow_tool().add_workflow_tool_description(...).generate_resources()`, the call the portal uses today.
   - `delete(dataset_uuid)` removes `ActivityDefinition?identifier=<uuid>` and sends `Cache-Control: no-cache`, as the measurement cleanup does.
   - Wiring:
     - `app/routers/dataset_uploads.py:135-147` and `datasets.py`: allow `fhir` and `fhir_descriptions` for tools, and validate them with `build_descriptions` at finalize or at the one-shot upload.
     - `measurements/jobs.py`:
       - `_commit` saves the annotation for tools.
       - `run_fhir_push_job` branches on category. The tool branch deletes the old ActivityDefinition, pushes the new one and stores `fhir.json`.
       - `fhir_status` handling is shared.
     - `app/routers/dataset_fhir.py`, tool branches:
       - `GET /fhir/tree` returns prefilled descriptions plus the CWL inputs and outputs.
       - `PUT /fhir/annotation` validates with `build_descriptions` instead of `check_descriptions_match`.
       - `GET /fhir/preview` builds the ActivityDefinition as a dry run.
     - `core/deleter.py`: the FHIR cleanup has a tool branch that calls `tools.fhir.delete`.
   - Tests:
     - new `tests/test_tool_fhir.py` (builder and validation)
     - extended tool upload tests: `fhir=auto` gives `fhir_status=completed` and a `FakeHapi` ActivityDefinition with identifier = dataset_uuid; a HAPI failure gives `failed` and a retry works
     - `test_dataset_fhir_api.py` tool cases
     - `test_delete_dataset_cleanup.py` tool FHIR case

5. **`UploadClient` / CLI** (`src/digitaltwins/client.py`, `cli/import_dataset.py`)
   - `UploadClient.upload_dataset` gains `tool_type` and `seek_project_id`, and sends `fhir` / `fhir_descriptions` for tools too.
   - The CLI gains:
     - `--tool-type` and `--seek-project-id`
     - `find_tool_cwl` for `--category tools`
     - `--username` with a getpass password, which does a Keycloak password grant through the existing helper in `app/routers/auth.py`, or reuse whatever the CLI already does
     - the token passed to `run_commit_and_push`
   - Wrapper scripts are unchanged.
   - Tests: `test_upload_client.py`, `test_import_dataset_cli.py`.

6. **Docs:** update README "Uploading a tool dataset" to cover FHIR, the CLI and SEEK-first.

### B. portal-backend (`services/portal/backend`)

7. **Auth**
   - Add a `require_any_role(*roles)` helper next to `require_role` in `app/utils/auth.py`.
   - Apply it to the `workflow_tool_plugin.router` endpoints: reads need any token, writes need `admin` or `researcher`, and deploy/execute need `admin`.
   - Test: new `tests/test_tools_auth.py` checks 401 without a token, 403 for the wrong role, and deploy as admin only.

8. **Build output** (`app/builder/build_tool.py:create_sparc_dataset`, the upload step)
   - Require exactly one root `.cwl` for every label and copy it to `primary/tool_<slug>.cwl`.
   - Notebook follows the Script path, with no npm build.
   - Upload test builds to the `tool-builds` bucket.
   - Add Notebook to the label enum: `ALTER TYPE plugin_label ADD VALUE IF NOT EXISTS 'Notebook'` in `database/database.py` migration, plus the `Literal` in `db_model.py`.
   - Make `get_workflow_type` (`app/utils/utils.py`) recognise `notebook`.
   - Tests: CWL rule, the `tool_<slug>.cwl` name, and the Notebook label.

9. **Handoff job** (new `app/services/tool_handoff.py`)
   - A small httpx client for the chunked protocol: create → PUT parts per file → finalize → poll the session. It resumes from the chunk status returned by `GET /datasets/uploads/{id}`.
   - A `TokenRelay` holds the latest token in memory, keyed by build_id.
   - `PluginBuild` gains the columns `handoff_status` (`uploading|awaiting_reauth|committing|completed|failed`), `upload_id`, `dataset_uuid`, `seek_id`, `tool_type` and `handoff_error`, added through `migrate_add_missing_columns`. `Plugin` gains `seek_project_id`.
   - Endpoints:
     - `POST /plugin/{id}/approval` replaces the GET. It takes `{seek_project_id, fhir, fhir_descriptions}` and starts the job (202). It returns 409 if the latest build is not COMPLETED, has already been handed off, or a handoff for this plugin is already running.
     - `GET /plugin/{id}/approval/status` refreshes the relay token, resumes the job if it is in `awaiting_reauth`, and returns progress.
   - On success:
     - Remember the previous `Plugin.uuid`, then set `Plugin.uuid = dataset_uuid`.
     - Call the API's `DELETE /datasets/{previous}` and clear `dataset_uuid` on the old build (overwrite, D11).
     - If the delete fails, record it in `handoff_error` as a warning. The new version stays live, and the old one can be deleted again later.
   - Remove the placeholder uuid and the portal-side FHIR push.
   - Env: `DIGITALTWINS_API_INTERNAL_URL`, default `http://digitaltwins-platform:8000`.
   - Tests: `tests/test_tool_handoff.py` with a fake API (httpx `MockTransport`):
     - the happy path stores the uuid and seek_id
     - a 401 mid-upload pauses, and a new token resumes and skips the parts already sent
     - a failed session records the error
     - re-approving the same build returns 409
     - re-approving after a rebuild deletes the previous dataset only once the new one has committed
     - a failed re-approval keeps the previous dataset

10. **Annotation**
    - The Annotation step's draft (`plugin_annotations.fhir_note`) is converted into `workflow_tool.input` / `output` and sent at approval.
    - `workflow_router.py` reads a tool's I/O from the API's `GET /datasets/{uuid}/fhir/annotation` when the tool has a dataset_uuid, and falls back to the draft otherwise.
    - Test: the converter, and the workflow router reading through a fake API.

11. **Tool Hub and `/metadata`**
    - Merge `GET {API}/datasets?categories=tools` (with the caller's token) with the Plugin rows.
    - GUI path:
      - an approved tool resolves to `/tools/<dataset_uuid>/primary/my-app.umd.js`
      - a test build that isn't approved resolves to `/tool-builds/<expose>/primary/my-app.umd.js`
      - a REST GUI tool resolves to its path only if the bundle object exists
    - Test: the merge and the path rules.

12. **Delete (D16):** `DELETE /plugin/{id}` calls the API's `DELETE /datasets/{Plugin.uuid}` when it is set, then removes the portal rows, the `tool-builds` objects and staging. If the API delete fails, the portal rows are kept and the error is returned, so no orphaned datasets are left. The exception is a 404, which counts as already deleted.

13. **Legacy purge**
    - New `app/cli/purge_legacy_tools.py`, modelled on `purge_legacy_measurements.py`:
      - deletes `tools/` objects whose prefix is not a UUID
      - deletes `ActivityDefinition`s whose identifier starts with `sparc-tool-`
      - nulls `Plugin.uuid` values that start with `sparc-tool-`
    - It has a dry-run flag.
    - Test: new `tests/test_purge_legacy_tools.py`, which also checks that UUID prefixes are never touched.

### C. Portal frontend (`services/portal/frontend/src`)

14. `bootstrap/tool_api.ts`:
    - `useApproveTool` (POST) and `useApprovalStatus` (poll every ~3 s through the existing interceptor, which relays a fresh token).
    - SEEK projects come from `dtApi` `GET /projects`.
15. `views/upload-dataset/components/BaseInformationStep.vue`:
    - a SEEK project dropdown
    - a Notebook option
    - the "exactly one root .cwl" rule for every label
16. The Complete/Approve step shows handoff progress and the result (dataset_uuid, seek_id, fhir_status), and offers FHIR retry through `dtApi` `POST /datasets/{uuid}/fhir/push`.
17. `ToolsOverallView.vue` lists the merged `/metadata`. `router/index.ts` changes `requiresRoles` to `['admin','researcher']`.
18. Infra:
    - `frontend/nginx.conf.template` gets a `location /tool-builds/` modelled on `/tools/`.
    - `services/minio/init-minio.sh` creates the `tool-builds` bucket as public-read.
    - Portal `docker-compose.yml` gets the env for the API internal URL.

### D. Records (AGENTS.md)

19. After approval:
    - Copy this plan to `docs/artifacts/2026-10-01-<HHMMSS>-unified-tool-ingest/plan.md`, plus a `task.md` that has a `[ ] Sync artifacts to docs/artifacts/` item after each document change.
    - Write the ADR `docs/decisions/2026-10-01-unified-tool-dataset-ingest.md` (draft below).
    - Run `gitleaks detect --source docs/artifacts/ --no-git`.
    - At the end: write a walkthrough, update the ADR with amendments, sync again, and commit the artifacts and ADR on the same branch.

## Out of scope (noted, not fixed)

- Workflow datasets: the `workflow_router.py:458` `sparc-workflow-$` placeholder, the `tool_fhir_note` camelCase key mismatch, and missing auth on `/api/workflow/*`.
- Portal build bugs: nonexistent `error`/`error_message` fields, the hard-coded `main` branch, `/app/tmp` staging not being on a volume, and silent MinIO upload failure during builds.
- SEEK versioning, since re-approval creates a new Workflow.
- `core/downloader.py:72` compares against `"measurement"`, which is singular.

## Verification

- `pytest services/api/tests` with the stack up. Only the three failures that already existed are allowed (`test_delete_existing_dataset`, `test_upload_workspace_datasets_jupyter`, `test_upload_zip`).
- `pytest services/portal/backend/tests`.
- The frontend builds with `npm run build` / type-check. There are no frontend tests.
- Live end-to-end against the local stack (token `<REDACTED>`):
  1. REST: `POST /datasets?category=tools&tool_type=script&seek_project_id=<p>` with `tests/data/tool_dicom_to_nifti.zip` and `fhir=auto`.
     - The `public.dataset` row has `tool_type` and `seek_id`, and there are no subject rows.
     - MinIO has `tools/<uuid>/`.
     - The SEEK workflow exists.
     - HAPI has `ActivityDefinition?identifier=<uuid>`.
     - `DELETE` removes all four.
  2. CLI: `scripts/import-dataset.sh --category tools --tool-type script ...` gives the same result.
  3. Portal:
     - Register a local Script tool (a scratch folder with one root `.cwl` plus a script), then annotate, build and approve.
     - The progress completes, and the Plugin shows dataset_uuid and seek_id.
     - The workflow editor reads the tool's I/O from the API.
     - Rebuild and approve again: a new dataset_uuid and seek_id, and the old dataset, SEEK workflow and ActivityDefinition are gone.
     - Deleting the tool removes the current dataset from the platform.
  4. Portal GUI with a GitHub source: the same with https://github.com/chinchien-lin/VolView, registered through its GitHub URL (git source type). If the repo has no root `.cwl`, the build must fail with a clear error, and the E2E needs a branch with one. The test build loads from `/tool-builds/`, and the approved build loads from `/tools/<uuid>/primary/my-app.umd.js`.
  5. Token relay: set `accessTokenLifespan` to 60 s temporarily in dev and hand off a large enough tool. The job must pause and resume on its own with the tab open.
  6. Auth: portal `/api/tools/*` without a token returns 401. A researcher calling deploy gets 403.

---

## ADR draft: `docs/decisions/2026-10-01-unified-tool-dataset-ingest.md`

**Context.** This is the tool-dataset counterpart of `2026-09-28-unified-dataset-ingest-in-digitaltwins-api.md`.
- The portal's tool wizard is a build pipeline that never reaches `public.*` or SEEK and checks no token.
- The API ingests SDS tool folders into Postgres, MinIO and SEEK, but has no FHIR and no portal client.
- Keycloak access tokens last 300 s.

**Alternatives and choices:**
- **Ownership:**
  - (A, chosen) The portal builds and the API ingests, with a handoff at Approval.
  - (B) Separate upload from build.
  - (C) Drop the portal build.
  - (D) Script tools only.
- **Handoff credentials:**
  - (chosen) Forward the user's token on the Approve click.
  - Rejected: a staged session at build end (the token expires during the build), and a service account (SEEK membership checks would no longer mean anything).
- **Large-transfer handling:**
  - (chosen) The chunked session plus an in-memory token relay through status polls, with auto-resume after a 401.
  - (deferred) A shared staging volume with zero-copy adopt. It removes byte transfer and token exposure, at the cost of coupling the containers and adding an adopt endpoint. Revisit if tool datasets grow into tens of GB.
  - (rejected) Offline tokens, because portal-backend would hold long-lived user credentials.
- **SEEK ordering:** SEEK first, then storage, rolling back SEEK if storage fails. This keeps token use within seconds of finalize.
- **FHIR:** same pattern as measurements. The identifier is dataset_uuid, the dataset stays committed if the push fails, and the push can be retried. The alternatives were auto-only, and all-or-nothing together with SEEK.
- **Test builds:** a separate `tool-builds` bucket, as opposed to mixing prefixes in `tools` or serving from the portal volume.
- **Re-approval:**
  - (chosen) Overwrite: commit the new dataset first, then delete the previous one.
  - Rejected: keeping both, which leaves stale copies in SEEK and the platform; blocking re-approval; updating in place, which the API doesn't support and which would still give a new SEEK id.
  - The tool's ids change on each re-approval.

**Consequences:**
- There is one ingest implementation.
- Portal tools get real UUIDs, SEEK registration and FHIR.
- portal-backend gains an API dependency and a handoff state machine.
- If the tab is closed, a long handoff pauses until the page is opened again.
- The `tools` bucket maps 1:1 to `public.dataset`.
- Legacy plugins have to be re-approved.
- Re-approval changes a tool's dataset_uuid and SEEK id. Workflows or assays that reference them have to be re-linked, which is a follow-up if that becomes painful.
