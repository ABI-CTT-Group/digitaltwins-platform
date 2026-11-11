# Walkthrough: unified tool dataset ingest

Plan: `plan.md`. ADR: `docs/decisions/2026-10-01-unified-tool-dataset-ingest.md`.

digitaltwins-api now owns tool ingest for both interfaces:
- **REST** (`POST /datasets`, the `/datasets/uploads` sessions, `UploadClient`, the CLI) goes to it directly.
- **The portal** builds the tool and, on Approval, hands the built SPARC folder to the same API session pipeline as the approving user.

Either way the tool is:
1. registered in SEEK,
2. stored in Postgres and MinIO `tools/<dataset_uuid>/`,
3. optionally pushed to FHIR as an ActivityDefinition keyed by the dataset UUID.

## Changes

### digitaltwins-api (`services/api`)

| File | Change |
|---|---|
| `src/digitaltwins/tools/pipeline.py` | `commit_tool` registers in SEEK first, then stores. If storing or linking fails, the SEEK workflow and any stored dataset are removed; rollback errors are logged and never mask the original. `_link` sets `seek_id` and `tool_type`. `annotate_tool` builds and stores the tool's FHIR descriptions. |
| `src/digitaltwins/core/uploader.py` | `skip_tables` keyword. Tools skip `subject`/`sample`, so no `dataset_mapping` rows are written either; the xlsx files are still stored. |
| `src/digitaltwins/postgres/migrations/0003_dataset_tool_type.sql` | Adds `dataset.tool_type`. |
| `src/digitaltwins/tools/fhir.py` (new) | `build_descriptions`: `workflow_tool` with server-owned `uuid`/`name`/`title`. Port annotations are checked against the CWL, and unknown fields are rejected. Also `ports`, `push` (the digitaltwins-on-fhir `workflow_tool` adapter) and `delete` (the ActivityDefinition by identifier). |
| `src/digitaltwins/measurements/jobs.py` | Tool sessions store their annotation at commit. The push job has a tool branch: delete the old ActivityDefinition, push the new one, store `fhir.json`. |
| `app/routers/dataset_uploads.py` | Tool sessions accept `fhir` / `fhir_descriptions` (shape checked at create, validated against the CWL at finalize). |
| `app/routers/datasets.py` | One-shot tool uploads accept `fhir` / `fhir_descriptions` (`_ingest_tool`) and return `fhir_status`. |
| `app/routers/dataset_fhir.py` | Tool branches for `tree` (descriptions plus CWL ports), `PUT annotation` and `preview`. |
| `src/digitaltwins/core/deleter.py` | Tool FHIR cleanup deletes the ActivityDefinition. |
| `src/digitaltwins/client.py` | `UploadClient.upload_dataset(..., tool_type, seek_project_id)`. |
| `src/digitaltwins/cli/import_dataset.py`, `cli/keycloak_login.py` | `--tool-type`, `--seek-project-id`, and `find_tool_cwl` for tools. `login()` returns `(username, token)`, and the token goes to the commit job for SEEK. |
| `README.md` | "Uploading a tool dataset" rewritten. |

### portal-backend (`services/portal/backend`)

| File | Change |
|---|---|
| `app/utils/auth.py` | `require_any_role`. `get_current_user` also returns the raw token. |
| `app/client/keycloak.py`, `services/portal/docker-compose.yml` | Server-side Keycloak calls use the internal `KEYCLOAK_BASE_URL` (falling back to `PORTAL_KEYCLOAK_BASE_URL`), with a trailing slash. Before this, every token check in the local stack failed. |
| `app/router/workflow_tool_plugin.py` | Auth: the router requires a valid token; writes need `admin` or `researcher`; deploy/execute, debug and test-build need `admin`. |
| | `POST /plugin/{id}/approval` and `GET /plugin/{id}/approval/status` replace the placeholder-uuid GET approval and the portal-side FHIR push. |
| | `GET /plugin/{id}/annotation` reads the platform annotation for approved tools. |
| | `/metadata` serves approved tools from `/tools/<uuid>/` and test builds from their bucket. |
| | Delete removes the platform dataset through the API first. |
| `app/services/tool_handoff.py` (new) | Chunked-session client, `TokenRelay`, and the resumable handoff job. Also the draft ↔ `workflow_tool` converters. |
| `app/builder/build_tool.py` | `root_cwl` enforces exactly one root `.cwl` for every label, checked before npm runs. It is copied to `primary/tool_<stem>.cwl`. Test builds go to the `tool-builds` bucket. |
| `app/models/db_model.py`, `app/database/database.py` | `Notebook` label, plus `migrate_enum_values` for the Postgres enum. `plugins.seek_project_id`. `plugin_builds.handoff_status`, `upload_id`, `dataset_uuid`, `seek_id`, `handoff_error` and `handoff_user`. Only the approver's polls relay a token. |
| `app/utils/utils.py` | `get_workflow_type` recognises `notebook`. |
| `app/cli/purge_legacy_tools.py` (new) | Purges legacy `tools/<expose_name>/` objects and `sparc-tool-` ActivityDefinitions, and clears placeholder uuids. Has `--dry-run`. |

### Portal frontend and infra

