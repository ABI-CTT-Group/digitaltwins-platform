# Plan: test-suite hygiene + CI unit-test gate

## Context

The repo has four real automated test suites:
- `services/api`: pytest, Python 3.11, about 447 tests.
- `services/portal/backend`: a mix of unittest and pytest, Python 3.9, about 228 tests.
- `services/portal/frontend`: vitest, about 149 tests.
- `services/jupyterhub`: pytest, 1 file.

The repo has **no test CI**. Today the suites run through ad-hoc `docker run` recipes that are scattered across `docs/artifacts/*/walkthrough.md`. A best-practice review found the following problems, which the plan fixes or explicitly defers.

### Review findings (best-practice gaps)

| # | Finding | Severity | Action |
|---|---|---|---|
| R1 | A full portal-backend run **wipes the working-dir `plugin_registry.db`**. `test_dashboard_assay_download.py` imports `app.main` before any test sets `DATABASE_PATH`, so the engine binds to `./plugin_registry.db` and `drop_all` erases it. This has already happened on the host. | High | Fix (TDD) |
| R2 | 6 legacy API "tests" are scripts with no asserts. They hit live Postgres and MinIO through the repo `.env`, and one can delete a real dataset. | High | Delete (decided) |
| R3 | 5 tests use live fixtures without `@pytest.mark.integration`, and nothing enforces the marker. | Med | Mark + add a collection-time guard |
| R4 | Test dependencies are undeclared: no pytest or httpx in the API files, no pytest in `uv.lock`. Every run installs them ad hoc, unpinned. | Med | Declare and pin |
| R5 | The portal backend's documented `unittest discover` command silently skips 26 pytest-style tests. | Med | Run with pytest |
| R6 | There is no single documented way to run the tests; the recipes live only in agent walkthroughs. | Med | Add a Makefile and `docs/testing.md` |
| R7 | The frontend `lint` script always rewrites files (`--fix`); there is no type-check script; and vue-tsc 1.8 crashes with TypeScript 5.9. | Low | Add `lint:check`, `type-check`, bump vue-tsc |
| R8 | No lint, format or type config for the Python services. | Low | ruff, report-only |
| R9 | Global state leaks between tests (unrestored monkeypatches, imports between test modules, `sys.path` hacks), and helpers are duplicated. | Low | Note only; fix only what blocks a green run |
| R10 | Stale or unpinned dependency files: API `requirements-dev.txt`, portal `requirements.txt`, frontend `package-lock.json`, unpinned hub pip installs. Python 3.9 and Node 20 are end-of-life. | Low | Note as follow-ups, not in scope |

### Decisions (from the interview)

- **CI runs on GitHub Actions, and the same commands run locally.** A root `Makefile` runs each suite inside a pinned public toolchain image, and the CI jobs only call the `make` targets.
- **The gate:** unit tests plus gitleaks block PRs to `main`. Integration tests come in a later, non-blocking phase (outlined below).
- **Lint and type-check are report-only.**
- **Legacy API scripts are deleted.** Coverage gaps they leave are a follow-up.
- **Test files stay in their service folders.** The root `tests/` folder is left untouched and reserved for future cross-service end-to-end tests.

## Approach

### Container conventions (all targets)

- **Python and Node versions match each service's production Dockerfile.** That means 3.11 from `services/api/Dockerfile:1` and 3.9 from `services/portal/backend/Dockerfile:1`, and Node 20 from the frontend Dockerfile. To upgrade a service, change its Dockerfile first, then change the matching Makefile image in the same PR.
- **Pinned images, by tag and digest.** Resolve each digest at implementation time with `docker buildx imagetools inspect <tag>`.

  | Suite | Image | Why |
  |---|---|---|
  | API | `ghcr.io/astral-sh/uv:<ver>-python3.11-bookworm` | Matches the production `python:3.11` |
  | Portal backend | `ghcr.io/astral-sh/uv:<ver>-python3.9-bookworm` | Matches production 3.9. The full bookworm image has gcc and libpq-dev, which the psycopg2 source build needs. |
  | Frontend | `node:20-alpine` | Matches the production builder stage |
  | Lint | `ghcr.io/astral-sh/ruff:<ver>` | |
  | Secret scan | `ghcr.io/gitleaks/gitleaks:v8.30.1` | Same version as the pre-commit hook |
  | JupyterHub | Built locally from `services/jupyterhub/Dockerfile` | |

