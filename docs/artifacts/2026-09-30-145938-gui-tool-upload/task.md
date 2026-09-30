# Task: GUI tool dataset upload

Extends script and notebook tool upload (docs/artifacts/2026-09-30-122834-tool-dataset-upload, 2026-09-30-141352-notebook-tool-upload) to `tool_type=gui`. It works the same way as script and notebook: stored in MinIO + Postgres and registered in SEEK. Integration with the portal's GUI plugin build pipeline is deferred.

- [x] Failing tests: GUI upload through POST /datasets, through a session, and a crate test with the gui tag
- [x] Allow `gui` in `tool_type` (datasets.py, dataset_uploads.py)
- [x] Update README "Uploading a tool dataset"
- [x] Full test suite
- [x] Live end-to-end with tests/data/tool_volview
- [x] Walkthrough
- [x] Sync artifacts to docs/artifacts/
- [x] gitleaks detect --source docs/artifacts/ --no-git