| File | Change |
|---|---|
| `components/ToolApprovalDialog.vue` (new) | SEEK project picker, FHIR toggle, handoff progress, FHIR retry. |
| `components/ToolCard.vue` | Notebook kind, and chips for approving / approval failed / in platform / platform upload. Polls an active handoff, which relays the token and auto-resumes it. Platform-only tools are read-only. |
| `workflow-tool/ToolsOverallView.vue` | Tool Hub = portal tools plus platform-only tools (`useToolHub`). Approval goes through the dialog. |
| `components/BaseInformationStep.vue` | Notebook option. A root CWL is required for every tool type. |
| `bootstrap/tool_api.ts`, `models/types.ts`, `services/tool.ts`, `router/index.ts` | API wrappers and types. The tool route allows `admin` or `researcher`. |
| `frontend/nginx.conf.template` | `/tool-builds/` route to MinIO. |
| `services/minio/init-minio.sh`, `services/portal/docker-compose.yml` | Download-only `tool-builds` bucket. |

## Verification (so far)

- `pytest services/api/tests`: **228 passed**, 2 failed, 1 error. The failures are the same three pre-existing legacy ones as the baseline (202 passed before this work): `test_delete_existing_dataset`, `test_upload_workspace_datasets_jupyter`, `test_upload_zip`.
- `python -m unittest discover -s tests -t .` (portal-backend): **81 OK**, 7 skipped. The Postgres tests (`tests.test_postgres_integration`, including the new enum test) were run separately against the live database: **OK**.
- `docker compose build digitaltwins-api portal-backend portal-frontend`: all three images built, including the frontend's `yarn build`. They were redeployed on the local stack.
- **Live checks:**
  - migrations `0001`–`0003` are applied
  - `portal.plugin_builds` has the handoff columns
  - `portal.plugin_label` includes `Notebook`
  - the `tool-builds` bucket exists (download policy)
  - `/api/tools/*` without a token returns **401**
  - `/tool-builds/` is proxied to MinIO
- **Live REST E2E** (user `admin1`, token `<REDACTED>`, SEEK project 10):
  - **One-shot upload:** `POST /datasets?category=tools&tool_type=script&fhir=auto` with `tests/data/tool_dicom_to_nifti.zip` returned 200 with `seek_id` 49 and `fhir_status: pending`.
    - The row is `('tools', 'sds_tool_dicom_to_nifti', '49', 'script', 'completed')`, with 0 `dataset_mapping` rows (subjects and samples skipped) and 1 stored annotation.
    - HAPI has 1 ActivityDefinition with that identifier (name `sds_tool_dicom_to_nifti`, title `Tool - dicom to nifti`).
    - MinIO `tools/<uuid>/` holds the SDS files, `primary/tool_dicom_to_nifti.cwl` and `fhir.json`.
    - SEEK: title `Tool - dicom to nifti`, tags `script, tool`.
  - **Its `DELETE`** reported 14 MinIO objects, `{"ActivityDefinition": 1}` and `seek_workflow_deleted: true`. Afterwards HAPI has 0 resources for it and SEEK `workflows/49` returns 404.
  - **Resumable sessions through `UploadClient`:** `tests/data/tool_volview` (622 files) with `tool_type=gui` and `fhir_descriptions` ended `completed` with FHIR `completed`: row `('tool_volview', '50', 'gui', 'completed')`, 0 subjects. `DELETE` removed 623 objects and the ActivityDefinition, and SEEK `workflows/50` returns 404.
  - **Unrelated to this change:** `GET /tools/{id}` returns 500 rather than 404 for a deleted SEEK workflow.
- **Live portal E2E** (user `admin1`, SEEK project 10). It called the same `/api/tools/*` endpoints the Tool Hub calls, through the gateway; the UI wasn't clicked through.
  - **Script tool from a local zip:**
    - upload-source → create → annotation draft → build.
    - The test build is at `s3://tool-builds/<expose>`, and `/metadata` points to `/tool-builds/<expose>/primary`.
    - Approval completed with 14/14 parts and SEEK 51. `/metadata` then pointed to `/tools/<uuid>/primary`, and the annotation came back from the platform in the draft shape (`src`→ImagingStudy, `nifti`→Observation).
    - Rebuild and re-approve gave SEEK 52 and a new UUID. The old dataset row, its ActivityDefinition and SEEK 51 (now 404) were deleted. The new row is `('E2E Convert …', '52', 'script', 'completed')`.
    - Delete removed the platform dataset, SEEK 52, the ActivityDefinition, the `tool-builds` objects and the portal rows.
  - **GUI tool from GitHub** (https://github.com/chinchien-lin/VolView, root `volview.cwl`):
    - The clone and `npm run build:plugin` succeeded; the test bundle is served from `/tool-builds/<expose>/primary/my-app.umd.js`.
    - Approval completed with 755/755 parts and SEEK 53. The SEEK title is `VolView` and the tags are `gui, tool`.
    - `/metadata` pointed to `/tools/<uuid>/primary/my-app.umd.js`, which is served with 200 (2 MB). MinIO `primary/` holds `my-app.umd.js`, `assets`, `itk` and `tool_volview.cwl`.
    - Re-approve gave SEEK 54, and the old version was fully deleted (SEEK 53 returns 404).
    - Delete removed everything: platform row, ActivityDefinition, SEEK 54, `tools/<uuid>/`, `tool-builds/`, and the portal rows.
  - **Found and fixed:**
    - Portal-backend reached Keycloak through the public URL, so every token was rejected with 401.
    - The plugin delete used bulk `DeleteObjects`, which this MinIO rejects (`MissingContentMD5`); objects are now deleted one by one, and a retried delete succeeds.
- **Not run live:**
  - the CLI, which needs an interactive Keycloak login in the container (covered by the integration tests);
  - the token-relay pause and resume, which would mean changing the live realm's token lifetime (covered by `tests/test_tool_handoff.py`);
  - clicking through the frontend UI (only the image build was checked).
