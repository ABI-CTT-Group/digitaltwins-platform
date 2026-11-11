# Walkthrough: tools dataset upload (script type)

Plan: `implementation_plan.md`. ADR: `docs/decisions/2026-09-30-register-tools-in-seek-via-single-ro-crate-post.md`.

## What changed (services/api)

| Area | Change |
|---|---|
| `src/digitaltwins/tools/` (new) | `CATEGORY = "tools"`. `validation.find_tool_cwl`: exactly one top-level `primary/tool_*.cwl`. `pipeline.commit_tool`: Postgres + MinIO → SEEK → `dataset.seek_id`; any SEEK or link failure deletes the dataset and raises `SeekRegistrationError` |
| `src/digitaltwins/seek/writer.py` (new) | `build_tool_crate` (a Workflow RO-Crate built by hand) and `Writer.register_tool` / `delete_workflow`, as the caller's Keycloak JWT |
| `app/routers/datasets.py` | `POST /datasets?category=tools&tool_type=script&seek_project_id=N`. 400 if a param is missing, 502 on SEEK failure; the response includes `seek_id`. `DELETE` returns `seek_workflow_deleted` |
| `app/routers/dataset_uploads.py` | Sessions accept `category=tools` with `tool_type` + `seek_project_id` and no FHIR. Finalize validates with `find_tool_cwl`. Finalize and approve pass the token to the background job |
| `measurements/jobs.py`, `measurements/sessions.py` | The commit job branches to `commit_tool` for tools. The session stores `tool_type` / `seek_project_id` |
| `postgres/migrations/0002_upload_session_tool.sql` (new) | Nullable `upload_session.tool_type`, `seek_project_id` |
| `core/deleter.py`, `postgres/deleter.py`, `app/routers/dependencies.py` | Deleting a tools dataset also deletes its SEEK Workflow, best-effort, after commit. `get_deleter` now passes the caller's token |
| `core/querier.py` | `get_dataset(get_cwl=True)` now checks `tools` (it had checked `tool`) and reads `primary/tool_*.cwl` from MinIO (it had read from iRODS by folder name) |
| `README.md` | New section "Uploading a tool dataset" |
| `tests/conftest.py` | **Fix:** `BASELINE_SCHEMA` pointed at `<repo>/postgres/` (`parents[3]`), so every `platform_db` integration test was being skipped. Now `parents[2]` → `services/postgres/`. Also adds the `FakeSeek` / `seek` fixture |

New tests: `test_tool_validation.py` (7), `test_seek_writer.py` (9), `test_datasets_tools_api.py` (8), `test_dataset_uploads_tools_api.py` (8), and 3 in `test_delete_dataset_cleanup.py`.

## Deviations from the plan
- **Test isolation:** tests point `tools.CATEGORY` at a throwaway bucket, the same pattern as `INGEST_CATEGORIES` in the existing tests. They don't use the real `tools` bucket plus cleanup.
- **`INGEST_CATEGORIES` stays `{"measurements"}`.** Sessions accept `tools.CATEGORY` next to it. Adding `tools` to that set would have sent one-shot tool uploads down `_ingest_measurements`.
- **Delete response field** is `seek_workflow_deleted` (the plan said `seek_deleted`).
- **Example-script secret:** the user had already removed the fallbacks (`os.environ.get(...)`, no defaults) before step 0b ran. That edit was kept, and only the zip was rebuilt from the fixed folder.

## Verification
- `pytest services/api/tests`: **194 passed**, 2 failed, 1 error. The failures are pre-existing, identical to the baseline, and in legacy script-style tests: `test_delete_dataset_api::test_delete_existing_dataset`, `test_upload_workspace_dataset_api::test_upload_workspace_datasets_jupyter`, `test_upload_dataset_api::test_upload_zip`. The baseline before this change was 159 passed; 63 had been skipped by the conftest path bug.
- **Live end-to-end** (new API code in-process; live SEEK, Postgres and the `tools` bucket; admin token `<REDACTED>`), upload of `tests/data/sds_tool_dicom_to_nifti.zip` to project 10:
  - `POST` returned 200 with `seek_id` 43. The Postgres row is `('tools', 'sds_tool_dicom_to_nifti', '43')`, and MinIO has `primary/tool_dicom_to_nifti.cwl` + `code/tool_dicom_to_nifti.py`.
  - The SEEK workflow's title is `Tool - dicom to nifti`, its tags are `script, tool`, its class is `cwl`, and its input `#main/dicom_input` has description `measurements`. It appears in the `tag=tool` listing, with no duplicate created.
  - `get_cwl` returned the CWL.
  - `DELETE` returned 200 with `seek_workflow_deleted: true`. SEEK 43 then returns 404 and MinIO shows 0 keys.
  - Only the user's pre-existing workflow 41 remains in SEEK.

## Known limitations / follow-ups
- `UploadClient` and `digitaltwins.cli.import_dataset` don't pass `tool_type` / `seek_project_id`. A tools session started from them fails at commit and stores nothing.
- Re-uploading a tool creates a new SEEK Workflow; there is no versioning. The live SEEK already has workflow 41 with the same title.
- `tests/data/sds_tool_dicom_to_nifti` still has copied MRI metadata. Its `subjects.xlsx` / `samples.xlsx` create sub-1..3 rows for the tool; these are removed on delete. Its CWL/script filename mismatch also remains.
- The `tools` MinIO bucket is public-read.
- The legacy `services/api/app/routers/upload_workflow_to_seek` (untracked) was deleted after manual verification. It held a SEEK token that was never committed; rotate that token.
