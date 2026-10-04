# Walkthrough: workflow dataset upload

Implements [plan.md](plan.md). The design decisions are recorded in [ADR 2026-10-02-workflow-dataset-ingest](../../decisions/2026-10-02-workflow-dataset-ingest.md).

## What changed (`services/api`)

| File | Change |
|---|---|
| `src/digitaltwins/workflows/__init__.py` (new) | `CATEGORY = "workflows"`, `WORKFLOW_TYPES`. |
| `src/digitaltwins/workflows/validation.py` (new) | `load_workflow(staging, workflow_type)` returns `WorkflowLayout(root, workflow_cwl, steps, tool_code)`. Rules: exactly one `primary/workflow_*.cwl` with `class: Workflow`; every step `run`s a `primary/tool_*.cwl` with `class: CommandLineTool`; no unused tool CWLs; notebook and gui have exactly one step. Code split: `code/<stem>/`, otherwise `code/<stem>.*` (script; `400` if there are none), otherwise all of `code/` (notebook/gui). |
| `src/digitaltwins/workflows/pipeline.py` (new) | `commit_workflow` (described below), plus `linked_tools`, `tool_uuids` and `annotate_workflow`. |
| `src/digitaltwins/workflows/fhir.py` (new) | `build_descriptions(layout, uuid, name, tool_uuids, client)` returns `({"workflow": ...}, {tool_cwl: {"workflow_tool": ...}})`. It validates step and port ids and `resource_type` (ImagingStudy, DocumentReference or Observation), and accepts the stored form so descriptions round-trip. Also `push` (PlanDefinition) and `delete`. |
| `postgres/migrations/0004_workflow_dataset.sql` (new) | `dataset.workflow_type`, `upload_session.workflow_type`, and `workflow_tool(workflow_dataset_uuid ON DELETE CASCADE, step_id, tool_dataset_uuid)`. The tool foreign key has no cascade. |
| `seek/writer.py` | `_build_crate` is generalised from `build_tool_crate`. New `build_workflow_crate`: tagged `workflow` + type, with the tool CWLs in `hasPart` and the zip. `_post_crate` is shared by `register_tool` and the new `register_workflow`. |
| `tools/pipeline.py` | `_link` becomes the public `link_tool`, reused by the workflow pipeline. `commit_tool` is otherwise unchanged. |
| `tools/fhir.py` | New `build_cwl_descriptions(cwl_path, …)` and `cwl_ports(cwl_path)`. `build_descriptions` and `ports` delegate to them. |
| `measurements/sessions.py`, `measurements/pipeline.py` | `create_session(workflow_type=)`. `get_dataset_row` also returns `workflow_type`. |
| `measurements/jobs.py` | `_commit` gets a workflow branch (commit, then optional annotate). `run_fhir_push_job` branches on `workflow_type`. `_push_workflow`: delete the old PlanDefinition, re-push each tool's ActivityDefinition (with per-tool `fhir_status`), then push the PlanDefinition. |
| `core/deleter.py`, `postgres/deleter.py` | New `DatasetInUseError` and `delete_dataset(uuid, delete_tools=None)`. The new `workflow_links` reads the workflow type, its tools and the workflows that use a tool. SEEK and FHIR cleanup also covers workflows, and tools are deleted after the workflow when `delete_tools=true`. |
| `app/routers/datasets.py` | `POST /datasets?category=workflows&workflow_type=&seek_project_id=` goes to `_ingest_workflow`. `DELETE ?delete_tools=` returns 409 with `{message, tools \| workflows}`, and its response adds `tools_deleted`. |
| `app/routers/dataset_uploads.py` | Sessions accept `workflows` (with `workflow_type`). Finalize runs `load_workflow` and the descriptions pre-check. The session view includes `workflow_type`. |
| `app/routers/dataset_fhir.py` | Workflow branches for tree (descriptions plus per-step ports), annotation PUT (stores the tools' and the workflow's descriptions) and preview. |
| `cli/import_dataset.py`, `client.py` | `--workflow-type` / `workflow_type=`. |
| `README.md` | New section, "Uploading a workflow dataset". |

### `commit_workflow` steps

1. Validate the dataset.
2. Assemble each tool dataset in a temp dir under staging: the root files, `primary/<tool>.cwl` and its code.
3. Register in SEEK: each tool, then the workflow.
4. Store each tool and call `link_tool`.
5. Store the workflow as uploaded, then call `_link_workflow` (seek_id, workflow_type, `workflow_tool` rows).
6. If anything fails, roll back newest first: datasets, then SEEK entries.

### Deviations from the plan

- **No `store_tool` extraction.** The workflow pipeline calls `Uploader` and `link_tool` directly, so `commit_tool` is untouched apart from the rename.
- **Storage failures after SEEK registration.** They roll everything back and re-raise the original error, which surfaces as `500`. Only SEEK failures return `502`.
- **Tool FHIR status.** A tool's `fhir_status` stays `none` until the workflow's push job reaches it (`pushing`, then `completed` or `failed`).

## Tests

All tests ran in a throwaway `--rm` container from the `digitaltwins-api` image on the `digitaltwins-platform` network. They used scratch Postgres databases, throwaway MinIO buckets, and the fake SEEK and HAPI.

**New tests:**
- `test_workflow_validation.py`: 22
- `test_workflow_fhir.py`: 15
- `test_datasets_workflows_api.py`: 16
- `test_dataset_uploads_workflows_api.py`: 9
- additions:
  - `test_seek_writer.py`: +3
  - `test_migrate.py`: +1
  - `test_import_dataset_cli.py`: +3
  - `test_upload_client.py`: +1
  - `test_delete_dataset_cleanup.py`: +5

