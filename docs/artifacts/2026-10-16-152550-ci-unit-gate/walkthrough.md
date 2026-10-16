# Walkthrough: test hygiene and the CI unit-test gate

## What changed

### One way to run tests: root `Makefile`

| Target | Image (pinned by tag and digest) | Result on this branch |
|---|---|---|
| `make test-api` | `uv:0.9.30-python3.11-bookworm` | 287 passed, 1 skipped (root-only), 202 deselected (integration) |
| `make test-portal-backend` | `uv:0.9.30-python3.9-bookworm` | 224 passed, 7 skipped (Postgres integration) |
| `make test-frontend` | `node:20.20.2-alpine` | 155 passed |
| `make test-jupyterhub` | hub image built from `services/jupyterhub/Dockerfile` | 4 passed |
| `make lint` | ruff 0.17.1 + eslint + vue-tsc | report-only: 154 ruff, 11 eslint errors + 22 warnings, 14 vue-tsc errors |
| `make gitleaks` | gitleaks v8.30.1 | scans `GITLEAKS_RANGE` (default `origin/main..HEAD`) |

How every target runs:
- Dependencies install into the gitignored `.cache/ci/`.
- Tests run with `--network none`, as the invoking user.
- Only the service directory is mounted, so `.env` and `secrets.env` are not visible.

### CI: `.github/workflows/ci.yml`

**Triggers:**
- PRs to `main`. Draft PRs are skipped until "Ready for review".
- Pushes to `main`.
- Manual dispatch.

**Jobs:**
- A `detect changes` job uses `git diff` to choose which suites run on a PR.
- Docs-only PRs run only gitleaks.
- Unneeded jobs show as skipped, and GitHub counts a skipped required check as passing.

**Checks to make required on `main`:**
- `api unit tests`
- `portal-backend unit tests`
- `frontend unit tests`
- `jupyterhub unit tests`
- `gitleaks (PR commits)`

`lint (report-only)` never fails.

**Hardening:**
- `permissions: contents: read`
- the action is pinned by SHA
- `persist-credentials: false`
- superseded PR runs are cancelled
- each job has a timeout

### Test fixes

**API (`services/api`):**
- Deleted 6 legacy scripts that hit live services and had no asserts: `test_assay_api`, `test_download_dataset_api`, `test_minio`, `test_upload_dataset_api`, `test_delete_dataset_api`, `test_upload_dataset`.
- `tests/conftest.py` now fails collection when a test uses a live-service fixture without `@pytest.mark.integration`. It flagged 5 such tests, which are now marked.
- `requirements-test.txt` pins pytest and httpx.
- `pyproject.toml` sets `testpaths`, `pythonpath` and `--strict-markers`.
- Four workspace-dataset tests were failing; two separate causes:
  - **Order-dependent 401s.** The auth bypass was set when the module was imported, and other modules removed it in their teardown. It is now a per-test autouse fixture.
  - **Stale fake.** Since commit `f21a4354`, the endpoint lists `outputs/datasets`. The fake told the root URL apart from the subfolder URL with `"dataset" not in url`, which no longer works.

**Portal backend (`services/portal/backend`):**
- A full run **wiped the working-directory `plugin_registry.db`**. `test_dashboard_assay_download.py` imports the app before any test set `DATABASE_PATH`.
- Now `tests/__init__.py` always points `DATABASE_PATH` at a temp file.
- A regression test was added to `tests/test_live_db_guard.py`; it failed before the fix and passes after.
- pytest is in a non-default `test` dependency group, so production `uv sync` never installs it.
- The suite now runs under pytest. That also runs the 26 pytest-style tests the old `unittest discover` command skipped.

**Frontend (`services/portal/frontend`):**
- `BaseInformationStep.spec.ts` stubbed `LocalFolderDropzone` without its exposed `setProgress`. That caused 10 unhandled rejections, which made the run fail even though every test passed.
- vue-tsc was bumped from 1.8 to 2.2.10, because 1.8 crashes with TypeScript 5.9.
- Added the scripts `type-check` and `lint:check`. `lint:check` is a check-only lint; the existing `lint` always applies `--fix`.

### Docs
- `docs/testing.md`: the make targets, how a run works, what CI gates on, and the safety rules.
- Linked from `README.md` (Contributing) and `docs/development.md`.
- ADR: `docs/decisions/2026-10-16-ci-make-in-pinned-containers.md`.

## How to verify

```bash
make test        # all four suites green
make lint        # reports findings, exit 1 is expected for now
```

On GitHub, checked on PR #353:
- First run: all 7 jobs green, with the same counts as the local run. The jobs take 30 s to 1 m 20 s each.
- A push while the PR was a draft skipped every job. Marking it "Ready for review" triggered a full run.
- The docs-only path filter can only be observed on a later PR, after this one merges. The filter uses the whole PR's diff, and this PR changes the Makefile and the workflow. The filter script was tested locally against docs-only, frontend, API, Makefile, hub and push cases.

## Follow-ups (not in this change)

- `GET /datasets/{uuid}/download` has no test since the legacy script was deleted.
- Integration-test job: a compose file with Postgres 16 and MinIO, non-blocking.
- Global-state leaks between tests in the portal backend: unrestored monkeypatches, imports between test modules.
- Portal backend on Python 3.9 and the frontend on Node 20 are both end-of-life.
- Stale dependency files: API `requirements-dev.txt`, portal `requirements.txt`, frontend `package-lock.json`. The hub image's pip installs are unpinned.
- Burn down the lint and type-check findings, then make lint blocking.
