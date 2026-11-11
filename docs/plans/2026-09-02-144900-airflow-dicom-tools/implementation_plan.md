# Update Airflow DAG Tools

The goal is to update the Airflow tool scripts (`tool_dicom_to_nifti.py` and `tool_dicom_to_nrrd.py`) to align with the changes we made to the standalone Python/CWL scripts.

## Proposed Changes

### [MODIFY] [tool_dicom_to_nifti.py](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/tool/tool_dicom_to_nifti.py)
- Import `pydicom` and `dicom2nifti`.
- Replace the `_convert_dicom_to_nifti` stub with the actual conversion logic.
- Dynamically extract the `SeriesDescription` from the DICOM files to generate the NIfTI filename (e.g., `{SanitizedSeriesDescription}.nii.gz`).
- Update the `run()` function so that it uses the dynamically generated filename instead of the hardcoded `breast_mri_rai.nii.gz` when uploading the output to MinIO. The MinIO key will become `<run_id>/outputs/{SanitizedSeriesDescription}.nii.gz`.

### [MODIFY] [tool_dicom_to_nrrd.py](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/tool/tool_dicom_to_nrrd.py)
- Import `SimpleITK`.
- Replace the `_convert_dicom_to_nrrd` stub with the actual conversion logic.
- Dynamically extract the `0008|103e` (Series Description) tag to generate the NRRD filename (e.g., `{SanitizedSeriesDescription}.nrrd`).
- Update the `run()` function so that it uses the dynamically generated filename instead of the hardcoded `image.nrrd` when uploading the output to MinIO. The MinIO key will become `<run_id>/outputs/{SanitizedSeriesDescription}.nrrd`.

## User Review Required

> [!WARNING]
> By making these changes, the Airflow tasks will no longer upload files named exactly `breast_mri_rai.nii.gz` and `image.nrrd` to MinIO. Instead, the MinIO keys will contain the dynamic Series Description (e.g. `test_run/outputs/T1_Axial.nii.gz`). Please confirm if downstream systems are prepared to handle dynamic filenames from the Airflow DAG output, or if we should enforce the hardcoded names for Airflow.

Please click **Proceed** if you approve these changes, or let me know if we should modify the plan.
