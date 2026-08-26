# Walkthrough

`run_assay` now derives output-name aliases from assay metadata (`sample_name` -> `name`) and includes that map in each Airflow DAG payload.

`workflow_image_conversion` resolves NIfTI/NRRD output prefixes from this metadata-driven map, so output keys like `nifti dataset` and `nrrd dataset` are handled correctly.

Legacy key fallback remains in place (`nifti_output` / `nrrd_output`) for backward compatibility.
