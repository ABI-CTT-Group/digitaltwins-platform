# Walkthrough: accept SDS-packaged tools in the portal tool wizard

ADR: [docs/decisions/2026-10-01-accept-sds-packages-in-tool-wizard.md](../../decisions/2026-10-01-accept-sds-packages-in-tool-wizard.md)

## What changed

The wizard at `/upload-tool-dataset` accepts a tool in two layouts. It checks for both automatically, and there is no new radio button.

| Layout | How it is recognised | Source | CWL |
|---|---|---|---|
| Source code | no `dataset_description.xlsx` at the root | the root | exactly one root `*.cwl` |
| SDS package | `dataset_description.xlsx` at the root | `code/` | exactly one `primary/tool_*.cwl` |

Both layouts work for local folders, local zips and Git repos (public GitHub through the Contents API, and the others through the backend probe). They work for every tool type. Workflows keep the root-CWL rule.

### portal-backend
- `app/builder/tool_layout.py` (new):
  - `detect_tool_layout`. `root_cwl` moved here from `build_tool.py`, and its error message now names both layouts.
  - `inspect_tool_source` and `read_tool_cwl`: tool-only wrappers around `inspect_uploaded_source` and `read_root_cwl`, so the workflow paths are untouched.
- `PluginBuilder.build`: fails early through `detect_tool_layout`. A GUI build runs npm in `layout.source_dir`, which is `code/` for an SDS package.
- `PluginBuilder.create_sparc_dataset`:
  - SDS: copies the package's top-level items except `code/` unchanged, with no sparc-me regeneration.
  - Both layouts: `code/` is re-copied through the existing filter (no `node_modules`, `.git`, `dist` or `build`), and the GUI bundle goes into `primary/`.
- `SourceSpec.tool_layout`: the tool `/probe-source` sets it. The workflow probe is unchanged.
- `/upload-source` returns `is_sds`. `GET /plugin/{id}/cwl` serves the SDS CWL.
- The handoff, the digitaltwins-api, the DB schema and the deployer are unchanged.

### portal frontend
- `views/upload-dataset/components/utils.ts` holds the shared rule: `SDS_MARKER`, `sdsToolCwls`, `sdsCwlResult` and `noToolCwlMessage`. The Annotation step's public-GitHub CWL fetch reads `primary/tool_*.cwl` for an SDS repo.
- `useLocalFolderInfo.refresh(source, checkCwl, allowSds)`: for an SDS folder or zip, `foldersInRoot` comes from `code/` (used by the GUI frontend/backend folder selects).
- `useGithubRepoInfo`: public GitHub lists `code/` and `primary/` when the repo is an SDS. The backend probe passes `isSds` through.
- `CommonInfoForm` shows "Detected an SDS package: its metadata is kept as-is."

## Verification done
- Backend unittest, run in the portal-backend image with `/app/.venv/bin/python -m unittest discover tests`: **103 tests OK** (9 skipped). The baseline was 81 OK.
  - New: `tests/test_tool_layout.py` (7), `tests/test_tool_sds_source.py` (9), and 6 new cases in `tests/test_tool_build_dataset.py`.
- Frontend, in the frontend Dockerfile's builder stage:
  - `yarn build` OK.
  - `vue-tsc --noEmit`: 0 errors.
  - eslint on the changed files: 0 errors (the 2 warnings are on lines that already had them).
- Real fixtures (`tests/data`): `tool_dicom_to_nifti` (Script), `tool_cohort_selection` (Notebook) and `tool_volview` (GUI) are all detected as SDS. The CWL is read from `primary/`, and `create_sparc_dataset` keeps `dataset_description.xlsx` byte-identical.

## Not yet verified (manual E2E, needs rebuilt portal containers)
- The full wizard flow at http://localhost/upload-tool-dataset for each fixture (folder and zip), through Approval to digitaltwins-api.
- An npm build of `tool_volview` from `code/`, and launching it from the Tool Hub.
- A public GitHub repo with an SDS layout, and a private or GitLab one through the probe.
- Regressions: a source-shaped tool and a workflow upload.

## Known, out of scope
- `execute_build_in_background` writes `error`/`error_message`, but the column is `error_messages`, so build errors are never saved.
- `tests/data/tool_dicom_to_nifti/primary/tool_dicom_to_nifti.cwl` runs `dicom_to_nifti.py`, but the script is `tool_dicom_to_nifti.py`, and nothing stages it into the working directory.
