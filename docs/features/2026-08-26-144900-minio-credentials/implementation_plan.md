# MinIO Credentials Update (Keycloak Integration)

This plan outlines the changes required to update the default/hardcoded MinIO credentials from `minioadmin` to the new Keycloak credentials (`admin1` / `BXfeeHe5c4694t6xVMuV`) across the platform's workflows and notebooks.

## Open Questions

> [!WARNING]
> **Platform `.env` Configuration**
> Currently, I will only be updating the **Airflow DAGs** and **Jupyter notebooks** as requested. However, `MINIO_ROOT_USER`, `MINIO_SERVER_ACCESS_KEY`, and other environment variables in `.env` and `docker-compose.yml` are still set to `minioadmin`. 
> 
> *Should I also update the platform's `.env` and `docker-compose.yml` files, or are those intentionally left as `minioadmin` for the admin root user while `admin1` is just used for workflow execution?*

## Proposed Changes

### Airflow Workflows (`services/airflow/dags/`)

These DAG files currently default to `"minioadmin"` if the environment variables aren't found. We will update the fallback to `"admin1"` and `"BXfeeHe5c4694t6xVMuV"`.

#### [MODIFY] [workflow_image_conversion.py](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/workflow_image_conversion.py)
- Change `DEFAULT_MINIO_ACCESS_KEY` default from `"minioadmin"` to `"admin1"`
- Change `DEFAULT_MINIO_SECRET_KEY` default from `"minioadmin"` to `"BXfeeHe5c4694t6xVMuV"`

#### [MODIFY] [tool_download_samples.py](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/tool/tool_download_samples.py)
- Update `os.environ.get("MINIO_ACCESS_KEY", "minioadmin")` to default to `"admin1"`
- Update `os.environ.get("MINIO_SECRET_KEY", "minioadmin")` to default to `"BXfeeHe5c4694t6xVMuV"`

#### [MODIFY] [tool_dicom_to_nrrd.py](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/tool/tool_dicom_to_nrrd.py)
- Update `os.environ.get("MINIO_ACCESS_KEY", "minioadmin")` to default to `"admin1"`
- Update `os.environ.get("MINIO_SECRET_KEY", "minioadmin")` to default to `"BXfeeHe5c4694t6xVMuV"`

#### [MODIFY] [tool_dicom_to_nifti.py](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/tool/tool_dicom_to_nifti.py)
- Update `os.environ.get("MINIO_ACCESS_KEY", "minioadmin")` to default to `"admin1"`
- Update `os.environ.get("MINIO_SECRET_KEY", "minioadmin")` to default to `"BXfeeHe5c4694t6xVMuV"`

---

### Local Jupyter Workspace (`my_workspace/pilot-2/`)

These notebooks have hardcoded `"minioadmin"` strings for their S3 connection block.

#### [MODIFY] [clinical_report_curation.ipynb](file:///home/clin864/Projects/digitaltwins-platform/my_workspace/pilot-2/RATA/Assay%201%20-%20Clinical%20Report%20Curation/clinical_report_curation.ipynb)
- Replace `"minioadmin"` with `"admin1"` for `SOURCE_ACCESS_KEY`
- Replace `"minioadmin"` with `"BXfeeHe5c4694t6xVMuV"` for `SOURCE_SECRET_KEY`

#### [MODIFY] [clinical_report_to_fhir.ipynb](file:///home/clin864/Projects/digitaltwins-platform/my_workspace/pilot-2/RATA/Assay%201%20-%20Clinical%20Report%20Curation/scripts/clinical_report_to_fhir.ipynb)
- Replace `"minioadmin"` with `"admin1"` for `SOURCE_ACCESS_KEY` and `MINIO_ACCESS_KEY` fallbacks.
- Replace `"minioadmin"` with `"BXfeeHe5c4694t6xVMuV"` for `SOURCE_SECRET_KEY` and `MINIO_SECRET_KEY` fallbacks.

---

### Live Jupyter Container (`jupyter-admin1`)

We will execute a script inside the running container to update the active workspace files.

#### [MODIFY] `./work/assay_31/clinical_report_curation.ipynb` (inside `jupyter-admin1`)
- Replace `"minioadmin"` with `"admin1"` for `SOURCE_ACCESS_KEY`
- Replace `"minioadmin"` with `"BXfeeHe5c4694t6xVMuV"` for `SOURCE_SECRET_KEY`

## Verification Plan
1. Ensure the Python scripts correctly replace the values in the `.ipynb` files without breaking JSON formatting.
2. Verify that running `clinical_report_curation.ipynb` inside the `jupyter-admin1` container succeeds or progresses past the `SignatureDoesNotMatch` error.
