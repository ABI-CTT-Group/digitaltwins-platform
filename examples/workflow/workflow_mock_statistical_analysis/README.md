# Mock statistical analysis workflow

A notebook workflow that stands in for a statistical analysis of the lesion position reports
in demos. Nothing is computed.

`code/mock_statistical_analysis.ipynb` has one cell per step (load the reports, compute summary statistics, plot the results); each waits about
10 seconds. The last cell copies the input dataset to `outputs/datasets/` with a note
that it is a mock output, so Submit uploads a dataset.

Register it like any workflow (see `docs/workflow-dag-authoring.md` in the platform repository);
`util/populate-isa-mock-assays.sh` registers all the mock workflows and creates their assays.
