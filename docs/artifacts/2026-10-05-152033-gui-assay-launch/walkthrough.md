# Walkthrough: launching a gui assay with its inputs preloaded

Date: 2026-10-05. Branch: `dev_chinchien`. ADR: `docs/decisions/2026-10-05-gui-assay-launch-input-handoff.md`.

## What changed

| Layer | Change |
|---|---|
| API `services/api/app/routers/assays.py` | `GET /assays/{id}/gui-inputs` (reuses `_fetch_assay_configs` + `_discover_samples`, lists each sample's MinIO objects) and `GET /assays/{id}/input-files/{bucket}/{key}` (403 unless the key is under a non-model input's `<dataset_uuid>/primary/`, no `..`; streams the object). |
| API `app/routers/dependencies.py` | `get_minio_downloader()`: the MinIO object store itself. The existing `get_downloader()` returns the *core* dataset `Downloader`, which wraps MinIO/iRODS and has no object-level methods — the first e2e run failed on exactly that. |
| API `src/digitaltwins/minio/downloader.py` | `find_bucket(dataset_uuid)`, `list_objects(bucket, prefix)`, `open_object(bucket, key)`. |
| Portal `app/router/dashboard.py` | `/assay-launch` `gui` branch → `{type: "gui", data: "/tool-view?assay=<id>"}` or the "no launchable GUI tool" message; `/assay-gui-context` (resolves the bundle through `workflow_builds.seek_id` + `served_workflow_build`, maps files to proxy URLs, snake_case); `/assays/{id}/input-files/{bucket}/{key}` streaming proxy. |
| Frontend | `launch()` opens `res.data` in a new tab for `gui`; `tool-plugin-view.vue` loads the context when `?assay=` is present, sets VolView's `urls`/`names`/`token` query with `history.replaceState` before the plugin mounts, strips it back to `?assay=` after; `RemoteComponentApp` `provide('assayContext', …)` and emits `mounted`; `utils/volviewParams.ts` builds the query (skips names with `,` `[` `]`); new `AssayGuiContext` types and `useDashboardGetAssayGuiContext`. |

## Tests (all written first, watched fail, then made green)

| Suite | How it was run | Result |
|---|---|---|
| API `tests/test_assay_gui_launch.py` (7), `tests/test_minio_downloader_objects.py` (4, live MinIO) | throwaway `digitaltwins-platform-digitaltwins-api` container, source bind-mounted, on the compose network | 11 passed |
| API full suite | same | 202 passed, 145 skipped, 6 failed + 1 error — all pre-existing harness issues (`test_delete_dataset_api`, `test_*_workspace_dataset_api`, `test_upload_dataset_api`: stdin read under capture, missing `bucket_name` fixture, `validate_credentials` overridden with `True`) |
| Portal `tests/test_dashboard_assay_gui_launch.py` (9) | throwaway `digitaltwins-platform-portal-backend` container, source at `/src`, **no `PORTAL_DB_HOST`** | 9 passed |
| Portal full suite | same | 213 passed, 9 skipped |
| Frontend `volviewParams.spec.ts` (4), `useAssayActions.spec.ts` launch (1) + full vitest | `node:20` container (host Node 18 lacks `util.styleText`) | 78 passed; `vue-tsc --noEmit` clean for the changed files |

## Rebuild

`docker compose up -d --build digitaltwins-api portal-backend portal-frontend` — all three came back healthy (the API was rebuilt a second time after the `get_minio_downloader` fix).

## End-to-end (curl, as `admin1`, token never written to disk outside the session scratchpad)

Assay 43 ("Test Assay 3: image visualisation") was already linked to SEEK workflow 95 (`workflow_volview`), input `test_converted` / sample type `nifti`, cohort `1`.

| Step | Result |
|---|---|
| `GET /api/dashboard/assay-launch?seek_id=43` | `{"type":"gui","data":"/tool-view?assay=43"}` |
| `GET /api/dashboard/assay-gui-context?seek_id=43` | tool `tool_volview`, path `/tools/718cb9b2-…/primary/my-app.umd.js?v=…` (the approved build), expose `workflowvolview_7c361058`; input "Input DICOM file" → 1 file `sub-1/sam-1/image.nii.gz` |
| `GET` that file URL with the token | 200, `Content-Length: 41418422`, body is gzip (41,418,422 bytes received) |
| same URL, no token | 401 |
| key under another dataset / key with `%2e%2e` | 403 / 403 |
| the bundle path | 200, 2,095,770 bytes |
| `assay-launch?seek_id=42` (script) | unchanged `{"type":"airflow", …workflow_89}` — **note:** this check triggered a real Airflow run of assay 42; launch is not idempotent, so use the unit test for this regression check next time |

**Not verified here:** the browser step — clicking Launch, VolView mounting in the new tab and loading the NIfTI. To check: dashboard → trail `7,12,10,11` → Test Assay 3 → Launch. Expect a new tab at `/tool-view?assay=43`, a short "Loading the assay's inputs…" state, then VolView with `image.nii.gz`; DevTools → Network shows the `input-files/...` request at 200 and the address bar ends up as `?assay=43` (no `token=`).

## Browser test and the fix it forced

First browser run: VolView mounted in the new tab with the right `urls=` but showed "Some file failed to load"; portal logs showed the file request answered **401** (no `Authorization` header). Root cause, from the VolView source: its `?token=` param only sets a header on its legacy `$fetch`/DICOMweb client, while `urls=` downloads go through `openUriStream` → `CachedStreamFetcher` → a request pool built on the browser's plain `fetch`. A plain same-origin fetch sends cookies but no custom header, so:

- `src/utils/assayFileCookie.ts` sets `dt_assay_file_token` scoped to `/api/dashboard/assays/<id>/input-files` (max-age 300, samesite=strict, secure on https) before the plugin mounts; cleared on unmount.
- Portal `get_input_file_token`: `Authorization` header first, else that cookie, else 401; the file proxy now depends on `get_input_file_client`.
- `buildVolViewQuery` no longer emits `token`.
- Tests: portal +3 (header wins, cookie fallback, 401), frontend +3 (`assayFileCookie.spec.ts`), VolView spec asserts no `token`.

## Known limits (see ADR)

- A file whose name contains `,`, `[` or `]` is skipped for the VolView query (console warning); `assayContext` still lists it.
- `_discover_samples` dedups on `(subject_id, sample_id)` across inputs.
- Outputs / Submit for gui assays are a follow-up.
