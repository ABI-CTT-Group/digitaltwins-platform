# Workspace Dataset Platform Upload Feature

The endpoint to upload workflow dataset results from the `airflow-workspace` bucket to the digitaltwins platform database has been successfully implemented.

## What Was Done

**New Endpoint `POST /assays/{assay_id}/workspace/dataset/upload` added in `upload.py`:**
1. **Timestamp Resolution**: Automatically discovers the latest workflow execution under `assay_{assay_id}` in MinIO if a `timestamp` isn't provided.
2. **Category Mapping**: Queries the Postgres database using `querier.get_assay()` to dynamically map the subfolder name (e.g. `converted_dataset`) to its proper output `category` defined in the assay configuration.
3. **Workspace Retrieval**: Downloads the complete timestamp folder from `airflow-workspace` to a secure temporary directory.
4. **Dataset Ingestion**: Iterates through each subfolder in the workspace folder and calls `uploader.upload_dataset()`, seamlessly uploading each dataset to the platform and returning their new `dataset_uuid`s.
5. **Robust Cleanup**: The temporary files and folders are automatically wiped in a `finally` block regardless of whether the upload was successful or failed.

## Next Steps
You can now hit `POST http://localhost:<port>/assays/<id>/workspace/dataset/upload` in Postman or cURL to seamlessly ingest your airflow run results directly into the platform!
