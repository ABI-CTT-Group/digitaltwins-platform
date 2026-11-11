# SDS Metadata and Folder Structure Plan

This plan addresses updating `samples.xlsx` with the workflow runs, ensuring all SPARC folders exist in the MinIO bucket, and determining the best way to populate `manifest.xlsx`.

## Proposed Changes

### 1. Fixing Empty Directories in MinIO (All SPARC Folders)

Currently, `sparc-me` generates the full skeleton locally (`primary/`, `derivative/`, `source/`, `code/`, `docs/`, `protocol/`), but `digitaltwins.minio.uploader.Uploader` ignores empty directories when uploading. In S3/MinIO, a folder only exists if there is an object inside it (or a 0-byte object with a trailing slash).
- **Change**: In `workflow.py`, after uploading the files, we will use `uploader.s3_client.put_object` to explicitly create empty 0-byte folder markers in MinIO for **all standard SPARC folders** (e.g., `primary/`, `derivative/`, `source/`, `code/`, `docs/`, `protocol/`), as well as the specific `primary/sub-{id}/sam-{id}/` folders.

### 2. Updating `samples.xlsx`

The `run_assay` API endpoint knows exactly which samples are going to be processed.
- **Change**: In `workflow.py`, alongside updating `subjects.xlsx`, we will fetch the `samples` metadata file via `sparc-me` (`dataset.get_metadata("samples")`) and populate it with the discovered samples (setting `subject id`, `sample id`, and `sample type`).

### 3. Registering Output Files in `manifest.xlsx`

Since the individual Airflow sample DAG runs execute asynchronously and in parallel, having them all try to download, modify, and re-upload the same `manifest.xlsx` file to MinIO will cause race conditions and data loss. Therefore, we must choose a safer approach to update the manifest.

> [!WARNING]
> **User Review Required: Choose the best approach for `manifest.xlsx`**
> 
> **Option A (API Pre-population - Recommended for simplicity):**
> We pre-populate `manifest.xlsx` in the API during `run_assay`. Since the database `assay_output` table only defines abstract output names (like `nifti_output`), the API would need to predict the exact filenames the tools will generate (e.g., `breast_mri_rai.nii.gz` and `image.nrrd`).
> *Pros*: Synchronous, easy to implement, no race conditions.
> *Cons*: Hardcodes expected tool output filenames in the API, which reduces flexibility if a tool changes its output filename.
> 
> **Option D (Post-Processing "Finalize" DAG):**
> The API triggers the individual sample workflows, and then triggers a final `finalize_dataset` DAG. This DAG waits for all sample DAGs to finish, then scans the MinIO dataset directory to dynamically discover all generated files, builds `manifest.xlsx` using `sparc-me`, and uploads it.
> *Pros*: 100% accurate file tracking, no hardcoding of filenames in the API.
> *Cons*: Requires creating a new Airflow DAG and a mechanism to wait for dynamic DAG runs.
> 
> **Option E (Deferred/On-Demand Generation):**
> We don't generate the manifest immediately. Instead, we add a new API endpoint `POST /assays/{assay_id}/finalize_dataset` that the portal/user calls *after* they see the workflows are completed. This endpoint scans the MinIO bucket and uses `sparc-me` to generate and upload `manifest.xlsx`.
> *Pros*: Simple, accurate, avoids Airflow synchronization complexity.
> *Cons*: Requires a manual trigger or separate scheduled job.

Please review these options and let me know which one you prefer, and I will begin execution!
