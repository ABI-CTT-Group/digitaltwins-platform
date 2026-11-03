# Plan: resolve the open Dependabot alerts

## Context

The repo has 284 open Dependabot alerts (2 critical, 137 high, 119 medium, 26 low). Most come from duplication or from
dev-only tooling. The real exposure is three Python packages that run live in the API and builder, plus a few
packages bundled into the portal's browser code. The user asked for the least dangerous fixes first, and careful
review of the ones that could break the platform.

Decisions settled with the user:
- **7 PRs, one per batch**, done in order of risk. Each branch comes off `main` after the previous PR merges, because
  batches 2, 4, 5 and 7 all touch `yarn.lock`.
- **pydicom: leave the alert open.** fhir-cda 1.2.5 pins `pydicom==2.4.4` exactly, and it only calls `dcmread` on
  single files, so the FileSet/DICOMDIR path traversal can't be reached.
- **xlsx: switch to the SheetJS CDN tarball 0.20.3.**
- **vitest 3 → 4: in scope, as the last batch.**

Defaults I chose (the user can override them):
- Use the lowest patched version that clears each alert.
- Refresh transitive npm packages by deleting only their `yarn.lock` entries and re-running `yarn install`, which
  resolves the newest version within the existing range. No blanket `yarn upgrade`, and no `resolutions` unless an
  entry won't move.
- Add no `dependabot.yml`; it's out of scope.

Facts checked before planning:
- **Python:** a dry-run resolution of `requests==2.33.0`, `urllib3==2.8.0` and `python-multipart==0.0.31` succeeds
  for both the API and the builder. It resolves fastapi 0.116.1, starlette 0.47.3 and botocore (`urllib3<3`) cleanly.
- **npm:** for every `yarn.lock` alert except vitest, @vitest/mocker, tinypool, @vue/server-renderer, xlsx and
  deepmerge, the patched version satisfies the range already declared. For @vue/server-renderer, `vue` pins it
  exactly, so moving `vue` to 3.5.42 fixes it; that's still inside `^3.5.13`.

## Process, applied to every PR

1. `git checkout main && git pull`, then `git checkout -b chore/deps-<n>-<slug>`.
2. **Red:** make a check that proves the alert. Re-run the version classifier against the lockfile, or run
   `grep '^pkg==' requirements*.txt`, and record which vulnerable versions are present.
3. Make the change.
4. **Green:** the vulnerable versions are gone, plus the gates listed under each batch. `make lint` and
   `make docs-check` run in every PR.
5. Rebuild and restart only the affected service, by name. Never run a blanket `docker compose up -d`.
6. Sync the artifacts: copy this plan and append the batch's section to the walkthrough in
   `docs/artifacts/2026-11-03-<HHMMSS>-dependabot-alerts/` (`plan.md` and `walkthrough.md`). Scan them with gitleaks.
   No local paths, no live-operations details.
7. Stop and report. **I commit and open the PR only when you say so.** Commits use Conventional Commits with the
   Co-Authored-By trailer. The PR body lists the alerts it closes.
8. After merging, check on GitHub that the alerts closed.

## Batches, least dangerous first

### PR 1: delete the stale npm lockfile (86 alerts, no runtime effect)
- Delete `services/portal/frontend/package-lock.json`. Nothing reads it: the Dockerfile, the Makefile and CI all use
  `yarn.lock`.
- `docs/future_refactoring.md` item 1: remove only the `package-lock.json` sentence. The unused
  `DownloadSheet.vue` and `SubmitSheet.vue` stay on that list.
- **Gates:** `make test-frontend`, plus a `docker compose build portal-frontend` to prove the image still builds.

### PR 2: refresh frontend dev and build tools within existing ranges (about 40 alert entries in yarn.lock)
- Packages: brace-expansion (1.x, 2.x, 5.x), minimatch (3.x, 9.x), picomatch (2.x, 4.x), fast-uri, flatted,
  immutable, browserslist, baseline-browser-mapping, rollup, postcss-selector-parser, serialize-javascript,
  vite 6.4.1 → ≥6.4.4, and the nested vite 7.3.6 → ≥7.3.7.
- Method: remove those entries from `yarn.lock`, run `yarn install` in the pinned `node:20.20.2-alpine` container
  with only `services/portal/frontend` mounted, then review `git diff yarn.lock`. Only these packages, and any
  sub-dependencies they newly pull in, may change.
- **Gates:** `make test-frontend`, `make lint` (vue-tsc), and `docker compose build portal-frontend`. Check that the
  `@ts-expect-error` at `vite.config.ts:160` still holds, because nested vite still exists until PR 7.
- Rebuild `portal-frontend` and load the portal.

### PR 3: pytest 8.4.2 → 9.0.3 (test files only, 3 alerts)
- `services/api/requirements-test.txt` and `services/builder/requirements-test.txt`.
- **Red step first:** on 8.4.2, run `make test-api test-builder PYTEST_ARGS="-W error::pytest.PytestRemovedIn9Warning"`
  to surface any pytest-9 removals before bumping. A static grep found no `tmpdir`, `py.path` or
  `pytest.warns(None)`.
- **Gates:** `make test-api test-builder` pass with the same counts as on `main`.

### PR 4: refresh frontend packages that ship to the browser (medium risk)
- Inside existing ranges: axios 1.13.2 → ≥1.20.0, lodash and lodash-es → ≥4.18.0 (from element-plus), js-yaml
  → ≥4.3.2, defu → ≥6.1.5, fflate (0.7.x, 0.8.x), follow-redirects, form-data, nanoid → ≥3.3.12, postcss → ≥8.5.23,
  source-map-js, and `vue` 3.5.25 → 3.5.42, which also moves `@vue/server-renderer` and the other `@vue/*`
  packages pinned to it.
