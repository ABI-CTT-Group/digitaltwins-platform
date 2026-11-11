# Task: tools dataset upload (script type)

- [x] 0. Copy the plan to docs/artifacts
- [x] Sync artifacts to docs/artifacts/
- [x] 0. Write the ADR (docs/decisions/2026-09-30-register-tools-in-seek-via-single-ro-crate-post.md)
- [x] 0b. Remove hardcoded MinIO credentials from the example tool script; rebuild the zip
- [x] 1. Spike: single RO-Crate POST against live SEEK
- [x] Sync artifacts to docs/artifacts/ (spike notes)
- [x] 2. Tool validation (find_tool_cwl) + tests
- [x] 3. SEEK writer (build_tool_crate / register_tool / delete_workflow) + tests
- [x] 4. commit_tool pipeline with rollback
- [x] 5. One-shot POST /datasets for tools + tests
- [x] 6. Resumable sessions for tools (migration 0002) + tests
- [x] 7. Delete also removes the SEEK workflow + tests
- [x] 8. Fix get_dataset(get_cwl=True) for tools + test
- [x] 9. Docs, re-check the ADR, full test run
- [x] Sync artifacts to docs/artifacts/ (walkthrough)
- [x] gitleaks detect --source docs/artifacts/ --no-git