- **Two phases per suite.**
  - **Install, with network.** Dependencies go into `.cache/ci/<suite>/` (already gitignored by the `.cache` rule).
  - **Test, with `--network none`.** Unit tests physically cannot reach a live service.
- **Containers run as the host user.** Use `--user $(id -u):$(id -g)`, `HOME=/tmp`, `PYTHONDONTWRITEBYTECODE=1` and `pytest -p no:cacheprovider`, so no root-owned files appear in the tree.
- **Mount only the service directory, never the repo root.** Then `.env`, `secrets.env` and `e2e-creds.txt` are invisible inside the container, as they are in CI. API mounts: `services/api` plus `services/postgres:ro`. Portal mounts: `services/portal`, because one test reads `../frontend/nginx.conf.template`.
- **Frontend `node_modules`** is shadowed by a mount from `.cache/ci/frontend/node_modules`, so the host `node_modules` is never touched.
- **Accepted trade-off:** `test_workflow_dag.py:157` (`skipif geteuid()!=0`) is skipped, because the container doesn't run as root. This is documented.

## Steps

There is one atomic conventional commit per step, and each commit is made only when you ask. Work happens on a **new branch `feat/ci-unit-gate` cut from `origin/main`**. That keeps the unrelated `dev_chinchien` merges and the six untracked artifact folders out of the PR.

**Phase 0: setup**
- Create the branch.
- Sync this plan and a `task.md` to `docs/artifacts/<YYYY-MM-DD-HHMMSS>-ci-unit-gate/`.
- Draft the ADR `docs/decisions/2026-10-16-ci-make-in-pinned-containers.md` from `docs/decisions/TEMPLATE.md`.
  - Options compared: Makefile + pinned images (chosen); native setup-python/node in CI; test stage in the service Dockerfiles.

**Phase 1: API (`services/api`)**
1. `test(api): remove legacy live-service scripts`. Delete these files from `tests/`:
   - `test_assay_api.py`
   - `test_download_dataset_api.py`
   - `test_minio.py`
   - `test_upload_dataset_api.py`
   - `test_delete_dataset_api.py`
   - `test_upload_dataset.py`

   Nothing imports them. Record any endpoint left uncovered as a follow-up in `task.md`.
2. `test(api): require integration marker on live-service fixtures`.
   - **Red:** add a `pytest_collection_modifyitems` hook to `tests/conftest.py`. It raises `pytest.UsageError` when a test uses `scratch_db`, `platform_db` or `minio_bucket` without the `integration` marker. Confirm it flags exactly these 5 tests: `test_migrate.py:194` and the 4 tests in `test_minio_downloader_objects.py`.
   - **Green:** mark those tests. Use a module-level `pytestmark` in `test_minio_downloader_objects.py`.
3. `build(api): declare pinned test dependencies and pytest config`.
   - New `requirements-test.txt`: `-r requirements-prod.txt`, plus exact pins for pytest 8.4.x and `httpx==0.28.1`.
   - `pyproject.toml` `[tool.pytest.ini_options]`: `testpaths=["tests"]`, `pythonpath=["src","."]`, `addopts="--strict-markers -ra"`.
   - Leave `requirements-dev.txt` untouched; it is noted as stale.
4. `build: add root Makefile with test-api target`. It runs `-m "not integration"` offline.
   - Verify: `make test-api` is green, and the skip and deselect counts look sane.

**Phase 2: portal backend (`services/portal/backend`)**
5. `fix(portal-backend): keep test runs off the working-dir SQLite` (finding R1).
   - **Red:** a subprocess test in the style of the existing `tests/test_live_db_guard.py`. It runs with no `DATABASE_PATH` in the backend dir, imports `tests` and then `app.models.db_model`, and asserts that `engine.url.database` is not `<backend>/plugin_registry.db`.
   - **Green:** in `tests/__init__.py`, after the existing `PORTAL_DB_HOST` guard, set `os.environ["DATABASE_PATH"]` unconditionally to a temp file. `__init__.py` is the right place because it runs before every test module under both pytest and unittest.
