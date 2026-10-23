# Testing

The unit tests run through one root `Makefile`. You get the same results locally and in CI, because the GitHub workflow (`.github/workflows/ci.yml`) only calls these targets.

You need Docker and GNU make. You don't need Python, Node, uv or a virtualenv on the host.

```bash
make test                  # all five unit suites
make test-api              # services/api                (pytest, Python 3.11)
make test-builder          # services/builder            (pytest, Python 3.11)
make test-frontend         # services/portal/frontend    (vitest, Node 20)
make test-jupyterhub       # services/jupyterhub         (pytest, hub image)
make test-util             # util/                       (bash, Python 3.11 image)
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
   - Builder: `services/builder/requirements-test.txt`
   - Frontend: `yarn.lock`, installed into a cached `node_modules`. Your own `node_modules` is never used or changed.
2. **Test, with `--network none`.** Only the service's own directory is mounted, never the repo root. (`make test-builder` also mounts five files read-only: the portal-frontend nginx template and the root and API `docker-compose.yml`, which the builder's template and service-separation tests check, and the API's `migration_runner.py` and `keycloak_verifier.py`, which the builder's copies must match. None holds secrets.) The tests can't reach live Postgres, MinIO, Keycloak and so on, and they can't see `.env` or `secrets.env`.

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
| `services/api/`, `services/postgres/` | api (and builder, for `services/api/docker-compose.yml`, `services/api/src/digitaltwins/postgres/migration_runner.py` and `services/api/src/digitaltwins/core/keycloak_verifier.py`) |
| `services/builder/`, root `docker-compose.yml` | builder |
| `services/portal/frontend/nginx.conf.template` | frontend and builder |
| the rest of `services/portal/frontend/` | frontend |
| `services/jupyterhub/` | jupyterhub |
| `util/`, `services/airflow/docker-compose.yml`, `services/airflow/gpu.override.yml` | util |
| `Makefile`, `.github/workflows/` | all suites |
| anything else (e.g. docs) | no tests |

Gitleaks runs on every PR. It scans only the PR's own commits, not the full history.

A suite that isn't needed shows as *skipped*. GitHub counts a skipped required check as passing.

These checks block merging:
- `api unit tests`
- `builder unit tests`
- `frontend unit tests`
- `jupyterhub unit tests`
- `gitleaks (PR commits)`

`util unit tests` runs too, but isn't a required check.

`lint (report-only)` shows its findings as annotations but never fails.

These five checks are required by the repo ruleset "CI required checks" (Settings → Rules). The ruleset matches checks by job `name:` in `.github/workflows/ci.yml`. If you rename a job, update the ruleset in the same change, or every PR will wait for a check that never reports.

## Safety rules

- **Never run the builder tests (`services/builder/tests/`) inside the live `builder` container,** or in any shell where `BUILDER_DB_HOST` is set. They drop and recreate every table. `services/builder/tests/__init__.py` refuses to load when `BUILDER_DB_HOST` is set, and it always points SQLite at a temporary file.
- Don't point the API integration tests at a production database. They need `CREATEDB` rights on whatever `POSTGRES_*` names.
