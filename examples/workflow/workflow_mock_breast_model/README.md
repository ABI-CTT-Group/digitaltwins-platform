# Mock breast model generation workflow

A script (Airflow) workflow that stands in for generating a breast model from skin, outer rib and sternum segmentations
in demos. Nothing is computed.

Steps: `point_cloud_generation` → `mesh_fitting`. Each step waits about 10 seconds and passes.
The last step writes a small placeholder text file to each assay output, so Submit
uploads a tiny dataset.

- `primary/workflow_mock_breast_model.cwl`: the workflow; each step runs a `primary/tool_mock_*.cwl`.
- `code/workflow_mock_breast_model.py`: the Airflow DAG. It names itself after the folder it is deployed to.
- `code/tool_mock_*.py`: one tool per step; each only waits.

Register it like any workflow (see `docs/workflow-dag-authoring.md` in the platform repository);
`util/populate-isa-mock-assays.sh` registers all the mock workflows and creates their assays.
