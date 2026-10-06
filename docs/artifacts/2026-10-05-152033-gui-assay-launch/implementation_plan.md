# Plan: Launch a GUI assay with its configured inputs preloaded

## Context

In the study dashboard (e.g. `/study-dashboard?trail=7,12,10,11`), clicking **Launch** on an assay tagged `gui` only shows the toast "GUI based workflow launch is under development":
- the portal branch is at `services/portal/backend/app/router/dashboard.py:465-504`;
- the API's `POST /assays/{id}/run` returns 400 for anything that isn't `script` or `notebook`.

The goal is that Launch opens the assay's GUI tool, for example VolView on Test Assay 3 (SEEK 43), in a **new tab**. The tool should already have the assay's configured input data loaded: the input dataset, its sample type, and the cohort subjects.

**Decisions from the interview**

| Topic | Decision |
|---|---|
| Where the tool opens | A new browser tab at `/tool-view?assay=<seekId>`. The page describes itself, so a refresh works. |
| How data reaches the tool | A generic `assayContext` is `provide()`d to the plugin. VolView also gets `?urls=[..]&names=[..]`, so it works without changes. |
| How files are served | Through an authenticated portal proxy that streams from the API, which reads MinIO. MinIO stays private. |
| Which files are loaded | Only the configured `sample_type` for the cohort subjects, using the same `_discover_samples` logic as script runs. |
| How the tool authenticates file fetches | With the user's Keycloak token. It is injected client-side only (via `history.replaceState`) as VolView's `?token=`, which VolView strips straight away. Generic plugins call `assayContext.getAccessToken()`. |
| Assay workflow has no portal-built GUI tool | Launch fails with a clear toast. There is no fallback, per ADR 2026-10-02. |
| Outputs / Submit for gui assays | Out of scope; this will be a follow-up. |

**Facts verified**
- The portal `workflow_builds` table has `seek_id=95` → `workflow_volview` (gui, completed, expose `workflowvolview_7c361058`, bundle at `tool-builds/workflowvolview_7c361058/primary`).
- Assay 43 is currently linked to SEEK workflow **91**, which has no portal build. For the e2e test it will be **relinked to 95** through the configure dialog.
- Sample files are stored at `<bucket>/<dataset_uuid>/primary/<subject_id>/<sample_id>/…`. The bucket is the dataset category. The DAGs find the bucket by scanning for the prefix (`services/airflow/dags/tool/tool_download_samples.py:49-60`).
- VolView reads `urls`, `names` and `token` from `window.location` when it is set up (`tests/data/tool_volview/code/src/components/App.vue:159-171`, `utils/token.ts`). `normalizeUrlParams` (`utils/urlParams.ts`) splits a bracketed `[a,b]` value on commas, and accepts relative URLs such as `/api/...`. `$fetch` (`utils/fetch.ts:6-38`) adds the `Authorization` header set from `?token=` to every file request.
- **Comma caveat.** vtk.js `extractURLParameters` percent-decodes each value *before* VolView splits on `,`, so encoding a comma as `%2C` does not help. The VolView param builder must skip files whose key contains `,`, `[` or `]` and log a warning. The generic `assayContext` is unaffected. `&` and `=` are safe, because vtk splits on them before decoding.
- URL size: one proxied URL is about 120 characters, so even a 1000-slice series stays far below Chrome's 2 MB limit for `replaceState`.
- `_discover_samples` dedups on `(subject_id, sample_id)` **across inputs**, so two inputs that share sample ids would lose files. VolView has one input, so this does not matter yet. The ADR records it as an inherited limitation.

## Design

```
Dashboard Launch ──GET /api/dashboard/assay-launch──► portal: tag=="gui" → resolve tool (validate) → {type:"gui", data:"/tool-view?assay=43"}
      └─ window.open(new tab)
/tool-view?assay=43 ──GET /api/dashboard/assay-gui-context?seek_id=43──► portal:
      ├─ API GET /assays/43/gui-inputs            (configs → _discover_samples → list MinIO keys)
      └─ portal DB WorkflowBuild.seek_id == workflow_seek_id → served_workflow_build → path/expose
   ◄─ {tool:{name,path,expose}, assayId, inputs:[{name, datasetUuid, sampleType, files:[{name, subjectId, sampleId, url}]}]}
   history.replaceState(?assay=43&urls=[…]&names=[…]&token=<jwt>)   (client-side only)
   mount plugin with provide('assayContext', {...ctx, getAccessToken})
VolView fetch(url, Bearer) ──► portal GET /api/dashboard/assays/43/input-files/<bucket>/<key…>
                              ──► API GET /assays/43/input-files/<bucket>/<key…> (validates key ⊂ an input dataset) ──► MinIO stream
```

