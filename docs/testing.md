# Testing

The unit tests run through one root `Makefile`. You get the same results locally and in CI, because the GitHub workflow (`.github/workflows/ci.yml`) only calls these targets.

You need Docker and GNU make. You don't need Python, Node, uv or a virtualenv on the host.

```bash
make test                  # all four unit suites
make test-api              # services/api                (pytest, Python 3.11)
make test-portal-backend   # services/portal/backend     (pytest, Python 3.9)
make test-frontend         # services/portal/frontend    (vitest, Node 20)
make test-jupyterhub       # services/jupyterhub         (pytest, hub image)
make lint                  # ruff + eslint + vue-tsc (report-only in CI)
make gitleaks              # secret scan of origin/main..HEAD
```

To run part of a Python suite, pass pytest arguments:

```bash
make test-api PYTEST_ARGS="-q tests/test_models_api.py -k delete"
```

## How a run works

Each suite runs in a pinned toolchain image: tag plus digest, at the same Python or Node version as the service's production Dockerfile. A run has two steps:

1. **Install, with network access.** Dependencies are installed into `.cache/ci/`, which is gitignored and reused between runs. The sources are:
   - API: `services/api/requirements-test.txt`
   - Portal backend: `uv.lock` plus its `test` dependency group
   - Frontend: `yarn.lock`, installed into a cached `node_modules`. Your own `node_modules` is never used or changed.
2. **Test, with `--network none`.** Only the service's own directory is mounted, never the repo root. The tests can't reach live Postgres, MinIO, Keycloak and so on, and they can't see `.env` or `secrets.env`.

Containers run as your user, so no root-owned files end up in the tree. Because the tests don't run as root, `test_workflow_dag.py`'s root-only `chown` test is skipped.

If you upgrade a service's Python or Node version, change its Dockerfile and the matching image in the `Makefile` in the same PR.

## Unit vs integration tests (API)

API tests that need a live Postgres or MinIO are marked `@pytest.mark.integration`, and `make test-api` deselects them. `tests/conftest.py` makes collection fail if a test uses a live-service fixture without the marker. Those fixtures are:
- `scratch_db`
- `platform_db`
- `minio_bucket`
- `tool_bucket`
- `s3`

Integration tests aren't in CI yet. To run them by hand against a local stack, see the fixtures' docstrings in `services/api/tests/conftest.py`. They create, then drop, a throwaway database or bucket.

## What CI checks

The workflow runs:
- on PRs to `main`; draft PRs are skipped until they're marked "Ready for review"
- on pushes to `main`
- manually, from the Actions tab

On a PR, only the suites whose files changed run. "Changed" means the whole PR's diff against `main`, not just the latest commit:

| Change touches | Jobs that run |
|---|---|
| `services/api/`, `services/postgres/` | api |
| `services/portal/backend/` | portal-backend |
| `services/portal/frontend/` | frontend and portal-backend |
| `services/jupyterhub/` | jupyterhub |
| `Makefile`, `.github/workflows/` | all suites |
| anything else (e.g. docs) | no tests |

Gitleaks runs on every PR. It scans only the PR's own commits, not the full history.

A suite that isn't needed shows as *skipped*. GitHub counts a skipped required check as passing.

These checks block merging:
- `api unit tests`
- `portal-backend unit tests`
- `frontend unit tests`
- `jupyterhub unit tests`
- `gitleaks (PR commits)`

`lint (report-only)` shows its findings as annotations but never fails.

These five checks are required by the repo ruleset "CI required checks" (Settings → Rules). The ruleset matches checks by job `name:` in `.github/workflows/ci.yml`. If you rename a job, update the ruleset in the same change, or every PR will wait for a check that never reports.

## Safety rules

- **Never run the portal backend tests inside the live `portal-backend` container,** or in any shell where `PORTAL_DB_HOST` is set. The suite drops and recreates every table. `tests/__init__.py` refuses to load when `PORTAL_DB_HOST` is set, and it always points SQLite at a temporary file.
- Don't point the API integration tests at a production database. They need `CREATEDB` rights on whatever `POSTGRES_*` names.
