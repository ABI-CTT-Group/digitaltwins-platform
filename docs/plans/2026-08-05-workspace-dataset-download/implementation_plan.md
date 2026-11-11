# Add Workspace Dataset Download Endpoint

This plan outlines the steps to add an endpoint in the `digitaltwins-api` to download assay workflow results/datasets directly from the workspace bucket (`airflow-workspace`).

## User Review Required

- **Endpoint Path**: We will define `GET /assays/{assay_id}/workspace/dataset/download` in `app/routers/assay.py`.
- **Dynamic Dataset Name**: The dataset folder will be dynamically derived from the assay configs (e.g. `outputs[0].get("dataset_name")`), defaulting to `"output_dataset"` to match how it's created.
- **Timestamp**: The endpoint will support an optional `timestamp` query parameter. If omitted, it will automatically query the `airflow-workspace` bucket for folders under `assay_{assay_id}/` and pick the one with the latest timestamp.

## Proposed Changes

### MinIO Downloader

#### [MODIFY] [downloader.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/src/digitaltwins/minio/downloader.py)
We need to add two new methods to the `Downloader` class to support this specific workspace download:
1. `get_latest_timestamp_folder(self, bucket_name: str, prefix: str) -> str`: Uses the MinIO/S3 `list_objects_v2` API with `Delimiter="/"` to find all folders under a given prefix (e.g., `assay_1/`). It will sort the folder names (which are timestamps like `20260805_131413`) lexicographically and return the latest one.
2. `download_folder(self, bucket_name: str, prefix: str, save_dir: str) -> int`: Downloads all objects matching the given prefix from the specified bucket into the local `save_dir`.

### API Router

#### [MODIFY] [assay.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/assay.py)
1. Add a new endpoint `GET /assays/{assay_id}/workspace/dataset/download`.
2. The endpoint will:
   - Accept an optional `timestamp` query parameter.
   - Use `querier.get_assay()` to fetch the assay configs and derive the dataset name.
   - Use the `MinioDownloader` directly (or via `get_downloader()`) to resolve the latest timestamp (if `timestamp` is not provided).
   - Create a temporary directory.
   - Use the `MinioDownloader` to download the specific folder (`assay_{assay_id}/{timestamp}/{dataset_name}/`) from `airflow-workspace`.
   - Zip the downloaded dataset.
   - Return a `StreamingResponse` with the ZIP file and clean up the temporary directory afterwards (similar to the existing `download_dataset` endpoint).

## Verification Plan

### Automated Tests
- No automated tests are explicitly required for this new endpoint as part of this plan, but we will ensure it follows FastAPI best practices and error handling.

### Manual Verification
- Start the API locally.
- Use an HTTP client (e.g., cURL, Postman) to call `GET http://localhost:<port>/assays/1/workspace/dataset/download`.
- Verify a ZIP file is downloaded containing the dataset from the `airflow-workspace` bucket.
- Verify that providing a `timestamp` query parameter downloads that specific historical run.
