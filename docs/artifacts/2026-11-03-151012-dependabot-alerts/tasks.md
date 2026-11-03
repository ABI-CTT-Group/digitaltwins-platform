# Tasks: resolving the Dependabot alerts

Plan: [plan.md](plan.md). Walkthrough: [walkthrough.md](walkthrough.md). One PR per batch, each branched off `main`
after the previous PR merges.

## Setup
- [x] Review the open alerts (284: 2 critical, 137 high, 119 medium, 26 low)
- [x] Write the plan and settle decisions with the user (7 PRs; pydicom left open; xlsx from the SheetJS CDN; vitest 4 last)
- [x] Sync artifacts to docs/artifacts/
- [x] Add this task list
- [x] Sync artifacts to docs/artifacts/

## PR 1: delete the stale npm lockfile (`chore/deps-1-remove-package-lock`)
- [x] Red: confirm `package-lock.json` exists and nothing reads it
- [x] Delete `services/portal/frontend/package-lock.json`
- [x] Update `docs/future_refactoring.md` item 1
- [x] Gates: `make test`, `make lint`, `make docs-check`, `docker compose build portal-frontend`
- [x] Rebuild and restart `portal-frontend`; the portal loads
- [x] Write the walkthrough section
- [x] Sync artifacts to docs/artifacts/
- [x] Commit, push and open the PR
- [x] Merge (#372); confirm the 86 `package-lock.json` alerts closed (284 → 198)

## PR 2: refresh frontend dev and build tools within their ranges
- [x] Red: list the vulnerable `yarn.lock` entries
- [x] Remove those entries and re-run `yarn install` in the pinned node container; review `git diff yarn.lock`
- [x] Remove the `as PluginOption` cast the rollup alignment made unnecessary; update `docs/future_refactoring.md` item 2
- [x] Gates: `make test`, `make lint`, `make docs-check`, `docker compose build portal-frontend`
- [x] Rebuild and restart `portal-frontend`; the portal loads
- [x] Write the walkthrough section; update this list
- [x] Sync artifacts to docs/artifacts/
- [ ] Commit, push and open the PR (on approval)
- [ ] Merge; confirm the alerts closed

## PR 3: pytest 8.4.2 → 9.0.3
- [ ] Red: run on 8.4.2 with `-W error::pytest.PytestRemovedIn9Warning`
- [ ] Bump `requirements-test.txt` in the API and builder
- [ ] Gates: `make test-api test-builder` (same counts as on `main`), `make lint`, `make docs-check`
- [ ] Write the walkthrough section; update this list
- [ ] Sync artifacts to docs/artifacts/
- [ ] Commit, push and open the PR (on approval)
- [ ] Merge; confirm the alerts closed

## PR 4: refresh frontend packages that ship to the browser (incl. vue 3.5.42)
- [ ] Red: list the vulnerable `yarn.lock` entries
- [ ] Review the axios 1.13 → 1.20 changelog against our axios interceptors
- [ ] Remove those entries and re-run `yarn install`; review `git diff yarn.lock`
- [ ] Gates: `make test`, `make lint`, `make docs-check`
- [ ] Rebuild and restart `portal-frontend`; smoke-test sign-in, the dataset list, upload-dataset and the workflow canvas
- [ ] Write the walkthrough section; update this list
- [ ] Sync artifacts to docs/artifacts/
- [ ] Commit, push and open the PR (on approval)
- [ ] Merge; confirm the alerts closed

## PR 5: xlsx from the SheetJS CDN 0.20.3
- [ ] Write the ADR `docs/decisions/2026-11-03-xlsx-from-sheetjs-cdn.md`
- [ ] Sync artifacts to docs/artifacts/
- [ ] Point `xlsx` at the CDN tarball in `package.json`; `yarn install`
- [ ] Gates: `make test` (sampleTypes spec), `make lint`, `make docs-check`
- [ ] Rebuild and restart `portal-frontend`; drop a dataset that contains `samples.xlsx`
- [ ] Write the walkthrough section; update this list
- [ ] Sync artifacts to docs/artifacts/
- [ ] Commit, push and open the PR (on approval)
- [ ] Merge; confirm the alerts closed

## PR 6: Python runtime pins (python-multipart, urllib3, requests)
- [ ] Red: grep for the vulnerable pins
- [ ] Review the python-multipart 0.0.21 to 0.0.31 changes against our upload and form endpoints
- [ ] Bump the pins in the API prod and dev requirements and in the builder requirements
- [ ] Gates: `make test`, `make lint`, `make docs-check`
- [ ] Rebuild and restart `api` and `builder`; smoke-test a dataset upload, a plugin upload, and MinIO, SEEK and FHIR calls
- [ ] Write the walkthrough section; update this list
- [ ] Sync artifacts to docs/artifacts/
- [ ] Commit, push and open the PR (on approval)
- [ ] Merge; confirm the alerts closed

## PR 7: vitest 3 → 4
- [ ] Read the vitest 4 migration guide; check mocks, `server.deps.inline` and the pool settings
- [ ] Bump `vitest`; `yarn install`
- [ ] Remove the `@ts-expect-error` in `vite.config.ts` if the nested vite 7 goes away; update `docs/future_refactoring.md` item 2
- [ ] Gates: `make test` (same counts as on `main`), `make lint`, `make docs-check`, `docker compose build portal-frontend`
- [ ] Write the walkthrough section; update this list
- [ ] Sync artifacts to docs/artifacts/
- [ ] Commit, push and open the PR (on approval)
- [ ] Merge; confirm the alerts closed

## Wrap-up
- [ ] Re-list the open alerts; expect only pydicom, deepmerge and minimatch #513 (new on 2026-11-03, no in-range fix)
- [ ] Record what stays open, and why, in the walkthrough
- [ ] Check whether any ADR is needed beyond the xlsx one
- [ ] Sync artifacts to docs/artifacts/
