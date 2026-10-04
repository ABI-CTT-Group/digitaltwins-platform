# Tasks: workflow dataset upload

Plan: [plan.md](plan.md) · Walkthrough: [walkthrough.md](walkthrough.md) · ADR: [2026-10-02-workflow-dataset-ingest](../../decisions/2026-10-02-workflow-dataset-ingest.md)

- [x] Interview and plan, approved 2026-10-02
- [x] Sync artifacts to docs/artifacts/ (plan.md)
- [x] Draft the ADR `docs/decisions/2026-10-02-workflow-dataset-ingest.md` (Proposed)
- [x] Baseline full suite: 237 passed, 4 failed and 1 error (all legacy)
- [x] 0. Spike: live SEEK accepts the workflow crate and extracts its input, outputs and steps (SEEK 64, deleted)
- [x] 1. Migration 0004 and `create_session(workflow_type)` (`test_migrate.py`)
- [x] 2. `workflows/validation.py` (`test_workflow_validation.py`, 22 tests); both example datasets load
- [x] 3. SEEK `build_workflow_crate` and `register_workflow` (`test_seek_writer.py`, +3)
- [x] 4. `workflows/pipeline.py` `commit_workflow` with rollback; `FakeSeek.register_workflow`
- [x] 5. One-shot `POST /datasets?category=workflows` (`test_datasets_workflows_api.py`)
- [x] 6. Sessions, CLI and client (`test_dataset_uploads_workflows_api.py`, CLI +3, client +1)
- [x] 7. FHIR: tool ActivityDefinitions, then the workflow PlanDefinition; tree, annotation and preview; retry (`test_workflow_fhir.py`, API +6, sessions +2)
- [x] 8. Delete: `delete_tools`, 409s, tool cascade, assay outputs unaffected (`test_delete_dataset_cleanup.py`, +5)
- [x] 9. README and docstrings
- [x] Full suite: 311 passed, with the same 4 failed and 1 error as the baseline
- [x] Write walkthrough.md
- [x] Sync artifacts to docs/artifacts/ (plan.md, walkthrough.md, task.md); gitleaks: no leaks
- [x] Live end-to-end: both example datasets, FHIR, the 409s, and delete with and without `delete_tools` (see walkthrough)
- [x] Task-end ADR check: status set to Accepted, step 0 outcome recorded, no further decisions
- [x] Sync artifacts to docs/artifacts/; gitleaks: no leaks
- [x] Deploy: `digitaltwins-api` rebuilt and restarted by the user; healthy, serves `workflow_type` and `delete_tools`, migration 0004 applied
- [ ] Commit (only when asked)
