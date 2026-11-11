# Tasks: GUI tool launch context

- [x] 0. Branch `feat/gui-launch-context` from `main`; plan folder with plan.md and tasks.md
- [x] Sync plans to docs/plans/
- [x] 1. API: `cohort` and per-input `bucket` in `get_assay_gui_inputs` (test first)
- [x] 1a. API: GUI inputs keep their own samples when two datasets share `sub-1/sam-1` (test first; added during implementation)
- [x] 2. API: `schema_version`, `cohort`, `bucket`, `key` in `get_assay_gui_context` (test first)
- [x] 3. Portal: `LaunchContext` type, `toLaunchContext`, `provide('launchContext')`, example JSON (tests first)
- [x] 4. Docs: `docs/gui-tool-authoring.md`, docs index, glossary, request-flows, plugin-system-architecture, ADR
- [x] Sync plans to docs/plans/
- [x] 5. Rebuild and restart `api` and `portal-frontend`; check a gui assay launch by hand
- [x] 6. `make test`, `make lint`, `make docs-check`, `make gitleaks`; re-check ADR
- [x] Sync plans to docs/plans/
- [x] Note for tool authors kept outside the repo: what the two existing GUI tools need to change (`my_workspace/`, not committed)
- [x] Sync plans to docs/plans/ (after step 1a)
- [x] Commit as atomic Conventional Commits: `feat(api)`, `fix(api)` (step 1a), `feat(portal)`, `docs` (this plan folder and the ADR included)