### 1. API: digitaltwins-api (`services/api/app/routers/assays.py`)

- **`GET /assays/{assay_id}/gui-inputs`**:
  - Reuses `_fetch_assay_configs` and `_discover_samples` (`:125`, `:162`). Models are skipped, as they already are.
  - For each sample, finds the bucket that holds `<dataset_uuid>/` and lists the objects under `<dataset_uuid>/primary/<subject_id>/<sample_id>/`.
  - Returns `{workflow_seek_id, inputs:[{name, dataset_uuid, sample_type, files:[{bucket, key, name, subject_id, sample_id}]}]}`.
  - Does **not** depend on `AIRFLOW_ENABLED`, unlike `run_assay`.
  - Returns 400 with the `ValueError` message when there is no config, the cohort has no match, or no samples are found.
- **`GET /assays/{assay_id}/input-files/{bucket}/{key:path}`**:
  - Loads the assay configs as the calling user.
  - Returns 403 unless `key` starts with `<dataset_uuid>/primary/` for one of the assay's non-model inputs, and has no `..` segment.
  - Streams the object from MinIO (`StreamingResponse`, content type guessed from the extension). Returns 404 if the object is missing.
- Bucket discovery and object listing use the existing `digitaltwins.minio` S3 client (the `Downloader`/`Uploader` already imported in `assays.py`). If that client lacks the listing or bucket-finding behaviour, add a small helper on it, modelled on `_find_source_bucket` and `_download_prefix` in the DAG tool. Do not duplicate it.

### 2. Portal backend (`services/portal/backend/app/router/dashboard.py`)

- Import `get_db` from `app.database.database` (`:102`); `dashboard.py` does not use it yet.
- **`/assay-launch`**: add a `gui` branch. It calls a helper `_resolve_gui_tool(db, workflow_seek_id)`:
  - `WorkflowBuild.seek_id == str(id)` → its `Workflow` (must be `workflow_type == "gui"`) → `served_workflow_build` + `workflow_bundle_path` (`app/utils/workflow_tool_utils.py:236-255`), the same resolution `/api/tools/metadata` uses (`workflow_tool_plugin.py:856-880`).
  - On success it returns `{"type": "gui", "data": "/tool-view?assay=<seek_id>"}`.
  - If nothing resolves, it returns `{"message": "This assay's workflow has no launchable GUI tool. Build and approve it in the portal, or link the assay to a workflow that has one."}`, which the existing toast path shows.
  - Every other tag keeps its current behaviour.
- **`GET /assay-gui-context?seek_id=`**:
  - Calls `/assays/{id}?get_configs=True` (for `workflow_seek_id`), then `_resolve_gui_tool`, then API `/assays/{id}/gui-inputs`.
  - Maps each file to `url = /api/dashboard/assays/{seek_id}/input-files/{bucket}/{key}`, URL-encoding each path segment.
  - Error handling follows the `HTTPStatusError`/`RequestError` pattern already used in the file.
- **`GET /assays/{seek_id}/input-files/{bucket}/{key:path}`**: streams from the API with `client.get_stream`, in the same shape as `/assay-download` (`:610-633`). It passes `Content-Type` and `Content-Length` through.

### 3. Portal frontend (`services/portal/frontend/src`)

- `models/types.ts`: add `AssayGuiContext` and the `"gui"` launch type.
- `bootstrap/dashboard_api.ts`: add `useDashboardGetAssayGuiContext(seekId)`.
- `composables/useAssayActions.ts` `launch()`: on `res.type === "gui"`, call `window.open(res.data, "_blank")`, matching the notebook path. Do not set Monitor; it stays limited to script assays.
- `views/tool-plugin/tool-plugin-view.vue`:
  - **With `route.query.assay`**: fetch the GUI context and show a loading state, or an error message on failure. Then build the VolView params and replace the address with `history.replaceState`, keeping `assay`. Then render `RemoteComponentApp` with the context's `path`/`expose` and a `context` prop.
    - VolView params are `urls=[u1,u2]`, `names=[n1,n2]` and `token=<getAccessToken()>`. The builder lives in a small pure module, `src/utils/volviewParams.ts`, so it can be unit-tested. It skips files whose key contains `,`, `[` or `]` (see the comma caveat above).
    - `replaceState` must run before the mount, because VolView reads `window.location` during setup.
  - **Without it**: keep the current behaviour, which reads the persisted `remoteApp` store.
  - The exit button calls `window.close()` when the page was opened for an assay, because a new tab has no history to go back to.
