# Task List

- `[x]` Update MinIO prefix logic to use `assay_{assay_id}/{dataset_name}` instead of just `{dataset_name}`.
- `[x]` Populate `samples.xlsx` using `sparc-me` with discovered samples in `workflow.py`.
- `[x]` Pre-populate `manifest.xlsx` using `sparc-me` with expected tool outputs based on `configs["outputs"]`.
- `[x]` Ensure empty S3 folder markers are created for all SPARC structure directories (`primary/`, `derivative/`, `source/`, `code/`, `docs/`, `protocol/`, and `primary/sub-{id}/sam-{id}/`).
- `[ ]` Verify changes locally.
- `[ ]` Update `walkthrough.md` with a summary of the implementation.
