# Stage a notebook assay's workspace in JupyterHub at launch

- **Date:** 2026-10-16
- **Status:** Accepted

## Context

When a notebook assay is launched, the portal calls `POST /assays/{id}/run`. That call returns the URL of `assay_<id>/` in the user's JupyterHub workspace, but nothing places the registered notebook or the assay's inputs there. Unless someone copies them in by hand, the folder is empty or missing. After the run, the existing download and upload-workspace endpoints read the results from `assay_<id>/outputs/datasets/`.

Several things constrain the design:

- **The API can't reach the user's files directly.** Each user's files live in a per-user Docker volume. The API container mounts neither those volumes nor the Docker socket.
- **The user's server may not be running.** It may be stopped, or the user may never have logged into JupyterHub. The hub only spawns it when the user opens a URL.
- **The API's hub service token has the admin role.** With it, the API can create users, start servers and read and write any server's contents API. `_download_jupyter_folder` already uses it to read results.
- **Datasets can be large.** Measurement datasets can be up to `MAX_UPLOAD_MB` (default 20 GB).
- **`/run` has a time limit.** Nginx and the portal's API client both cut it off at 600 s.
- **The notebook expects fixed paths.** The example `mri_curation.ipynb` reads `inputs/datasets/*/` and writes `outputs/datasets/`, both relative to its own folder.

## Alternatives Considered

### How the files reach the workspace

#### Option A: the API pushes them through the hub (chosen)
On `/run` the API creates or starts the user's server if needed, then writes the files through the Jupyter contents API.
- Pros:
  - Notebooks need no download code.
  - It reuses the token and authentication that the results download already uses.
  - The workspace is ready when the tab opens.
- Cons:
  - Every byte crosses the API and is base64-encoded on the way.
  - Launch waits for the server to spawn and the files to copy.

#### Option B: the notebook pulls its own data
The API writes only the notebook and a config file. The notebook downloads its inputs with the digitaltwins client.
- Cons: every notebook author must write download code, and a notebook breaks if that code is missing or wrong.

#### Option C: a spawn-time hook in the single-user image
- Cons:
  - User containers would hold MinIO credentials.
  - It runs only at spawn, so launching a second assay on a running server would stage nothing.

### Which input data is staged

#### Option A: a cohort and sample-type subset (chosen)
For each measurement input, stage:
- the files outside `primary/`;
- the `primary/<sub>/<sam>/` folders that the assay's cohort and sample type select (the same selection as script runs);
- `subjects.xlsx`, `samples.xlsx` and `manifest.xlsx`, filtered to match.

Model inputs are staged whole.
- Pros:
  - The assay's configuration decides what the notebook sees.
  - Transfers are smaller.
- Cons: the metadata has to be rewritten.

#### Option B: whole datasets
- Cons:
  - The cohort and sample type would be ignored, so each notebook would have to repeat the selection.
  - A full 20 GB dataset can't be copied within `/run`'s time limit.

### When staging runs

#### Option A: inside `/run`, resumable (chosen)
- Existing files are skipped.
- Each file is written under a temporary name, then renamed into place.

So a file that exists is complete. If the request times out, the user clicks Launch again and the copy continues where it stopped.
- Pros: no job state and no polling.
- Cons: launching a large subset may need more than one click.

#### Option B: a background job with progress polling
- Cons: adds a job state machine to the API and polling to the portal, for sizes we don't expect.

### What happens on re-launch

#### Option A: stage only missing files (chosen)
- Pros: the user's edits to the notebook and any results in `outputs/` survive.
- Cons: if the assay's cohort changes after staging, the old subset stays until the user deletes `inputs/`.

#### Option B: refresh the code and inputs on every launch
- Cons: discards the user's edits to the notebook.

## Decision

Option A in every section.

The staged layout is:

```
assay_<id>/
  <the contents of workflows/<workflow uuid>/code/>
  inputs/datasets/<input name>/
  inputs/models/<input name>/
  outputs/datasets/
```

`<input name>` is the assay input's name without its CWL `#main/` prefix.

Related changes:
- `run_assay` checks `AIRFLOW_ENABLED` only for script assays.
- The portal reads an assay's type as the one tag in `{script, notebook, gui}`, wherever it appears in the tag list, instead of using `tags[0]`.
- Verify on a notebook assay opens the workspace through JupyterHub's `user-redirect`; on script and gui assays it stays disabled.

## Consequences

- Launching a notebook assay can take as long as a server spawn plus the copy. The Launch button shows a spinner meanwhile.
- If a launch times out, launching again finishes the copy.
- `/run` for notebook assays now depends on JupyterHub, MinIO and the workflow dataset's `seek_id` row. A workflow registered only in SEEK, not ingested into the platform, gets a 400 error.
- The staged inputs are a snapshot. If the assay's cohort or sample type changes, the user must delete `inputs/` to stage the new selection.

## Amendments during implementation

- **The temporary name is `<name>.staging`, not `.<name>.staging`.** jupyter_server refuses to save or rename hidden paths unless `allow_hidden` is set, which the single-user image doesn't set.
- **Hidden files are not staged.** For the same reason, files whose path has a segment starting with `.` (such as `.DS_Store`) are left out of the workflow code and of the input datasets.
- **Input folders are named after the assay input, not the dataset.** A workspace prepared by hand before this change may already hold the same dataset under its dataset name, for example `inputs/datasets/<dataset name>/`. Staging then adds a second copy under the input's name. A notebook that expects exactly one dataset in `inputs/datasets/` fails until the user removes the hand-placed copy.