- `components/RemoteComponentApp.vue`: add an optional prop `context?: Record<string, unknown>`. If it is set, call `pluginApp.provide('assayContext', context)` before `mount`, and update the comment at `:25-27`. The context contains `{assayId, tool, inputs, getAccessToken}`, where `getAccessToken` is the portal's existing token getter from `bootstrap/http.ts`.

### 4. Docs (per AGENTS.md)

- **ADR** `docs/decisions/2026-10-05-gui-assay-launch-input-handoff.md`. It records:
  - serving files through an authenticated portal proxy, instead of MinIO presigned URLs;
  - passing the user's token client-side through `?token=`, instead of signed file tokens;
  - the `assayContext` provide contract, plus the VolView URL convention;
  - one URL per file, instead of one zip per sample (VolView can unzip archives, which would avoid the comma caveat and shorten the URL, but it would cost on-the-fly zipping and per-file progress);
  - the comma caveat and the cross-input dedup limitation.
- **Artifacts** go in `docs/artifacts/2026-10-05-<HHMMSS>-gui-assay-launch/` (`implementation_plan.md`, `task.md`, `walkthrough.md`). Sync them after every edit, and check them for secrets before staging. They are committed in the same branch as the code.

## TDD order

1. **API tests** in `services/api/tests/test_assay_gui_launch.py`, following `test_assay_api.py`, with the querier and S3 mocked:
   - `gui-inputs` filters by cohort and sample type and lists keys;
   - `gui-inputs` returns 400 when there is no config;
   - `input-files` returns 403 for a key outside the input datasets, for `..`, and for a model input's dataset;
   - `input-files` streams the bytes on success.
   Then implement until they pass.
2. **Portal tests** in `services/portal/backend/tests/test_dashboard_assay_gui_launch.py`, following `test_dashboard_assay_download.py`:
   - a gui launch returns `{type:"gui", data:"/tool-view?assay=43"}`;
   - a gui launch with no build returns the message;
   - script and notebook launches are unchanged;
   - the context maps files to proxy URLs and resolves path/expose for the approved build first, then the latest one;
   - the file proxy streams and passes 403/404 through.
   Then implement.
3. **Frontend** (vitest, `npm test` in `services/portal/frontend`):
   - extend `src/composables/__tests__/useAssayActions.spec.ts`: a `gui` launch calls `window.open("/tool-view?assay=43", "_blank")` and does not set Monitor;
   - new `src/utils/__tests__/volviewParams.spec.ts`: bracketed lists, encoded path segments, `assay` kept, files with `,`/`[`/`]` skipped with a warning.

Portal tests must **not** run inside the live container: the suite runs `drop_all()` against the live Postgres when `PORTAL_DB_HOST` is set. Run them locally or in a throwaway environment.

## Verification (end-to-end)

1. Rebuild and restart the affected services: `docker compose up -d --build api portal-backend portal-frontend`. Confirm the exact service names from `docker-compose.yml` first.
2. In the dashboard, open Test Assay 3 (SEEK 43), then Configure. Pick **workflow_volview (95)**, a dataset with DICOM `measurements`, the sample type and a cohort (e.g. `1`), then Save. Launch is now enabled.
3. Click Launch. A new tab should open at `/tool-view?assay=43` and VolView should load the cohort's DICOM series. In DevTools, check that the file requests return 200 through `/api/dashboard/assays/43/input-files/...` and that the address bar no longer shows `token=`.
4. Negative checks:
   - an assay linked to workflow 91 shows the "no launchable GUI tool" toast;
   - a cohort with no samples shows the error in the tool-view tab;
   - `curl` of an `input-files` URL for another dataset's key returns 403;
   - Launch on script and notebook assays behaves as before.
5. Tool Hub launch (`/tool-view` with no query) still works.