6. `build(portal-backend): add test dependency group`.
   - Run `uv add --group test 'pytest>=8.4,<9'` inside the 3.9 image. pytest 9 dropped Python 3.9 support.
   - Use a **non-default** group, so the production `uv sync --frozen` and `uv run` never install pytest.
   - Review that the `uv.lock` diff only adds pytest and its dependencies.
7. `build: add make test-portal-backend`. It runs `pytest tests`.
   - Verify: the count is about the `unittest discover` count plus 26.
   - Fix order-dependent failures (R9) only if they block a green run.

**Phase 3: frontend (`services/portal/frontend`)**
8. `build(frontend): bump vue-tsc and add type-check and lint:check scripts`.
   - Run `yarn add -D vue-tsc@^2.2.10` inside the node image, so `yarn.lock` is updated by Yarn 1.
   - Add `"type-check": "vue-tsc --noEmit -p tsconfig.json"` and `"lint:check": "eslint . --ignore-path .gitignore"`.
9. `build: add make test-frontend`. It runs `yarn install --frozen-lockfile`, then `yarn test` offline.

**Phase 4: remaining targets, CI, docs**
10. `build: add make test-jupyterhub, lint and gitleaks targets`.
    - `test-jupyterhub`: build the hub image, then pip-install a pinned pytest into `.cache/ci/hub`, then run offline.
    - `lint`: ruff check on the three Python services, plus `lint:check` and `type-check` on the frontend. The target collects failures and reports them.
    - `gitleaks`: `gitleaks git --log-opts=$(GITLEAKS_RANGE) --redact`, defaulting to `origin/main..HEAD`.
    - `test`: runs all four unit suites.
11. `ci: add unit-test gate workflow` in `.github/workflows/ci.yml`.
    - Triggers: `pull_request` to main, `push` to main, `workflow_dispatch`.
    - `permissions: contents: read`; concurrency that cancels superseded PR runs; actions pinned by SHA; `persist-credentials: false`; per-job timeouts; `ubuntu-24.04` runners.
    - Jobs, with stable names (they become required checks), each calling `make`:
      - `api unit tests`
      - `portal-backend unit tests`
      - `frontend unit tests`
      - `jupyterhub unit tests`
      - `lint (report-only)`: `continue-on-error` is set on the **steps**, so the job stays green and annotations still show.
      - `gitleaks (PR commits)`: PR only, `fetch-depth: 0`, scans `base.sha..head.sha`. It scans only the PR's commits, because past secrets in the public history would otherwise make every run fail. It uses the docker image, because `gitleaks-action` needs a paid licence for organisation repos.
    - No `actions/cache` in the first version; measure job times first.
    - **Run only the affected suites** (decided). A first `changes` job computes `git diff --name-only <base.sha>...<head.sha>` in plain shell, with no third-party action, and outputs one flag per suite. Each test job has `needs: changes` and `if: <flag> == 'true'`.
      - `services/api/**` and `services/postgres/**` → api
      - `services/portal/backend/**` → portal-backend
      - `services/portal/frontend/**` → frontend **and** portal-backend (one test reads `nginx.conf.template`)
      - `services/jupyterhub/**` → jupyterhub
      - `Makefile` and `.github/workflows/**` → all suites
      - Any other path, such as `docs/**` or `*.md`, runs no tests. gitleaks always runs on PRs, and lint runs when any code suite runs.
      - On `push` to main and on `workflow_dispatch`, every flag is true.
      - The workflow itself is never skipped by `on.*.paths`. Unneeded jobs are marked *skipped*, and GitHub counts a skipped required check as passing, so a docs-only PR is not left waiting on required checks.
    - **Skip draft PRs** (decided).
      - `pull_request` uses `types: [opened, synchronize, reopened, ready_for_review]`.
      - The `changes` and `gitleaks` jobs carry `if: github.event_name != 'pull_request' || !github.event.pull_request.draft`, so every downstream job is skipped while the PR is a draft.
      - CI runs on "Ready for review" and on every push after that.
      - A draft can't be merged, so the skipped required checks don't matter.
    - **No CI on plain `dev_*` pushes** (decided). Run `make test` locally before pushing; CI starts when the PR is opened.
