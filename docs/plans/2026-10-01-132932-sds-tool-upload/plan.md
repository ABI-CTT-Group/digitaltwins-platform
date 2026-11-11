# Accept SDS-packaged tools in the portal tool wizard

## Context

`/upload-tool-dataset` accepts (1) a Git URL and (2) a local folder/zip of **source code**, both requiring exactly one `.cwl` at the root; portal-backend then packages the source into a SPARC dataset (`code/` + `primary/tool_<stem>.cwl`) and hands it to digitaltwins-api at Approval. Uploading an **already-packaged SDS tool dataset** (e.g. `tests/data/tool_dicom_to_nifti`) fails with "No CWL files found in the root of the selected folder", because its CWL lives in `primary/`. The API already ingests such packages (REST/CLI), but GUI users can't.

Goal: the same wizard also accepts SDS packages, from local folder/zip **and** Git repos, for **all tool types** (Script, Notebook, GUI), through the existing pipeline (Annotation → Build & Test → Approval → handoff).

### Decisions (from interview)
| Question | Decision |
|---|---|
| Route | Portal pipeline (ADR Option A preserved; handoff unchanged) |
| Detection | Auto-detect; no new radio |
| Tool types | All, incl. GUI |
| GUI SDS | npm source lives in `code/` (like `tests/data/tool_volview`); portal builds it as today and writes the bundle into `primary/` |
| Git sources | SDS-shaped repos detected too |
| SDS metadata | Passed through untouched (no sparc-me regeneration) |
| Frontend verification | Backend unittest (TDD) + manual E2E; no vitest |

