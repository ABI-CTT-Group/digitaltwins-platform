# Plan: stage notebook assays into JupyterHub; fix launch type, Verify and the Airflow gate

## Context

A notebook assay's Launch calls `POST /assays/{id}/run`. For notebook assays that call only returns `…/jupyter/user/<user>/lab/tree/assay_<id>`, and nothing puts the registered notebook or the assay's inputs into that folder. Unless someone copies them in by hand, the user opens an empty or missing folder.

Three related defects:
- **Airflow gate.** `run_assay` returns 503 when `AIRFLOW_ENABLED=false`, even for notebook assays, which never use Airflow ([assays.py:561](services/api/app/routers/assays.py#L561)).
- **Launch type.** The portal picks the launch type from `tags[0]` ([dashboard.py:504](services/portal/backend/app/router/dashboard.py#L504)). Assay tags are set by hand in SEEK, so their order is arbitrary, and an empty list raises IndexError.
- **Verify.** The button is permanently disabled. Its handler opens `workflow_outputs/<uuid>/verify.ipynb`, which nothing creates.

**Outcome.** Clicking Launch on a notebook assay, with the user's Jupyter server stopped and Airflow disabled, opens JupyterHub on `assay_<id>/`. The folder holds:
- the workflow's notebook;
- a cohort and sample-type subset of each input dataset, with consistent SDS metadata;
- each model input in full;
- an empty `outputs/datasets/`.

Running the notebook writes results there, and the existing "upload workspace" ingests them. Verify on a notebook assay opens the same workspace.

### Decisions from the interview

| Topic | Decision |
|---|---|
| Mechanism | The API pushes the files through JupyterHub. It uses the hub service token (admin role) to create or start the user's server, then writes through the Jupyter contents API. |
| Input scope | A cohort and sample-type subset of each measurement input: root files plus the selected `primary/<sub>/<sam>/`, with `subjects.xlsx`, `samples.xlsx` and `manifest.xlsx` filtered to match. |
| Model inputs | Staged in full under `inputs/models/<input name>/`. |
| Re-launch | Stage only the files that are missing. Never overwrite, so user edits and outputs survive. |
| Size and timing | Synchronous, inside `/run`, and resumable. Each file is uploaded under a temporary name and then renamed, so "exists" means "complete". A request that times out (600 s at nginx and in the portal client) is finished by clicking Launch again. |
| Verify | Notebook assays: opens the workspace URL only, with no staging. Script and gui assays: stays disabled. |
| Launch type | The one tag in `{script, notebook, gui}`, wherever it is in the tag list. |

## Staged layout (`/home/jovyan/work/assay_<id>/`)

```
<everything in workflows/<workflow_uuid>/code/, subpaths kept>   e.g. mri_curation.ipynb
inputs/datasets/<input name>/        cohort/sample-type subset, SDS metadata filtered
inputs/models/<input name>/          whole model dataset
outputs/datasets/                    created empty; the existing upload/download contract
```

- `<input name>` is the assay input's `name` with any CWL `#main/` prefix removed, for example `raw_dataset`.
- The code comes from the workflow dataset's own `code/`. For notebook workflows this is identical to the single tool's `code/` ([validation.py:53-63](services/api/src/digitaltwins/workflows/validation.py#L53-L63)), and it is where `deploy.py` reads script workflow code from, so no `workflow_tool` join is needed.

## Changes

### 1. API: JupyterHub client
New file: `services/api/src/digitaltwins/jupyterhub/hub.py`.

The `JupyterHub` class is configured from the existing `JUPYTERHUB_INTERNAL_URL` and `JUPYTERHUB_API_TOKEN` environment variables, and sends the same `Authorization: token …` header that `_download_jupyter_folder` already sends.

- `ensure_server(username)`:
  - `GET /hub/api/users/{u}`; on 404, `POST` to create the user.
  - If the default server isn't ready, `POST /hub/api/users/{u}/server`, then poll the user until `servers[""].ready`.
  - Timeout of 120 s, matching `DockerSpawner.start_timeout`.
  - Raises `HubError` or `HubTimeout`.
- `existing_files(username, root) -> set[str]`: a recursive contents-API listing. A missing root returns an empty set.
- `mkdir(username, path)`: `PUT {type: directory}` for each missing ancestor, since jupyter_server doesn't create parents.
- `put_file(username, path, chunks)`:
  - Uploads to `<path>.staging` (not dot-prefixed: jupyter_server refuses hidden paths) with the contents-API `chunk` protocol (8 MB base64 parts: 1..n, last part -1).
  - Then `PATCH` renames it to `path`.
  - A leftover `.staging` file from an interrupted run is overwritten next time.

### 2. API: staging
New file: `services/api/src/digitaltwins/jupyterhub/staging.py`.

- `workflow_uuid_by_seek_id(conn, seek_id)`: a parameterised `SELECT dataset_uuid FROM dataset WHERE seek_id = %s AND workflow_type IS NOT NULL`, in the style of `deploy._workflow_row` ([deploy.py:83](services/api/src/digitaltwins/workflows/deploy.py#L83)). Raises `LookupError`. The unused, string-formatted `postgres/querier.py:126` is not used.
- `plan_files(configs, samples, workflow_uuid, downloader) -> list[Entry]`: a pure function returning `(remote_path, source)` pairs, where the source is either a MinIO `(bucket, key)` or generated bytes.
  - **Code:** every object under `workflows/<uuid>/code/`.
  - **Measurement inputs.**
    - Samples come from `_discover_samples`, which already applies cohort and `sample_type`.
    - Staged: every object of `<uuid>/` outside `primary/`, plus the `primary/<sub>/<sam>/` objects of the selected samples.
    - The bucket comes from `downloader.find_bucket`.
  - **Filtered metadata.**
    - `subjects.xlsx` keeps the rows of selected subjects (`subject id`).
    - `samples.xlsx` keeps the selected `(subject id, sample id)` pairs.
    - `manifest.xlsx` keeps rows whose `filename` is a staged path. Root manifests use `primary/sub-1/sam-1/…` paths, per `tests/data/example_sds_dataset`.
    - All filtering uses openpyxl row deletion, as `_reconcile_manifest` does ([assays.py:397](services/api/app/routers/assays.py#L397)).
  - **Model inputs:** every object of `<uuid>/`.
  - **Outputs:** a directory entry for `outputs/datasets/`.
- `stage_notebook_assay(hub, username, assay_id, entries, downloader)`:
  - Calls `ensure_server`, then `existing_files`.
  - Uploads only entries whose path is absent, streaming MinIO objects through `downloader.open_object`.
  - Returns `{"staged": n, "skipped": m}`.
  - The metadata xlsx files are filtered only when they are themselves missing, so a resumed run doesn't re-download them.

### 3. API: `run_assay`
File: [assays.py:543](services/api/app/routers/assays.py#L543).

- Use `tags = … or []`, since tags can be `None` today and `in` would raise TypeError.
- Move the `AIRFLOW_ENABLED` 503 inside the `script` branch.
- Notebook branch:
  - `_fetch_assay_configs` and `_discover_samples`; a `ValueError` becomes 400.
  - Look up the workflow UUID by `workflow_seek_id`; a `LookupError` becomes 400 "workflow not registered".
  - `plan_files`, then `stage_notebook_assay`.
  - `HubTimeout` becomes 504; `HubError` and `requests` errors become 502.
  - Return `{"url": <unchanged monitor URL>, "staged": n, "skipped": m}`.
- Add dependencies `conn=Depends(get_conn)` and `downloader=Depends(get_minio_downloader)`, which `get_assay_gui_inputs` already uses.

### 4. Portal backend: launch type
File: [dashboard.py](services/portal/backend/app/router/dashboard.py).

- Add `assay_type(tags) -> Optional[str]` in `app/utils/utils.py`. It returns the single tag found in `{script, notebook, gui}` (case-insensitive), or `None` when there are none or more than one. It sits beside `get_workflow_type`, whose `'other'`/`'error'` return values don't fit this use.
- Launch (`:504`) uses `assay_type(tags or [])`. `None` returns `{"message": "Tag this assay in SEEK with exactly one of script, notebook or gui."}` instead of `None` or an IndexError.
- In the assay list (`:183`), the card `tag` becomes `assay_type(tags_list) or (tags_list[0] if tags_list else None)`. The chip, `isScript` and the new `isNotebook` then follow the type tag.

### 5. Portal frontend: Verify
- [AssayActionBar.vue](services/portal/frontend/src/views/dashboard/components/AssayActionBar.vue):
  - New `isNotebook` prop. Verify is enabled when `ready && isNotebook`.
  - The tooltip, shown only when disabled, reads "Verify is only available for notebook assays".
- [AssayCard.vue](services/portal/frontend/src/views/dashboard/components/AssayCard.vue): compute `isNotebook` from `data.tag`, the same way `isScript` is computed, and pass it down. Do the same in `AssayReportView.vue`, which also renders the bar.
- [useAssayActions.ts:135](services/portal/frontend/src/composables/useAssayActions.ts#L135): `verify(seekId)` opens `${JUPYTER_BASE_URL}/hub/user-redirect/lab/tree/assay_${seekId}`.
  - JupyterHub's `user-redirect` resolves the signed-in user, so the frontend doesn't need the username.
  - The dead `workflow_outputs/…/verify.ipynb` URL is removed.

## Tests (red first, per TDD)

**API** (`services/api/tests/`):
- New `test_notebook_staging.py`:
  - Uses `FakeDownloader` from `test_assay_gui_launch.py` and a fake hub (a recording session or a `requests` patch).
  - Covers the plan contents: code paths, sample subset, root files, model inputs whole, `#main/` stripped.
  - Covers metadata filtering on xlsx built from `tests/data/example_sds_dataset`.
  - Covers skip-existing.
  - Checks the upload goes to `.staging` and is then renamed.
  - Covers `ensure_server` across the 404→create, start→poll→ready and timeout paths.
- New `test_assay_notebook_launch.py`, using router-level dependency overrides:
  - A notebook launch succeeds with `AIRFLOW_ENABLED=False`.
  - A script launch still returns 503.
  - `tags=None` gives 400, not 500.
  - An unregistered workflow gives 400.
  - A hub timeout gives 504.

**Portal backend:** extend `tests/test_dashboard_assay_gui_launch.py`:
- A notebook launch with tags `["demo", "notebook"]`.
- Empty tags and two type tags each return the message.
- The list card's `tag` picks the type tag.

**Frontend (vitest):**
- `useAssayActions.spec.ts`: `verify` opens the user-redirect URL.
- New `AssayActionBar.spec.ts`: Verify is enabled only for a ready notebook assay.

Run the tests in throwaway containers, following the memory recipe:
- API: `docker run --rm -v …/services/api:/digitaltwins-api … python -m pytest`.
- Portal tests use `--network none`, never inside `portal-backend-1`.

## Verification (end to end)

1. Rebuild and restart `digitaltwins-api`, `portal-backend` and `portal-frontend` with `docker compose up -d --build <svc>`.
2. Stop the user's Jupyter server. In a local scratch run, clear that user's `assay_<id>/`.
3. In the portal, click Launch on notebook assay `<id>` (one input dataset, a one-subject cohort, one sample type). Expect a spinner, then a JupyterLab tab on `assay_<id>/` containing:
   - `mri_curation.ipynb`;
   - `inputs/datasets/raw_dataset/`, with only the cohort subject's selected sample folder and `samples.xlsx`/`subjects.xlsx`/`manifest.xlsx` rows only for that subject and sample;
   - an empty `outputs/datasets/`.
4. Edit the notebook and click Launch again. The edit survives and the response reports `staged: 0`.
5. Set `AIRFLOW_ENABLED=false` on the API and repeat the launch. It still works, while a script assay returns 503.
6. Verify on the notebook card opens the same workspace. On script and gui cards it is disabled.
7. Run the notebook, then use "upload workspace". The datasets are ingested as before.

## Process items (on approval)

- **ADR.** Write `docs/decisions/2026-10-16-stage-notebook-assay-workspace.md`. It records three real choices:
  - push through the hub vs. the notebook pulling its own data vs. a spawn-time hook;
  - subset vs. whole datasets;
  - sync and resumable vs. async.
- **Artifacts.** Sync this plan, and the task list and walkthrough later, to `docs/artifacts/2026-10-16-103613-notebook-assay-staging/`. Use repo-relative paths only, keep live assay and SEEK ids out of committed walkthroughs, and run a gitleaks scan before staging.
- **Containers.** Rebuild and restart `digitaltwins-api`, `portal-backend` and `portal-frontend`.

## Out of scope (noted)

- **Output name mismatch.** The example notebook writes `outputs/datasets/test_curated_dataset`, but its CWL and the assay output name say `curated_dataset`, so the upload defaults it to the `workflows` category. The example is in the gitignored `my_workspace/`, so fixing it is a separate edit to the dataset.
- **Stale inputs.** If the assay's cohort changes after staging, the "stage missing only" rule leaves the old subset in place. To restage, the user deletes `inputs/` in Jupyter.
- **Hard-coded hub token.** The hub service token falls back to a hard-coded default because neither compose file passes `JUPYTERHUB_API_TOKEN`. This is existing behaviour and a separate hardening task.