**Changed tests:**
- `test_dataset_uploads_api.py::test_other_categories_are_rejected` now uses `models`, because `workflows` is a session category now.
- `test_datasets_tools_api.py` patches the renamed `link_tool`.

**Fixtures:** `FakeSeek.register_workflow` and `fail_register_workflow`; `FakeHapi` gains a workflow mode. Its PlanDefinition actions hold `{"reference": "ActivityDefinition/<id>"}`, so the fake's referential-integrity check also tests the delete order.

**Full suite:** 311 passed, 4 failed and 1 error. Before the change it was 237 passed with the same failures:
- `test_delete_dataset_api.py::test_delete_nonexistent_dataset`
- `test_delete_dataset_api.py::test_delete_existing_dataset`
- `test_download_dataset_api.py::test_download_dataset`
- `test_upload_workspace_dataset_api.py::test_upload_workspace_datasets_jupyter`
- `test_upload_dataset_api.py::test_upload_zip` (the error)

**Example datasets:** `load_workflow` on both real examples gives:
- `workflow_image_conversion`: steps `dicom_to_nifti` and `dicom_to_nrrd`, each with its own `code/tool_*.py`;
- `workflow_volview`: step `volview`, with all of `code/`.

## Live verification (2026-10-02)

**Setup:**
- New API code ran in-process (FastAPI `TestClient`) in a throwaway container on the `digitaltwins-platform` network.
- It used the live Postgres, MinIO, SEEK (project 10) and HAPI, as user `admin1` (token `<REDACTED>`, refreshed per call).
- Migration `0004` was applied to the live database. The user then rebuilt and restarted `digitaltwins-api`, which now serves the new code.

**SEEK spike (plan step 0):**
- `register_workflow` was called on `tests/data/workflow_image_conversion`, giving SEEK workflow 64 (deleted again).
- Title `Workflow - Image conversion`, tags `script` and `workflow`.
- `internals`: input `#main/dicom_input`, outputs `#main/nifti_output` and `#main/nrrd_output`, steps `#main/dicom_to_nifti` and `#main/dicom_to_nrrd`.
- So the packed tool CWLs resolve, and no fallback is needed.

**Script workflow:** `workflow_image_conversion`, `workflow_type=script`, `fhir=auto`.
- Workflow dataset (`workflows` bucket, 18 objects): `seek_id` 67, `workflow_type` `script`, `fhir_status` `completed`.
- Tool datasets `tool_dicom_to_nifti` (SEEK 65) and `tool_dicom_to_nrrd` (SEEK 66):
  - 14 objects each, in the `tools` bucket;
  - each has only its own `code/tool_*.py`;
  - `tool_type` `script`, `fhir_status` `completed`;
  - SEEK tags `script` and `tool`.
- `workflow_tool` rows for both steps.
- `GET /workflows` lists the workflow.
- HAPI: ActivityDefinitions 1405 and 1406, and PlanDefinition 1407 with actions `dicom_to_nifti → ActivityDefinition/1405` and `dicom_to_nrrd → ActivityDefinition/1406`.

**Deleting the script workflow:**
1. `DELETE` on a tool returned `409` naming the workflow.
2. `DELETE` on the workflow without `delete_tools` returned `409` listing both tools.
3. `DELETE ?delete_tools=true` returned `200`:
   - 18 objects, 1 PlanDefinition and the SEEK workflow deleted;
   - `tools_deleted` lists both tools;
   - afterwards: no dataset rows or objects, SEEK 404 for all three, and no PlanDefinition or ActivityDefinitions.

**GUI workflow:** `workflow_volview`, `workflow_type=gui`, `fhir=none`.
- Workflow dataset (623 objects): SEEK 69, tags `gui` and `workflow`, step `#main/volview`.
- Tool `tool_volview` (SEEK 68, tags `gui` and `tool`) got all of `code/` (622 objects).
- `DELETE ?delete_tools=false`: the workflow was removed (SEEK 404). The tool stayed (row, objects, SEEK 200).
- The tool, now standalone, was then deleted on its own: `200`, SEEK workflow deleted, nothing left.

**Left in place for inspection:** a second upload of `workflow_image_conversion` (`fhir=auto`).

| | Dataset | SEEK | HAPI |
|---|---|---|---|
| Workflow | `a8d6da0e-bde6-11f1-b540-5ee24f07b041` | 72 | PlanDefinition 1410 |
| Tool `dicom_to_nifti` | `a89fa502-bde6-11f1-87f5-5ee24f07b041` | 70 | ActivityDefinition 1408 |
| Tool `dicom_to_nrrd` | `a8b7d12c-bde6-11f1-a919-5ee24f07b041` | 71 | ActivityDefinition 1409 |

To remove it: `DELETE /datasets/a8d6da0e-bde6-11f1-b540-5ee24f07b041?delete_tools=true`.

**Note from the first run:** my e2e script's own HAPI search returned a stale empty bundle. HAPI caches identical searches, and the script didn't send `Cache-Control: no-cache` (the API's `HapiRest` already does). This was a script bug, not a product one.

## Notes found along the way

- `tests/data/workflow_image_conversion/*.xlsx` were copied from `curated_dataset`. Its manifest lists 450 DICOM files that the dataset doesn't contain. They are stored as-is and loaded into the manifest table.
- That dataset's tool CWLs run `dicom_to_nifti.py` / `dicom_to_nrrd.py`, but `code/` has `tool_dicom_to_nifti.py` / `tool_dicom_to_nrrd.py`.
- The DAG in its `code/` (and `services/airflow/dags/workflow_image_conversion.py`) contains a default MinIO secret key in plain text (`<REDACTED>`).
