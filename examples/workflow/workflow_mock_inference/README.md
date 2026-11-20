# Mock inference workflow

A script (Airflow) workflow that stands in for the breast MRI inference workflow (nnUNet skin, outer rib, sternum and lesion models)
in demos. Nothing is computed.

Steps: `download_samples` → `skin_inference` → `outer_rib_inference` → `sternum_inference` → `lesion_inference`. Each step waits about 10 seconds and passes.
The last step writes a small placeholder text file to each assay output, so Submit
uploads a tiny dataset.

- `primary/workflow_mock_inference.cwl`: the workflow; each step runs a `primary/tool_mock_*.cwl`.
- `code/workflow_mock_inference.py`: the Airflow DAG. It names itself after the folder it is deployed to.
- `code/tool_mock_*.py`: one tool per step; each only waits.

Register it like any workflow (see `docs/workflow-dag-authoring.md` in the platform repository);
`util/populate-isa-mock-assays.sh` registers all the mock workflows and creates their assays.
