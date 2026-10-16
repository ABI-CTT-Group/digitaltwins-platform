# Tasks: CI unit-test gate

## Phase 0: setup
- [x] Branch `feat/ci-unit-gate` from `origin/main`
- [x] Sync plan to docs/artifacts/
- [x] Draft ADR `docs/decisions/2026-10-16-ci-make-in-pinned-containers.md` (Proposed)
- [x] Sync artifacts to docs/artifacts/

## Phase 1: API
- [x] 1. Delete the legacy live-service scripts (6 files)
- [x] 2. Red: marker guard in conftest flags the 5 unmarked live tests
- [x] 2. Green: mark them as `integration`
- [x] 2b. (found while running) Fix 4 failing workspace-dataset tests:
  - order-dependent 401s: import-time auth override cleared by other modules' teardown → per-test autouse fixture
  - stale Jupyter fake: endpoint lists `outputs/datasets` since f21a4354, the fake keyed on "dataset" not in URL
- [x] 3. `requirements-test.txt` + pytest config
- [x] 4. Makefile `test-api`: green (287 passed, 1 skipped (root-only), 202 deselected)
- [x] Sync artifacts to docs/artifacts/

## Phase 2: portal backend
- [x] 5. Red: regression test for the working-dir SQLite wipe (in `tests/test_live_db_guard.py`)
- [x] 5. Green: `tests/__init__.py` forces a temp `DATABASE_PATH`
- [x] 6. `test` dependency group + uv.lock (adds pytest 8.4.2 + deps; uv dropped greenlet s390x wheels no longer on PyPI)
- [x] 7. Makefile `test-portal-backend`: green (224 passed, 7 skipped Postgres-integration); `plugin_registry.db` mtime unchanged
- [x] Sync artifacts to docs/artifacts/

## Phase 3: frontend
- [x] 8. vue-tsc ^2.2.10, `type-check` and `lint:check` scripts (report: 14 type errors, 11 lint errors + 22 warnings, pre-existing)
- [x] 9. Makefile `test-frontend`: green (155 passed)
- [x] 9b. (found while running) BaseInformationStep.spec stubbed LocalFolderDropzone without `setProgress` → 10 unhandled rejections failed the run; stub now exposes it
- [x] Sync artifacts to docs/artifacts/

## Phase 4: targets, CI, docs
- [x] 10. Makefile `test-jupyterhub` (4 passed), `lint`, `gitleaks`, `test`
  - ruff pinned to `--select E4,E7,E9,F` (154 findings) instead of 0.17 defaults (1,330, mostly style); recorded in ADR
- [x] 11. `.github/workflows/ci.yml` (changes job, path filter, draft skip); actionlint clean; filter script tested for docs/frontend/api/Makefile/hub/push cases
- [x] 12. `docs/testing.md`, links from README + docs/development.md, ADR accepted
- [x] Sync artifacts to docs/artifacts/

## Phase 5: verify and PR
- [x] `make test lint` in a clean checkout-equivalent tree (no .env, node_modules or caches): all 4 suites green, lint reports as expected, 1m34s cold
- [ ] Push and open the PR (ask first)
- [ ] Required checks on `main` (ask first)

## Follow-ups (out of scope)
- Coverage lost with the deleted legacy scripts: `GET /datasets/{uuid}/download` has no remaining test
  (`POST /assays`, `POST /datasets`, `DELETE /datasets/{uuid}` are still covered elsewhere)
