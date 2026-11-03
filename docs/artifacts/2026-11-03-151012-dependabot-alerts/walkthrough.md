# Walkthrough: resolving the Dependabot alerts

Plan: [plan.md](plan.md). There's one PR per batch, done in order of risk. This file gets a section as each batch lands.

Baseline on 2026-11-03: 284 open alerts (2 critical, 137 high, 119 medium, 26 low).

## PR 1: delete the stale npm lockfile

**Change**
- Deleted `services/portal/frontend/package-lock.json`. The portal image (`Dockerfile`: `COPY package.json yarn.lock`,
  `yarn install --frozen-lockfile`), `make test-frontend`/`make lint` and CI install from `yarn.lock` only. Nothing
  in the repo read the npm lockfile.
- `docs/future_refactoring.md` item 1: removed the lockfile part. The unused `DownloadSheet.vue` and `SubmitSheet.vue`
  are still listed.

**Alerts closed:** all 86 alerts whose manifest is `services/portal/frontend/package-lock.json`. The same packages
still have alerts against `yarn.lock`, and later batches handle those.

**Verification**
- Red: the file was present, and `git grep package-lock` found only the refactoring note.
- `make test-frontend`: 33 files and 162 tests passed.
- `make lint`, `make docs-check`: pass.
- `docker compose build portal-frontend`: builds. The image content that matters doesn't change, because the build
  never copied the npm lockfile into the install step.

## PR 2: refresh frontend dev and build tools within their ranges

**Change**
- In `services/portal/frontend/yarn.lock`, removed the 24 entries for brace-expansion, minimatch, picomatch,
  fast-uri, flatted, immutable, browserslist, baseline-browser-mapping, rollup, postcss-selector-parser,
  serialize-javascript and vite. Then re-ran `yarn install` in the pinned `node:20.20.2-alpine` container, so each
  range resolved to its newest matching version. `package.json` didn't change.
- New versions:
  - vite 6.4.1 → 6.4.5, and the nested copy 7.3.6 → 7.3.7
  - rollup 4.53.3 / 4.61.1 / 4.63.6 → a single 4.67.4
  - brace-expansion 1.1.21 and 5.0.12; minimatch 3.1.5 and 10.2.6; picomatch 2.3.2 and 4.0.7
  - fast-uri 3.1.9, flatted 3.4.4, immutable 5.1.9, browserslist 4.29.5, baseline-browser-mapping 2.11.35,
    postcss-selector-parser 6.1.5, serialize-javascript 7.1.4
  - Their own sub-dependencies (caniuse-lite, electron-to-chromium, node-releases, update-browserslist-db,
    @types/estree, `@rollup/rollup-*`) moved with them. Nothing else changed.
- With every rollup copy now on 4.67.4, the `as PluginOption` cast on `glslify(...)` in `vite.config.ts` was no longer
  needed: type-check passes without it. Removed it and its `PluginOption` import. `docs/future_refactoring.md`
  item 2 now covers only the vite/vitest duplicate, which PR 7 handles.

**Alerts closed (44):** #147, 150, 151, 152, 154, 157, 158, 166, 167, 192, 193, 198, 199, 205, 206, 217, 358, 359, 360,
363, 364, 366, 367, 368, 369, 370, 398, 399, 400, 492–497, 500–503, 506–510.

**Left open**
- #513 (medium, minimatch, published 2026-11-03): every minimatch below 11.0.1 is affected, and only dev tools
  (eslint, glob and others) pull it in, across 3.x, 5.x, 9.x and 10.x ranges. A fix needs a major bump in each parent.
  It's left open until upstream backports a fix or the parents move to minimatch 11.

**Verification**
- Red/green: a classifier compares the `yarn.lock` entries against the open alerts' vulnerable ranges. Before the
  change, the 44 alerts above matched; after it, none do.
- `make test`: API 391, builder 221, frontend 33 files and 162 tests, jupyterhub and util all pass.
- `make lint` (including vue-tsc) and `make docs-check`: pass.
- `docker compose build portal-frontend`: builds with `--frozen-lockfile`. After restarting `portal-frontend`, the
  service is healthy and `/`, `/api/health` and `/sw.js` return 200. The app's entry bundle hash doesn't change, so no
  code that ships to the browser changed.

## PR 3: pytest 8.4.2 → 9.0.3

**Change**
- `pytest==9.0.3` in `services/api/requirements-test.txt` and `services/builder/requirements-test.txt`.
- The `Makefile` `test-jupyterhub` target installed `pytest==8.4.2` into the JupyterHub test image too. Dependabot
  doesn't scan the Makefile, but it's the same vulnerable version, so I bumped it with the others. The JupyterHub image
  runs Python 3.12; pytest 9 needs 3.10 or later.
- No Docker image installs these test requirements, so there's nothing to rebuild.

**Alerts closed (2):** #423 (API) and #458 (builder), "pytest has vulnerable tmpdir handling". The plan estimated 3;
only 2 were open.

**Verification**
- Red: on pytest 8.4.2, `make test-api test-builder test-jupyterhub PYTEST_ARGS="-W error::pytest.PytestRemovedIn9Warning"`
  passed. No test used anything pytest 9 removes.
- Green: `make test` with each suite on `pytest-9.0.3` (confirmed in the session header): API 391 passed / 1 skipped,
  builder 221 passed / 11 skipped, jupyterhub 5 passed. Those counts, and the warning counts, match `main`. Frontend
  and util pass too.
- `make lint` and `make docs-check`: pass.
