# Walkthrough: notebook assays get a staged workspace

Decision record: [2026-10-16-stage-notebook-assay-workspace](../../decisions/2026-10-16-stage-notebook-assay-workspace.md).

## What changed

### digitaltwins-api
- **`src/digitaltwins/jupyterhub/hub.py` (new).** `JupyterHub` acts as the `digitaltwins-api` hub service. It can:
  - `ensure_server`: create the hub user if needed, spawn their default server and wait until it is ready (120 s);
  - `list_paths`;
  - `mkdir`;
  - `put_file`: an 8 MB chunked save to `<path>.staging`, then a rename into place.
- **`src/digitaltwins/jupyterhub/staging.py` (new).**
  - `workflow_uuid_by_seek_id` finds the workflow dataset for a SEEK workflow id.
  - `plan_files` lists what `assay_<id>/` should hold:
    - the workflow's `code/`;
    - for each measurement input, the root files plus the selected `primary/<sub>/<sam>/` folders, with `subjects.xlsx`, `samples.xlsx` and `manifest.xlsx` filtered to match;
    - model inputs, whole;
    - `outputs/datasets/`.
  - `stage_notebook_assay` writes only the paths that are missing.
- **`app/routers/assays.py`.** `POST /assays/{id}/run`:
  - for notebook assays, plans and stages the workspace, then returns `{url, staged, skipped}`;
  - returns 400 for a configuration problem or an unregistered workflow, 504 when the server doesn't start in time, and 502 for other hub errors;
  - checks `AIRFLOW_ENABLED` only for script assays;
  - treats missing tags as an empty list.
- **`app/routers/dependencies.py`.** New `get_jupyterhub` dependency.

### portal-backend
- **`app/utils/utils.py`.** New `assay_type(tags)`: the one `script`/`notebook`/`gui` tag, wherever it is among the tags, or `None`.
- **`app/router/dashboard.py`.**
  - Launch uses `assay_type`. An assay without exactly one type tag gets a message instead of an IndexError.
  - The assay card's `tag` is the type tag when the assay has one.

### portal-frontend
- **`AssayActionBar.vue`.** New `isNotebook` prop. Verify is enabled for ready notebook assays; for the other types it shows the tooltip "Verify is only available for notebook assays".
- **`AssayCard.vue` and `AssayReportView.vue`.** Pass `isNotebook`.
- **`useAssayActions.ts`.** `verify` opens `/jupyter/hub/user-redirect/lab/tree/assay_<id>`. The dead `workflow_outputs/.../verify.ipynb` URL is gone.

## Tests

| Suite | Result |
|---|---|
| API: `tests/test_notebook_staging.py` (17, new) and `tests/test_assay_notebook_launch.py` (6, new) | pass |
| API, full suite | 283 passed. The 10 failures and 1 error are unchanged from a clean checkout of the base commit (MinIO env and workspace-dataset harness problems). |
| Portal backend, full suite | 221 passed, 9 skipped. New cases are in `test_dashboard_assay_gui_launch.py` and `test_dashboard_assay_workflow_link.py`. |
| Frontend, full vitest suite | 155 passed. New: `AssayActionBar.spec.ts` and a `verify` case in `useAssayActions.spec.ts`. |
| vue-tsc | No errors in the changed files. |

## End-to-end check (local stack)

- Rebuilt and restarted `digitaltwins-api`, `portal-backend` and `portal-frontend`.
- Launched a notebook assay through the API. The assay had one measurement input, a one-subject cohort and one sample type. The result:
  - The response returned the workspace URL with `staged: 19, skipped: 0` in about 3 s.
  - The workspace held the workflow's notebook and the input's root files.
  - It held only the cohort subject's selected sample folder.
  - `subjects.xlsx` and `samples.xlsx` each had one row; `manifest.xlsx` listed only the staged sample files plus the `docs/` rows.
  - No `.staging` files were left behind.
- Launching again returned `staged: 0, skipped: 19`, and existing files were left untouched.
- The portal's `GET /api/dashboard/assay-launch` returned `{"type": "notebook", "data": <workspace URL>}`.
- Signed out, the Verify URL redirects to the JupyterHub login with `next` preserved.

**Not exercised live:**
- The stopped-server spawn path, so as not to stop a user's running server.
- The API with `AIRFLOW_ENABLED=false`, so as not to change the running configuration.

Both are covered by the unit tests.

## Notes

- **Hand-prepared workspaces can end up with two datasets.** One that already holds the dataset under its dataset name keeps that copy, and staging adds a second copy under the input name. A notebook expecting exactly one dataset in `inputs/datasets/` then fails until the hand-placed copy is removed. See the ADR amendments.
- **Output name mismatch in the example notebook.** The example `mri_curation` notebook writes `outputs/datasets/test_curated_dataset`, while its CWL and assay output say `curated_dataset`, so uploads put it in the default `workflows` category. This is unchanged; the fix belongs in the example dataset.
