# Statistical analysis workflow

A notebook workflow that stands in for a statistical analysis of the lesion position reports
in demos. Nothing is computed.

`code/statistical_analysis.ipynb` has one cell per step (load the reports, compute summary statistics, plot the results); each waits about
10 seconds. The last cell copies the input dataset to `outputs/datasets/` with a note
that it is a placeholder, so Submit uploads a dataset.

Register it like any workflow (see `docs/workflow-dag-authoring.md` in the platform repository);
the platform repository's breast pilot populate script (listed in `util/SCRIPTS.md`) registers all four
stand-in workflows and creates their assays.
