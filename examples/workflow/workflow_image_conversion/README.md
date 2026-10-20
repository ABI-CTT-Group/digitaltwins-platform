# Image conversion workflow

A script (Airflow) workflow that converts a DICOM series to NIfTI and NRRD.

- `primary/workflow_image_conversion.cwl` describes the workflow: two steps,
  `dicom_to_nifti` and `dicom_to_nrrd`, each running a tool CWL in `primary/`.
- `code/workflow_image_conversion.py` is the Airflow DAG. It downloads the
  assay's input sample from MinIO (`tool_download_samples.py`), then runs both
  conversions in parallel and uploads the results.
- `code/tool_*.py` are the tools the DAG runs; each exposes `run(...)` and a
  command line.

## Deploying

Register the workflow (portal *Upload workflow* or the platform API
`POST /datasets?category=workflows&workflow_type=script`), then an admin
deploys its DAG (*Deploy DAG* on the portal's Workflows page, or
`POST /workflows/{dataset_uuid}/deploy`). The DAG names itself after the
folder it is deployed to (`workflow_<seek_id>`), so it never hardcodes an id.
See `docs/workflow-dag-authoring.md` in the platform repository.
