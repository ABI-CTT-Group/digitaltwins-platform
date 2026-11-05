# Tasks: start GUI tool backends on launch

Plan: [plan.md](plan.md). ADR: [2026-11-05-start-gui-backends-on-launch](../../decisions/2026-11-05-start-gui-backends-on-launch.md).
Builder baseline before the change: 244 passed, 11 skipped.

## 0. Docs first
- [x] Sync plan to `docs/artifacts/`
- [x] Draft ADR; mark ADR 2026-10-02's backend bullet as superseded in part
- [x] Glossary: "Backend (of a GUI tool)" (deploy vs start, deployment)
- [x] `make docs-check`

## 1. Builder: migration 0002
- [x] Failing tests: one deployment per build (tool, workflow), error stored (`test_db_constraints.py`); duplicates keep newest (`test_postgres_integration.py`)
- [x] Model: `error` column, unique `build_id` / `workflow_build_id`
- [x] `0002_one_deployment_per_build.sql`
- [x] Green: `make test-builder`
- [x] Postgres integration tests against a throwaway Postgres (12 passed)

## 2. Builder: one row per build
- [x] Reuse the build's deployment row on redeploy (in `start_backend`, reset status/error, keep deploy_id); fixed `run_deployment`'s exception branch writing a non-existent `error_message`

## 3. Builder: start endpoints
- [x] Failing tests: `tests/test_backend_start.py` (11 red)
- [x] `POST /tools/backend/{expose}/start`, `GET /tools/backend/{expose}`
- [x] Shared start helper, used by the `execute?command=up` endpoint too
- [x] Remove `/tools/plugin/{id}/deploy`, `/workflow/{id}/deploy`, `/tools/check/deploy/{id}/`; update their tests
- [x] Green: `make test-builder` (254 passed, 12 skipped); ruff clean

## 4. Portal: /tool-view ensures the backend
- [x] Failing specs: `bootstrap/__tests__/tool_backend.spec.ts`, `views/tool-plugin/__tests__/tool-plugin-view.spec.ts` (5 red)
- [x] `ensureBackend` + `BackendStartError` in `tool_api.ts`; spinner text and error in `tool-plugin-view.vue`
- [x] Green: `make test-frontend` (185 passed)

## 5. Portal: Tool Hub card
- [x] Failing spec updates in `cards.spec.ts` (2 red)
- [x] `ToolCard.vue`: Launch without backend check; menu only Stop backend + View logs
- [x] `ToolsOverallView.vue` / `tool_api.ts` / `services/tool.ts`: remove deploy and compose-up wiring and orphaned calls
- [x] Green: `make test-frontend` (186 passed); `make lint` clean

## 6. Finish
- [x] `make lint`, `make docs-check`, `make test` (api 407, builder 254, frontend 186, hub 5)
- [x] Update `services/portal/docs/plugin-system-architecture.md` and `services/builder/AGENTS.md` (the builder README has no deploy section)
- [x] Rebuild and restart `builder` and `portal-frontend`; live checks 1–4 through the API
- [x] Click-through in a browser: Tool Hub Launch and a gui assay Launch (checked by the user)
- [x] ADR final pass; walkthrough; sync artifacts
- [x] gitleaks dir scan (no leaks)