### Assumptions (please correct)
- **SDS rule:** a resolved project root is an SDS package iff it has a top-level `dataset_description.xlsx`. It must then contain exactly one top-level `primary/tool_*.cwl` (same rule as the API's `find_tool_cwl`, `services/api/src/digitaltwins/tools/validation.py:7`), else a clear error. The tool's source dir is `code/`.
- Otherwise it is a source tree, and the existing rule stands: exactly one root `*.cwl`.
- For a GUI SDS, `frontend_folder`/`backend_folder` and `config.portal.json` are relative to `code/` (consistent with the deployer, which already uses `<dataset>/code/<backend_folder>`, `app/builder/deploy_tool.py:200`).
- **Workflows are out of scope:** they keep the root-CWL rule. The shared composables and `inspect_uploaded_source` get an opt-in flag so workflow behaviour is byte-for-byte unchanged.

## Design

### 1. Backend: one layout detector (new `app/builder/tool_layout.py`)
```python
@dataclass(frozen=True)
class ToolLayout:
    root: Path        # resolve_project_root(project_dir)
    source_dir: Path  # root/"code" for SDS, root otherwise
    cwl: Path         # primary/tool_*.cwl for SDS, the root .cwl otherwise
    is_sds: bool

def detect_tool_layout(project_dir: Path) -> ToolLayout   # raises RuntimeError with a user-facing message
```
- Reuses `resolve_project_root` (`app/utils/builder_utils.py:167`). The source branch delegates to the existing `root_cwl` (`app/builder/build_tool.py:34`), so the existing messages and tests hold.
- Also a non-raising helper, `try_detect_tool_layout`, for inspect/probe, which must report rather than fail.

### 2. Backend: wire it in (tools only)
- `inspect_uploaded_source(..., tool_layout=False)` (`builder_utils.py:190`): when True, list `folders_in_root` from `layout.source_dir` and set `has_cwl` from layout detection. Add `is_sds` and `cwl_path` to the result. Tool callers pass True: `/upload-source` (`workflow_tool_plugin.py:201`) and `_inspect_with_cwl_content` (`source_acquirer.py:253`, when probing for tools). Workflow callers are unchanged.
- `_inspect_with_cwl_content` and `GET /plugin/{id}/cwl` (`workflow_tool_plugin.py:525`) read `layout.cwl` instead of `read_root_cwl` (tool paths only; `read_root_cwl` stays for workflows).
  - Check whether probe is shared with workflows. If it is, pass a `kind` through so workflow probes keep the root rule.
- `PluginBuilder.build` (`build_tool.py:500`):
  - `root_cwl(project_dir)` at line 556 becomes `layout = detect_tool_layout(project_dir)`.
  - GUI: `frontend_path` and `config.portal.json` are resolved under `layout.source_dir`.
- `create_sparc_dataset` (`build_tool.py:143`), same signature, with layout detected inside:
  - **SDS:** copy every top-level item of `layout.root` except `code/` via `copy_item` (metadata xlsx, `primary/` with its CWL, docs, …). Skip sparc-me `create_empty_dataset`/`save`.
  - **Source:** existing sparc-me path, unchanged.
  - **Both:** the existing `code/` copy logic, run from `layout.source_dir`. It is extracted into a small helper so both branches share it (it already skips `node_modules`/`.git`/`dist`/`build`). The existing GUI build-output → `primary/` step is unchanged.
  - **Source only:** copy root CWL → `primary/tool_<stem>.cwl` (SDS already has it).
- **Unchanged:** handoff (`app/services/tool_handoff.py`, which sends `build.dataset_path` as-is), the API, DB schema, deployer, and the MinIO `tool-builds` step.

### 3. Frontend: mirror the rule (tool kind only)
- `composables/useLocalFolderInfo.ts`: `refresh(source, checkCwl, { allowSds })`. With `allowSds`, folder and zip scans also accept `dataset_description.xlsx` at root + exactly one `primary/tool_*.cwl`. They then set `sdsDetected`, take `foldersInRoot` from `code/`, and pass the CWL check.
- `composables/useGithubRepoInfo.ts`:
  - Public GitHub: when the root listing has `dataset_description.xlsx`, list `primary/` via the Contents API and apply the same rule.
  - Backend probe: read the new `isSds` from the response.
- `views/upload-dataset/components/utils.ts` `getRepoRootCWLContent`: fall back to `primary/tool_*.cwl` when the repo is SDS-shaped. It is used by `BaseAnnotateStep.loadToolCwl` (`BaseAnnotateStep.vue:246`). The `_loadCwlViaBackendProbe` and local paths get this from the backend change.
- `BaseInformationStep.vue`: pass `allowSds: type === 'tool'`. Show a small "Detected SDS package. Metadata is kept as-is." hint (via `CommonInfoForm`).
- New error message when neither rule matches: *"No CWL found. Expected one .cwl at the root (source code) or one primary/tool_*.cwl in an SDS package (dataset_description.xlsx at the root)."*
- `models/types.ts`: add `isSds` to the probe/upload-source response types.

### 4. ADR (draft, created after approval)
`docs/decisions/2026-10-01-accept-sds-packages-in-tool-wizard.md`. It amends `2026-10-01-unified-tool-dataset-ingest.md`, and Option A stays in place.
- **Decision:** auto-detected SDS through the existing portal pipeline. GUI SDS packages are built from `code/`. Metadata passes through untouched.
- **Alternatives:**
  - Direct browser → API upload (rejected Option B: no Build & Test or approval).
  - An explicit third source radio (Git-hosted SDS would need yet another mode).
  - Prebuilt GUI bundles (no convention for the UMD global name; deferred).
  - Regenerating metadata (discards the user's curation).
- **Consequences:**
  - A source tree with a stray root `dataset_description.xlsx` is treated as SDS.
  - A prebuilt bundle in a GUI SDS's `primary/` is overwritten by the build output.
  - The rule is duplicated in the browser, the portal backend and the API (it is small; the tests pin it).

## Steps (TDD, backend: `python -m unittest discover tests` in `services/portal/backend`)
0. First action after approval (plan mode blocks it now): sync this plan, the ADR draft and a task checklist to `docs/artifacts/<YYYY-MM-DD-HHMMSS>-sds-tool-upload/`, and resync after every update.
1. Red/green `tests/test_tool_layout.py`:
   - source root CWL
   - SDS with one `primary/tool_x.cwl`
   - SDS with 0 or 2 tool CWLs, or a non-`tool_` CWL → error
   - single-wrapper folder
   - `source_dir` is `code/`
   → verify: new tests pass.
2. Red/green in `tests/test_tool_build_dataset.py` (`CreateSparcDatasetTest`, `BuildUploadTest`):
   - Script SDS → output equals the input tree, with the xlsx bytes unchanged.
   - Notebook SDS.
   - GUI SDS with a fake `dist` → `primary/` = bundle + CWL.
   - SDS `code/node_modules` is not copied.
   - `build()` on a local Script SDS succeeds and uploads to `tool-builds`.

   → verify: the existing tests in this file are still green.
3. Red/green for inspect/probe/CWL endpoint:
   - `inspect_uploaded_source(tool_layout=True)` on an SDS gives `is_sds`, `has_cwl`, and `code/` folders.
   - Workflow mode is unchanged.
   - `GET /plugin/{id}/cwl` returns the primary CWL for an SDS local plugin (via `tests/tool_app.py`).
   - `_inspect_with_cwl_content` inlines the primary CWL.
4. Frontend changes (§3) → verify: `npm run lint` and `npm run build` in `services/portal/frontend`.
5. Write the ADR, sync the plan/task/ADR to `docs/artifacts/<YYYY-MM-DD-HHMMSS>-sds-tool-upload/`, and scan with gitleaks.
6. Manual E2E (below). Then the final full backend test run.

## Verification (manual E2E at http://localhost/upload-tool-dataset, after rebuilding the portal containers)
- `tests/data/tool_dicom_to_nifti` as a folder and as `.zip` (Script): the SDS hint appears, Annotation shows the CWL ports, Build & Test succeeds, and the `tool-builds/<expose>/` object list matches the input tree. Approval: the API dataset gets a `seek_id`, and its MinIO `tools/<uuid>/` keeps the original `dataset_description.xlsx`.
- `tests/data/tool_cohort_selection` (Notebook): same checks.
- `tests/data/tool_volview` (GUI): the npm build runs in `code/`, `primary/` contains `my-app.umd.js` + `tool_volview.cwl`, and the tool launches from the Tool Hub test build.
- A public GitHub repo containing an SDS fixture: detection + Annotation CWL work through the Contents API. A private or GitLab one exercises the probe path.
- Regressions: a source-shaped tool (folder and GitHub) and a workflow upload still require a root CWL. A folder with neither layout shows the new error.

## Out of scope / noted
- Prefilling name/description from `dataset_description.xlsx`, and prebuilt GUI bundles.
- Existing bug: `execute_build_in_background` writes `error`/`error_message`, but the column is `error_messages` (`app/utils/builder_utils.py:323,336`), so build errors are never saved.
- Fixture issue: `tool_dicom_to_nifti.cwl` runs `dicom_to_nifti.py`, but the file is `tool_dicom_to_nifti.py` and isn't staged into the working directory.
