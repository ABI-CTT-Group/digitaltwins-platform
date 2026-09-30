# Walkthrough: GUI tool dataset upload

This extends script and notebook tool upload (`docs/artifacts/2026-09-30-122834-tool-dataset-upload/`, `docs/artifacts/2026-09-30-141352-notebook-tool-upload/`) to `tool_type=gui`. A GUI tool is handled exactly like a script or notebook tool: the SDS folder goes to the MinIO `tools` bucket, the metadata to Postgres, and a SEEK Workflow tagged `tool` + `gui` is created. There's no new ADR; only the allowed values changed.

**Deferred, by decision:** integration with the portal's GUI plugin pipeline (`services/portal/backend/app/builder/build_tool.py`, `router/workflow_tool_plugin.py`). That pipeline builds the frontend into `primary/my-app.umd.js`, stores it at `tools/<expose_name>/`, and serves it from its own `Plugin` / `PluginBuild` tables. Plugin approval still assigns a placeholder `sparc-tool-<uuid>` (`TODO: Upload dataset to Digitaltwins Platform`). Until that is wired to this endpoint, a GUI tool uploaded here is stored and catalogued in SEEK but is not built or loadable in the portal.

## Changes (services/api)
| File | Change |
|---|---|
| `app/routers/datasets.py` | `tool_type` accepts `Literal["script", "notebook", "gui"]` |
| `app/routers/dataset_uploads.py` | Same for `SessionCreate.tool_type` |
| `README.md` | "Uploading a tool dataset" covers GUI tools and says they are not built as portal plugins |
| `tests/test_datasets_tools_api.py` | `test_gui_tool_is_registered_with_the_gui_type` |
| `tests/test_dataset_uploads_tools_api.py` | `test_gui_tool_session_is_registered_with_the_gui_type` |
| `tests/test_seek_writer.py` | `test_crate_tags_the_gui_type` (passed before the change; kept as a guard) |

## Verification
- `pytest services/api/tests`: **202 passed**, 2 failed, 1 error. These are the same pre-existing legacy failures as before.
- **Live end-to-end** (new API code in-process; live SEEK, Postgres and the `tools` bucket; admin token `<REDACTED>`), folder upload of `tests/data/tool_volview` (622 files, about 35 MB) with `tool_type=gui` to project 10:
  - `POST` returned 200 with `seek_id` 47. The Postgres row is `('tools', 'tool_volview', '47')`, and MinIO holds all 622 objects (`primary/tool_volview.cwl` + `code/...`).
  - The SEEK title is `Tool - VolView`, the tags are `gui, tool`, and the class is `cwl`. The workflow appears in the `tag=tool` listing.
  - `get_cwl` returned the CWL. `DELETE` returned 200 with `minio_objects_deleted: 622` and `seek_workflow_deleted: true`; SEEK 47 then returns 404, and MinIO shows 0 keys.

## Notes on the example dataset (not changed)
- The user renamed `primary/volview.cwl` to `primary/tool_volview.cwl` so it passes the `tool_*.cwl` check. `code/volview.cwl` (label "VolView") is a second copy and isn't used.
- The input's `doc` is "Medical image file in DICOM format.". The portal reads input `description` as the dataset category, so this input won't match a category such as `measurements`.
- It is unbuilt VolView source (no `dist/`), so there is no plugin bundle for the portal to load yet.
- `code/.env.example` contains only empty placeholders.
