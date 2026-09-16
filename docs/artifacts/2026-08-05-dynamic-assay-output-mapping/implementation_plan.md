# Implementation plan

1. Stop relying on hardcoded output keys (`nifti_output`, `nrrd_output`) in the Airflow DAG.
2. Build a mapping from assay output metadata (`sample_name` -> `name`) in the API payload.
3. Resolve output prefixes in the DAG using metadata-driven names, with legacy fallback for existing runs.
4. Add regression coverage to ensure dynamic output names are forwarded from `run_assay`.