- Same lockfile-entry method as PR 2. `package.json` doesn't change; every new version is inside its range.
- **Review before merging:** read the axios changelog from 1.13 to 1.20, which includes the header/interceptor
  behaviour behind the alert. Check that the 4 files importing axios, such as interceptors that add the Keycloak
  token, still behave the same.
- **Gates:** `make test-frontend` and `make lint`. Rebuild `portal-frontend`, then smoke-test in the browser: sign
  in through Keycloak, run a page that makes API calls (dataset list), the upload-dataset flow (js-yaml, jszip),
  and the workflow canvas.

### PR 5: switch xlsx to the SheetJS CDN 0.20.3 (2 alerts; includes an ADR)
- `package.json`: `"xlsx": "https://cdn.sheetjs.com/xlsx-0.20.3/xlsx-0.20.3.tgz"`, then `yarn install` to update
  `yarn.lock`. The only consumer is `src/views/upload-dataset/measurements/components/sampleTypes.ts:76`; the
  `XLSX.read` and `sheet_to_json` API it uses doesn't change.
- **ADR** `docs/decisions/2026-11-03-xlsx-from-sheetjs-cdn.md`:
  - Context: npm's xlsx stopped at 0.18.5, which has 2 high CVEs.
  - Options considered: CDN tarball, accepting the risk, or switching to another library.
  - Decision: CDN tarball, with the integrity hash pinned in `yarn.lock`.
  - Consequence: image builds also need to reach `cdn.sheetjs.com`. `util/airgap.sh` blocks egress only after the
    build, so the airgap flow isn't affected.
- **Gates:** the `sampleTypes` spec passes in `make test-frontend`, plus `make lint` and `make docs-check` (for the
  new ADR). Rebuild `portal-frontend` and drop a dataset folder containing `samples.xlsx` to check the sample types
  are filled in.

### PR 6: Python runtime pins (about 87 alerts; most likely to break the platform)
- `python-multipart` 0.0.20 → 0.0.31, `urllib3` 2.3.0 → 2.8.0 and `requests` 2.32.3 → 2.33.0, in
  `services/api/requirements-prod.txt`, `services/api/requirements-dev.txt` and `services/builder/requirements.txt`.
  The `requirements-test.txt` files inherit them through `-r`.
- **Behaviour changes to review in python-multipart 0.0.21 to 0.0.31:**
  - 0.0.30 treats only `&` as a separator in URL-encoded forms; `;` no longer splits fields.
  - 0.0.26 to 0.0.28: preamble and epilogue handling, header limits, and a 256-byte cap on the boundary.
  - 0.0.25 removed the custom FormParser classes.
  - Check that nothing in our code calls `multipart` directly (it should only reach us through Starlette).
  - Check every `UploadFile` and `Form(` endpoint: 7 in `services/builder/app/router/workflow_router.py`,
    `workflow_tool_plugin.py` and the API routers.
- **Gates:** `make test-api test-builder`, where the API has 7 `test_*upload*` suites. Then rebuild and restart only
  `api` and `builder`: `docker compose up -d --build api builder`. Smoke-test live: upload a dataset through the
  portal, upload or register a workflow-tool plugin through the builder, and check that MinIO (boto3 on the new
  urllib3), SEEK and FHIR calls still work from the API logs.
- **Rollback:** revert the commit and rebuild `api` and `builder`.

### PR 7: vitest 3.2 → 4 (2 critical, 3 medium, plus the nested vite 7)
- In `package.json`, set `vitest` to `^4.1.12`, which pulls in `@vitest/mocker` ≥4.1.12 and tinypool ≥2.1.2.
  `jsdom` and `@vue/test-utils` stay unless vitest 4 requires a change to them.
- Read the vitest 4 migration guide first. Relevant here:
  - Mock reset semantics: we have 14 `vi.resetAllMocks` and 1 `vi.restoreAllMocks`.
  - `vi.mock` and `vi.hoisted` behaviour: 66 and 22 uses.
  - Whether `server.deps.inline` is still supported, or now belongs under `deps` (`vite.config.ts:165`).
  - The pool and worker changes.
- If vitest 4 resolves to the hoisted vite 6.4.x, the nested vite 7 copy disappears. The `@ts-expect-error` at
  `vite.config.ts:160` then fails type-check, so remove it, and update `docs/future_refactoring.md` item 2 to match.
  That's an orphan this change creates; anything beyond it stays untouched.
- **Gates:** `make test-frontend` with the same test count as `main` (33 spec files), plus `make lint`. Dev-only, so
  there's no service to rebuild beyond confirming `docker compose build portal-frontend`.

## What stays open afterwards (documented in the walkthrough)
- pydicom (high): blocked by fhir-cda's exact pin, and the vulnerable code isn't reachable. Left open on purpose.
- deepmerge (low): dev-only, with no fix released.

## Critical files
- `services/portal/frontend/{package.json,yarn.lock,package-lock.json,vite.config.ts}`
- `services/api/requirements-{prod,dev,test}.txt`, `services/builder/requirements{,-test}.txt`
- `docs/future_refactoring.md` (items 1 and 2), the new ADR, and `docs/artifacts/2026-11-03-*-dependabot-alerts/`

## Verification summary
- Each PR passes its gates (above), plus `make lint`, `make docs-check` and `make gitleaks`; CI's 5 required checks
  pass.
- Live smoke tests after rebuilding a service: PR 2, 4 and 5 for `portal-frontend`; PR 6 for `api` and `builder`.
- After each merge, re-run
  `gh api repos/ABI-CTT-Group/digitaltwins-platform/dependabot/alerts -f state=open` and confirm the expected alerts
  closed. Target at the end: 2 open (pydicom and deepmerge).