12. `docs: add testing guide; accept ADR`.
    - New `docs/testing.md`: the make targets, what CI gates on, the safety rules (never run the portal tests inside the live container), and the root-only skip.
    - Link it from `README.md` and `docs/development.md`.
    - Mark the ADR as Accepted, and sync the artifacts.

**Phase 5: PR and gate**
- Run `make test lint` in a clean worktree (`git worktree add .worktrees/ci-verify HEAD`), which has no `.env`, no `node_modules` and no untracked files.
- Push and open the PR, with your go-ahead. Confirm all jobs are green.
- Then mark the 5 blocking checks as required on `main`, either in GitHub settings or with `gh api` after your explicit confirmation.

**Phase 6: integration (outline only; separate later PR, non-blocking)**
- Add `ci/compose.integration.yml` with `postgres:16` and the same MinIO release as `services/minio`, using throwaway credentials.
- `make test-api-integration` starts it, runs `-m integration`, then tears it down.
- CI job with `continue-on-error`.
- Later: the portal `PORTAL_TEST_DB_HOST` variant, and cross-service e2e tests in the root `tests/` folder.

## Critical files

- **Modify:**
  - `services/api/tests/conftest.py`
  - `services/api/pyproject.toml`
  - `services/api/tests/test_migrate.py`
  - `services/api/tests/test_minio_downloader_objects.py`
  - `services/portal/backend/tests/__init__.py`
  - `services/portal/backend/pyproject.toml` and `uv.lock`
  - `services/portal/frontend/package.json` and `yarn.lock`
  - `README.md`
  - `docs/development.md`
- **New:**
  - `Makefile`
  - `.github/workflows/ci.yml`
  - `services/api/requirements-test.txt`
  - a new portal test file (the R1 regression test)
  - `docs/testing.md`
  - the ADR
  - the artifact folder
- **Reuse:**
  - the existing `scratch_db`, `platform_db` and `minio_bucket` fixtures (`services/api/tests/conftest.py`)
  - the subprocess pattern in `services/portal/backend/tests/test_live_db_guard.py`
  - the `.cache` gitignore rule
  - the gitleaks version from `.pre-commit-config.yaml`

## Verification

- **Per suite, locally:**
  - `make test-api`, `make test-portal-backend`, `make test-frontend` and `make test-jupyterhub` each exit 0.
  - `git status` shows no new root-owned or untracked files.
  - `ls -l services/portal/backend/plugin_registry.db` shows its mtime unchanged after `make test-portal-backend`.
- **R1:** the new test fails before the `__init__.py` change and passes after it.
- **R3:** temporarily removing a marker makes collection fail with the guard's error.
- **Isolation:** the unit runs pass with `--network none` (built into the targets).
- **`make lint`** runs and reports the existing violations. It does not fail CI.
- **`make gitleaks`** on the branch is clean.
- **Clean worktree:** `make test` passes there.
- **Drafts:** a draft PR shows every job as skipped. Marking it "Ready for review" starts a full run.
- **Path filter:** a test PR that changes only a `.md` file runs `changes` and `gitleaks`, and every test job shows as skipped.
- **On GitHub:** all jobs pass on the PR. A deliberately failing unit test in a scratch commit turns the job red; drop that commit afterwards.

## Out of scope / follow-ups

- Rewriting the coverage lost with the legacy scripts.
- Cleaning up global state in tests (R9).
- Python 3.9 → 3.11+ for the portal backend, and the Node 20 upgrade.
- Pinning the hub pip installs and the unpinned API dependencies.
- Deleting the stale `package-lock.json`.
- Dependabot.
- Coverage reporting.
- PACS live scripts; Airflow DAG tests (gitignored).
- Rotating any secrets in the public git history.

## Process notes

- Plan mode currently allows writing only this file. The artifact sync to `docs/artifacts/` and the ADR draft (Phase 0) are the first actions after approval, as `AGENTS.md` requires.
- No Docker service images are changed, so no rebuild or restart of the running stack is needed.
