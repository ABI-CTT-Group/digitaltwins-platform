# Preprocessor Migration Walkthrough

The Airflow preprocessor logic has been successfully migrated to the API service! The `run_assay` endpoint now natively orchestrates the workflow setup, significantly streamlining the process and reducing dependency on Airflow for non-workflow tasks.

## What Changed

### API Service (`workflow.py`)
- **Direct Configuration Fetching**: The API now calls `querier.get_assay(..., get_configs=True)` internally rather than relying on Airflow to fetch the configurations.
- **Sample Discovery**: Replaced `discover_subjects` with `_discover_samples`. It directly queries postgres to find all unique `(subject_id, sample_id)` pairs for the assay inputs.
- **SDS Dataset Generation**: Integrated `sparc-me` directly into the API. When an assay runs, it locally creates an SDS structure, populates the `dataset_description.xlsx`, `subjects.xlsx`, `samples.xlsx`, and pre-populates `manifest.xlsx` based on the expected outputs.
- **MinIO Uploading**: The generated SDS structure is uploaded to the `airflow-workspace` bucket under the `assay_{assay_id}/{dataset_name}` path.
- **Empty Directories for SPARC Structure**: The API creates explicit empty 0-byte objects in MinIO to ensure that all standard SPARC folders (`primary/`, `derivative/`, `source/`, `code/`, `docs/`, `protocol/`, and `primary/sub-{id}/sam-{id}/`) exist.
- **Per-Sample DAG Triggering**: Instead of triggering a single DAG that discovers subjects and triggers sub-DAGs, the API now iterates over the discovered samples and triggers a workflow DAG for **each sample** directly.

### Airflow
- **Deleted Preprocessor DAG**: `preprocessor.py` was removed as its responsibilities are now handled by the API.
- **Updated Workflow DAGs**: Modified `workflow_image_conversion.py` to extract `output_prefix` and `sample_id` from the DAG run configuration.
- **Tool Updates**: Verified that `tool_dicom_to_nifti.py` and `tool_dicom_to_nrrd.py` already accepted `output_key_prefix`. Wired them up in the workflow DAG to use the new output prefix, ensuring files are written to the correct SDS path (e.g., `{dataset_name}/primary/sub-{id}/sam-{id}/image.nrrd`).

## Verification

The API syntax has been verified in the local virtual environment. 

> [!TIP]
> **Next Steps**
> You can rebuild the API Docker container to ensure `sparc-me` is fully installed and test the `POST /assays/1/run` endpoint to verify the full end-to-end flow!
