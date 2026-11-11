# Walkthrough: notebook tool dataset upload

This extends script-tool upload (`docs/artifacts/2026-09-30-122834-tool-dataset-upload/`, ADR `docs/decisions/2026-09-30-register-tools-in-seek-via-single-ro-crate-post.md`) to `tool_type=notebook`. There's no new ADR, because no design choice was involved: the pipeline, the SEEK crate and the validation never depended on the tool type.

## Changes (services/api)
| File | Change |
|---|---|
| `app/routers/datasets.py` | `tool_type` accepts `Literal["script", "notebook"]` (one-shot `POST /datasets`) |
| `app/routers/dataset_uploads.py` | Same for `SessionCreate.tool_type` (resumable sessions) |
| `README.md` | "Uploading a tool dataset" covers notebooks; `gui` is not supported yet; the example zip is renamed to `tool_dicom_to_nifti.zip` |
| `tests/test_datasets_tools_api.py` | `test_notebook_tool_is_registered_with_the_notebook_type` |
| `tests/test_dataset_uploads_tools_api.py` | `test_notebook_tool_session_is_registered_with_the_notebook_type` |
| `tests/test_seek_writer.py` | `test_crate_tags_the_notebook_type` (passed before the change; kept as a guard) |

A notebook tool needs the same layout as a script tool: exactly one top-level `primary/tool_*.cwl`, with the notebook in `code/`. Following the minimal-validation decision, nothing checks that `code/` actually holds an `.ipynb`.

## Verification
- `pytest services/api/tests`: **197 passed**, 2 failed, 1 error. The failures are the same pre-existing legacy tests as before (`test_delete_dataset_api::test_delete_existing_dataset`, `test_upload_workspace_dataset_api::test_upload_workspace_datasets_jupyter`, `test_upload_dataset_api::test_upload_zip`).
- **Live end-to-end** (new API code in-process; live SEEK, Postgres and the `tools` bucket; admin token `<REDACTED>`), folder upload of `tests/data/tool_cohort_selection` with `tool_type=notebook` to project 10:
  - `POST` returned 200 with `seek_id` 45. The Postgres row is `('tools', 'tool_cohort_selection', '45')`, and MinIO has `primary/tool_cohort_selection.cwl` + `code/cohort_selection.ipynb`.
  - The SEEK title is `Tool - cohort selection`, the tags are `notebook, tool`, and the class is `cwl`. The CWL has no inputs, and its one output `#main/cohort_dataset` has no description. The workflow appears in the `tag=tool` listing.
  - `get_cwl` returned the CWL. `DELETE` returned 200 with `seek_workflow_deleted: true`; SEEK 45 then returns 404, and MinIO shows 0 keys.

## Notes on the example dataset (not changed)
- The user fixed the stray backtick at the end of the CWL, which had made it invalid YAML.
- The CWL has `inputs: {}` and an output with no `doc`, so the portal gets no input categories and a null output category.
- `baseCommand: ["jupyter", "notebook", ...]` starts a notebook server rather than executing the notebook, and the notebook isn't staged into the container.
- The notebook defaults `API_USERNAME` / `API_PASSWORD` to `admin` / `admin` (a placeholder, not a real secret). It also posts to the old `/dataset` path with `CATEGORY = "measurements"`.
