# Walkthrough: MinIO Credentials Update (Keycloak Integration)

## Overview
We've updated the MinIO configuration logic to support the new Keycloak user integration. The credentials have been successfully updated from `minioadmin` to `admin1` / `BXfeeHe5c4694t6xVMuV` across Airflow DAGs and Jupyter workspaces.

### What Changed?
1. **Airflow DAGs**: 
   - `workflow_image_conversion.py`, `tool_download_samples.py`, `tool_dicom_to_nrrd.py`, and `tool_dicom_to_nifti.py` now all default to retrieving the `admin1` credentials via `os.environ.get()` instead of `minioadmin`.
2. **Local Jupyter Workspace**: 
   - The string `"minioadmin"` was updated for all `SOURCE_ACCESS_KEY`, `SOURCE_SECRET_KEY`, `MINIO_ACCESS_KEY`, and `MINIO_SECRET_KEY` variables inside `clinical_report_curation.ipynb` and `clinical_report_to_fhir.ipynb`.
3. **Live Jupyter Container (`jupyter-admin1`)**:
   - We ran a Python script directly inside the active JupyterHub container for `admin1` to replace the S3 connection string inside the loaded `clinical_report_curation.ipynb` file.

> [!TIP]
> Try re-running the cell block that failed in your live Jupyter notebook. The connection to MinIO using `boto3.client("s3")` should now authenticate cleanly via Keycloak!
