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
- **Correction (found during PR 4):** that unchanged hash doesn't prove the claim. The image was being built from the
  build host's stale local `node_modules`, not from `yarn.lock` (see "Fix: portal image ignored yarn.lock" below), so
  the hash couldn't have changed whatever the lockfile said. The conclusion still holds for a different reason: PR 2
  changed only dev and build tools.

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

## Fix: portal image ignored yarn.lock (found during PR 4, shipped before it)

**Problem**
- `services/portal/frontend/Dockerfile` runs `COPY package.json yarn.lock`, then `yarn install --frozen-lockfile`, then
  `COPY . .`. The folder had no `.dockerignore`, so on any build host with a local `node_modules` (a developer
  machine, for example), `COPY . .` overwrote the clean install, and `yarn build` bundled whatever versions were on
  that host. Docker doesn't read `.gitignore`. A clean checkout, as in CI or on a fresh server, wasn't affected.
- How it showed up: after PR 4's lockfile refresh (axios 1.21.0, vue 3.5.44), the rebuilt image still served the same
  bundle hash. A probe of the builder stage found axios 1.13.2 and vue 3.5.25: the stale local install.

**Change**
- Added `services/portal/frontend/.dockerignore` with `node_modules`, `build` and `dist`.
- Added `src/__tests__/dockerignore.spec.ts`, which fails if those entries go missing. It runs in vitest's `node`
  environment because it reads a file and needs no DOM.

**Verification**
- Red: the new spec failed with ENOENT. The builder-stage probe on `main` with no `.dockerignore` had vite 6.4.1, the
  stale local version.
- Green: the spec passes. The same probe with the `.dockerignore` has vite 6.4.5, as `yarn.lock` pins.
- `make test`: API 391, builder 221, frontend 34 files and 164 tests (2 new), jupyterhub and util pass. `make lint`
  and `make docs-check` pass.
- After rebuilding and restarting `portal-frontend`, it's healthy, and `/`, `/api/health`, `/sw.js` and the new entry
  bundle return 200. The bundle hash changed (`index-CJ4o-C4T.js` → `index-Bo9DUbwr.js`) because the image is now
  built from the lockfile. Comparing the stale local install with `yarn.lock`, only build and dev tools differ (vite,
  rollup, browserslist data, vue-tsc and their helpers); no runtime library does.

## PR 4: refresh frontend packages that ship to the browser

**Change**
- In `services/portal/frontend/yarn.lock`, removed the entries for axios, lodash, lodash-es, js-yaml, defu, fflate,
  follow-redirects, form-data, nanoid, postcss, source-map-js, vue and vue's core `@vue/*` packages (compiler-core,
  compiler-dom, compiler-sfc, compiler-ssr, reactivity, runtime-core, runtime-dom, server-renderer, shared), then
  re-ran `yarn install`. `package.json` didn't change.
- New versions, each the newest inside its existing range:

  | Package | Old | New |
  |---|---|---|
  | axios | 1.13.2 | 1.21.0 |
  | vue and `@vue/*` | 3.5.25 | 3.5.44 |
  | lodash, lodash-es | 4.17.21 | 4.18.1 |
  | js-yaml | 4.1.1 | 4.3.2 |
  | nanoid | 3.3.11 | 3.3.20 |
  | postcss | 8.5.6 | 8.5.32 |
  | defu | 6.1.4 | 6.1.7 |
  | fflate | 0.7.4, 0.8.2 | 0.7.5, 0.8.3 |
  | follow-redirects | 1.15.11 | 1.16.2 |
  | form-data | 4.0.5 | 4.0.6 |

  source-map-js moved to the 1.2.2 copy that was already in the lockfile.
- axios 1.21.0 adds `https-proxy-agent` 5 (with `agent-base` 6) and `proxy-from-env` 2 as dependencies. These are
  Node-only: axios's `browser` field swaps its Node HTTP adapter for an empty module, so they don't reach the bundle.

**Choosing axios 1.21.0 over the minimum fix (1.20.0)**
- I kept the same approach as PR 2: newest within the range. 1.21.0 was published 2026-10-27.
- I read the release notes from 1.13.3 to 1.21.0. The one breaking change, in 1.21.0, is that header defaults built
  from custom class instances become literal headers. The portal sets no header defaults, only `axios.defaults.baseURL`
  and `axios.create({ baseURL })` in `src/bootstrap/http.ts`.
- The other behaviour changes in that span don't affect how the portal uses axios in the browser (XHR adapter,
  interceptors that set `Authorization` and rewrite `config.data` and `config.params`, and retry by re-sending the
  original config after a 401):
  - fetch-adapter body limits (1.16.0);
  - Node proxy and redirect handling (1.15 to 1.18);
  - XHR navigation aborts now reject with ECONNABORTED (1.20.0);
  - trailing slashes in base URLs are collapsed (1.19.0).

**Alerts closed (59):** #141–143, 161–165, 168–191, 194–197, 200–204, 207, 208, 213–216, 218–221, 402–407, 442, 444.

**Verification**
- Red/green: the lockfile classifier matched the 59 alerts above on `main` and none of them after the change. What
  remains in `yarn.lock` belongs to PR 5 (xlsx) and PR 7 (vitest, @vitest/mocker, tinypool), plus deepmerge and
  minimatch #513.
- `make test`: API 391, builder 221, frontend 34 files and 164 tests, jupyterhub and util all pass. The frontend test
  cache had axios 1.21.0 and vue 3.5.44. `make lint` and `make docs-check` pass.
- Image: built on `main` after the `.dockerignore` fix. A builder-stage probe shows axios 1.21.0, vue and
  `@vue/server-renderer` 3.5.44, lodash-es 4.18.1, js-yaml 4.3.2, nanoid 3.3.20 and postcss 8.5.32. After rebuilding
  and restarting `portal-frontend`, it's healthy and serves a new entry bundle, `index-BW-tXSSc.js`.
- Headless browser (Playwright 1.48.2 in a throwaway container, against the local deployment):
  - The home page draws the 3D heart, and the heart chunk loads with 200.
  - Keycloak sign-in works.
  - `/catalogue/tools`, `/catalogue/workflows`, `/catalogue/measurements` and `/catalogue/models` made 12 API calls,
    all 2xx, all carrying an `Authorization` header (checked for presence, never read).
  - In the workflow assembler, opening a workflow draws the CWL graph (15 nodes, 14 edges).
  - Dropping `services/api/tests/data/example_sds_dataset/` into a new measurement upload filled in the name and the
    two sample types from `samples.xlsx`. The test then pressed Cancel, and the server still had 0 open uploads.
  - No console errors and no failed requests.
