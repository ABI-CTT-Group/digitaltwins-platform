# Assay Workspace Download — Implementation Plan

## Overview

Wire up the **Download** button in the portal's Study Dashboard to trigger a ZIP download of that assay's workspace files. The download path branches on assay type:

- **Airflow/script assays** → MinIO `airflow-workspace` bucket under `assay_{id}/`
- **Notebook/Jupyter assays** → JupyterHub API at `assay_{id}/outputs/datasets/`

The existing `GET /assays/{assay_id}/workspace/dataset/download` endpoint only handles the airflow case today. It must be extended to also handle the Jupyter case by inspecting the assay's `notebook` tag, then routing to the appropriate storage backend. All changes flow from the digitaltwins-api → portal backend → portal frontend.

---

## Data Flow

```
Browser (Download click)
  → [GET] /api/dashboard/assay-download?seek_id={seekId}    (portal backend)
      → [GET] /assays/{seekId}?get_configs=true              (digitaltwins-api: resolve assay type)
      → [GET] /assays/{seekId}/workspace/dataset/download   (digitaltwins-api: stream ZIP)
          → MinIO (airflow) OR JupyterHub API (notebook)
  ← StreamingResponse (application/zip)
← Browser saves file
```

---

## Proposed Changes

### 1. digitaltwins-api — `assays.py`

#### [MODIFY] [assays.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/assays.py)

**Current state:** `download_workspace_dataset` (line 531) only handles the airflow case — it unconditionally creates a `MinioDownloader`, resolves a timestamp folder, and streams a ZIP.

**Changes:**
- Add a `querier: Querier = Depends(get_querier)` dependency so we can fetch assay tags.
- At the start of the function, call `querier.get_assay(assay_id, get_configs=False)` to read `tags`.
- Branch on `"notebook" in tags`:
  - **Notebook branch:** call the existing `_download_jupyter_folder(username, remote_path, local_dir)` helper with `remote_path = f"assay_{assay_id}/outputs/datasets"` and username from `credentials`. Then ZIP the result and stream it. Filename: `assay_{assay_id}_jupyter.zip`.
  - **Airflow branch:** existing logic unchanged.
- Add `credentials: dict = Depends(validate_credentials)` to the function signature (needed for the Jupyter username). The existing `_valid: bool` dep is replaced by this richer one.

> [!IMPORTANT]
> `_download_jupyter_folder` uses `JUPYTERHUB_INTERNAL_URL` + `/user/{username}/api/contents/{path}` — this already works for the upload flow and is consistent.

---

### 2. Portal backend — `dashboard.py`

#### [MODIFY] [dashboard.py](file:///home/clin864/Projects/digitaltwins-platform/services/portal/DigitalTWINS-Portal/backend/app/router/dashboard.py)

**Changes:**
- Add a new `get_stream` method to `DigitalTWINSAPIClient` that performs a streaming GET with a large timeout (no `response.raise_for_status()` before reading — we stream the response body).
- Add a new route `GET /api/dashboard/assay-download` that:
  1. Calls `client.get_stream(f"/assays/{seek_id}/workspace/dataset/download")`.
  2. Forwards the binary response as a FastAPI `StreamingResponse` with `media_type="application/zip"` and the upstream `Content-Disposition` header forwarded.

#### [MODIFY] [digitaltwins_api.py](file:///home/clin864/Projects/digitaltwins-platform/services/portal/DigitalTWINS-Portal/backend/app/client/digitaltwins_api.py)

**Changes:**
- Add `async def get_stream(self, endpoint, params)` that uses `self.client.stream(...)` context manager (httpx streaming) with a generous timeout (e.g. `httpx.Timeout(300.0)`). This returns an async generator of bytes chunks.

> [!IMPORTANT]
> The existing 15s timeout is far too short for a ZIP download of a large dataset. The streaming client method needs a dedicated long timeout.

---

### 3. Portal frontend

#### [MODIFY] [dashboard_api.ts](file:///home/clin864/Projects/digitaltwins-platform/services/portal/DigitalTWINS-Portal/frontend/src/bootstrap/dashboard_api.ts)

Add:
```ts
export async function useDashboardDownloadAssayWorkspace(seekId: string): Promise<Blob> {
  return http.getBlob<Blob>("/dashboard/assay-download", { seekId });
}
```

#### [MODIFY] [useAssayActions.ts](file:///home/clin864/Projects/digitaltwins-platform/services/portal/DigitalTWINS-Portal/frontend/src/composables/useAssayActions.ts)

Replace the stub `download` function (currently just shows a toast):
- Call `useDashboardDownloadAssayWorkspace(seekId)`.
- On success: create a temporary `<a>` element with `URL.createObjectURL(blob)` and `.click()` it to trigger browser save. Revoke the URL after.
- Show a `toast.info("Preparing download…")` while the request is in flight and `toast.success("Download ready.")` on completion.
- On error: `toast.error(...)`.
- Set/clear `downloadZipProgressValue` (0 → 100) so the existing `DownloadSheet` dialog keeps working.

> [!NOTE]
> The `downloadDialog` ref opens the progress dialog. We set it to `true` at start, update progress value to `100` on completion (matching existing dialog logic in `DownloadSheet.vue`).

---

### 4. Tests

#### [MODIFY] [test_download_workspace_dataset_api.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/tests/test_download_workspace_dataset_api.py)

Current test covers airflow flow only. Add:
- `test_download_workspace_dataset_airflow` — rename/keep existing test, patch `querier.get_assay` to return `tags: ["script"]`.
- `test_download_workspace_dataset_jupyter` — patch `querier.get_assay` to return `tags: ["notebook"]`, patch `_download_jupyter_folder` to create dummy files, assert 200 + zip response + correct filename.

#### [NEW] `test_dashboard_assay_download.py` in portal backend tests

- Test `GET /api/dashboard/assay-download?seek_id=38` with a mocked `DigitalTWINSAPIClient.get_stream` that yields ZIP bytes — assert `200`, `application/zip`, `Content-Disposition` forwarded.

---

## Decisions

- **Jupyter username**: Use `credentials["username"]` from the authenticated Keycloak JWT — consistent with the existing `upload_workspace_datasets` flow.
- **`DownloadSheet` dialog UX**: The existing dialog shows 0% or 100% only. We jump 0→100 when the blob resolves. No changes to `DownloadSheet.vue` needed.

---

## Verification Plan

### Automated Tests
```bash
# digitaltwins-api tests
cd services/api/digitaltwins-api
pytest tests/test_download_workspace_dataset_api.py -v

# portal backend tests
cd services/portal/DigitalTWINS-Portal/backend
pytest tests/test_dashboard_assay_download.py -v
```

### Manual Verification
1. Open `http://localhost/study-dashboard?trail=5,11,8,9`
2. Click **Download** on an airflow assay (assay_id: 38) → ZIP file saves as `assay_38_{timestamp}.zip`
3. Click **Download** on a notebook assay (assay_id: 32) → ZIP file saves as `assay_32_jupyter.zip`
4. Verify the progress dialog opens and closes (DownloadSheet)
5. Verify error toast appears if the workspace has no files (404 from API)
