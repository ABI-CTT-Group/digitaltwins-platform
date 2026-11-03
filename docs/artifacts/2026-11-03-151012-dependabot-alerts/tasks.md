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
- [x] Commit, push and open the PR (#374)
- [x] Merge; confirm the alerts closed (199 → 155)

## PR 3: pytest 8.4.2 → 9.0.3
- [x] Red: run on 8.4.2 with `-W error::pytest.PytestRemovedIn9Warning`
- [x] Bump `requirements-test.txt` in the API and builder
- [x] Bump the `pytest==8.4.2` the Makefile installs for `test-jupyterhub`
- [x] Gates: `make test-api test-builder` (same counts as on `main`), `make lint`, `make docs-check`
- [x] Write the walkthrough section; update this list
- [x] Sync artifacts to docs/artifacts/
- [x] Commit, push and open the PR (#375)
- [x] Merge; confirm the alerts closed

## Fix: portal image ignored yarn.lock (`fix/frontend-dockerignore`, inserted before PR 4)
- [x] Red: probe the builder stage (stale local versions in the image); add a guard spec that fails
- [x] Add `services/portal/frontend/.dockerignore`
- [x] Green: the spec passes; the probe shows the lockfile versions
- [x] Gates: `make test`, `make lint`, `make docs-check`
- [x] Rebuild and restart `portal-frontend`; the portal serves the lockfile-built bundle
- [x] Correct the PR 2 walkthrough claim that relied on the bundle hash
- [x] Write the walkthrough section; update the plan and this list
- [x] Sync artifacts to docs/artifacts/
- [x] Commit, push and open the PR (#377)
- [x] Merge, then un-stash and finish PR 4

## PR 4: refresh frontend packages that ship to the browser (incl. vue 3.5.42)
- [x] Red: list the vulnerable `yarn.lock` entries
- [x] Review the axios 1.13 → 1.20 changelog against our axios interceptors
- [x] Remove those entries and re-run `yarn install`; review `git diff yarn.lock`
- [x] Gates: `make test`, `make lint`, `make docs-check`
- [x] Probe the image for the new versions; rebuild and restart `portal-frontend`; smoke-test (headless browser) sign-in, the dataset list, upload-dataset and the workflow canvas
- [x] Write the walkthrough section; update this list
- [x] Sync artifacts to docs/artifacts/
- [x] Commit, push and open the PR (#378)
- [x] Merge; confirm the alerts closed (153 → 94)

## PR 5: xlsx from the SheetJS CDN 0.20.3
- [x] Red: the classifier matches #356 and #357 on `xlsx` 0.18.5
- [x] Add `sampleTypes.spec.ts` (none existed): writes a real `.xlsx` and reads it back; passes on 0.18.5
- [x] Write the ADR `docs/decisions/2026-11-04-xlsx-from-sheetjs-cdn.md`
- [x] Sync artifacts to docs/artifacts/
- [x] Point `xlsx` at the CDN tarball in `package.json`; `yarn install`
- [x] Check that yarn enforces the tarball hash pinned in `yarn.lock`
- [x] Gates: `make test` (the new spec passes on 0.20.3), `make lint`, `make docs-check`
- [x] Rebuild and restart `portal-frontend`; drop a dataset that contains `samples.xlsx`
- [x] Write the walkthrough section; update this list
- [x] Sync artifacts to docs/artifacts/
- [x] Commit, push and open the PR (#379)
- [x] Review the source with the user: the npm alternatives (`@e965/xlsx`, `read-excel-file`) were rejected; keep the official CDN
- [x] Record the reason SheetJS left npm, and the rejected alternatives, in the ADR and walkthrough
- [x] Sync artifacts to docs/artifacts/
- [x] Merge; confirm the alerts closed (94 → 92)

## PR 6: Python runtime pins (python-multipart, urllib3, requests)
- [x] Red: grep for the vulnerable pins
- [x] Review the python-multipart 0.0.21 to 0.0.31 changes against our upload and form endpoints
- [x] Review the urllib3 2.4 to 2.8 and requests 2.32.4 to 2.33.0 changes against our usage
- [x] Add a unit test that part filenames keep their folder paths (passes on 0.0.20 and 0.0.31)
- [x] Bump the pins in the API prod and dev requirements and in the builder requirements
- [x] Gates: `make test`, `make lint`, `make docs-check`
- [x] Rebuild and restart `api` and `builder`; live-check uploads (through validation rejection, so nothing is stored) and MinIO, SEEK and FHIR calls
- [x] Write the walkthrough section; update this list
- [x] Sync artifacts to docs/artifacts/
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
