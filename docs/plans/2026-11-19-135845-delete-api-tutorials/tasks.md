# Tasks: delete the API tutorials

- [x] Review: tutorials are 2023 workshop material and their code no longer matches the package
- [x] Decision: delete, both `vph/` notebooks included
- [x] Plan written
- [x] Sync plans to docs/plans/
- [x] 1. `git rm -r services/api/tutorials/` (folder gone from disk too)
- [x] 2. `services/api/README.md`: workshop link and layout row
- [x] 3. `docs/codemap.md`: tutorials link
- [x] 4. `docs/future_refactoring.md`: "API tutorials" section and the vph notebook in the imports item
- [x] 5. No references left outside `docs/plans/`; `make docs-check`, `make lint`, `make gitleaks` pass
- [x] 6. Plan synced, Outcome section if anything differed
- [x] Sync plans to docs/plans/
