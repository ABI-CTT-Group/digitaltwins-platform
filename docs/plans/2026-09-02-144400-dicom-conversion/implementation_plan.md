# Complete DICOM to NIfTI and NRRD Conversion Scripts

The goal is to implement the actual conversion logic for `dicom_to_nifti.py` and `dicom_to_nrrd.py`, replacing the simulated mock logic. Based on our discussion, we will:
1. Use `dicom2nifti` for NIfTI conversion.
2. Use `SimpleITK` for NRRD conversion.
3. Dynamically install these dependencies within the CWL step using `InitialWorkDirRequirement`.
4. Derive the output filenames dynamically from the DICOM metadata (specifically, the `SeriesDescription`).

## User Review Required

Please review the proposed changes below. If you approve, click "Proceed" and I will implement the code.

## Open Questions

None currently. We resolved the core design questions during the interactive `/grill-me` session.

## Proposed Changes

### Assay 3 - Image conversion

#### [MODIFY] [dicom_to_nifti.py](file:///home/clin864/Projects/digitaltwins-platform/my_workspace/pilot-2/Breast/Assay%203%20-%20Image%20conversion/dicom_to_nifti.py)
- Import `pydicom` and `dicom2nifti`.
- Parse the DICOM directory to find a `SeriesDescription` using `pydicom`.
- Clean the extracted series description to make it filesystem-safe.
- Use `dicom2nifti.dicom_series_to_nifti` to convert the DICOM series into a `.nii.gz` file named after the sanitized series description.

#### [MODIFY] [dicom_to_nrrd.py](file:///home/clin864/Projects/digitaltwins-platform/my_workspace/pilot-2/Breast/Assay%203%20-%20Image%20conversion/dicom_to_nrrd.py)
- Import `SimpleITK`.
- Use `sitk.ImageSeriesReader()` to read the DICOM series.
- Extract the `0008|103e` (Series Description) tag from the metadata to construct the `.nrrd` filename.
- Save the image to the filesystem using `sitk.WriteImage()`.

#### [MODIFY] [tool_dicom_to_nifti.cwl](file:///home/clin864/Projects/digitaltwins-platform/my_workspace/pilot-2/Breast/Assay%203%20-%20Image%20conversion/tool_dicom_to_nifti.cwl)
- Add `InitialWorkDirRequirement` to inject a `run.sh` script that runs `pip install dicom2nifti pydicom` prior to execution.
- Update `baseCommand` to execute `bash run.sh`.
- Modify `outputBinding.glob` to `"*.nii.gz"` to dynamically capture the generated NIfTI file.

#### [MODIFY] [tool_dicom_to_nrrd.cwl](file:///home/clin864/Projects/digitaltwins-platform/my_workspace/pilot-2/Breast/Assay%203%20-%20Image%20conversion/tool_dicom_to_nrrd.cwl)
- Add `InitialWorkDirRequirement` to inject a `run.sh` script that runs `pip install SimpleITK` prior to execution.
- Update `baseCommand` to execute `bash run.sh`.
- Modify `outputBinding.glob` to `"*.nrrd"` to dynamically capture the generated NRRD file.

## Verification Plan

### Manual Verification
- We will visually inspect the CWL wrappers and Python scripts for correctness.
- When run in an Airflow or CWL context, the scripts will correctly download the required packages in the container before running.
- (Optional) We can perform a dry-run conversion using a sample dataset if one is provided.
