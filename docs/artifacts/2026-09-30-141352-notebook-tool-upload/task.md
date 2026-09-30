# Task: notebook tool dataset upload

Extends docs/artifacts/2026-09-30-122834-tool-dataset-upload (script tools) to `tool_type=notebook`.

- [x] Failing tests: notebook upload through POST /datasets, through a session, and a crate test with the notebook tag
- [x] Allow `notebook` in `tool_type` (datasets.py, dataset_uploads.py)
- [x] Update README "Uploading a tool dataset"
- [x] Full test suite
- [x] Live end-to-end with tests/data/tool_cohort_selection
- [x] Walkthrough
- [x] Sync artifacts to docs/artifacts/
- [x] gitleaks detect --source docs/artifacts/ --no-git
