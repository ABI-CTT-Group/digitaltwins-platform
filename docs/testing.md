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
make lint                  # ruff + eslint + vue-tsc (a required check in CI)
make docs-check            # doc links, code map, util/SCRIPTS.md, agent pointer files
make gitleaks              # secret scan of origin/main..HEAD
```

To run part of a Python suite, pass pytest arguments:

```bash
make test-api PYTEST_ARGS="-q tests/test_models_api.py -k delete"
```

## Where the tests are

| Suite | Tests live in | Runner | Make target | CI job |
|---|---|---|---|---|
| API | `services/api/tests/test_*.py`, shared fixtures in `conftest.py` | pytest | `test-api` | `api unit tests` |
| Builder | `services/builder/tests/test_*.py`, SQL fixtures in `tests/fixtures/` | pytest | `test-builder` | `builder unit tests` |
| Portal frontend | `services/portal/frontend/src/**/__tests__/*.spec.ts`, next to the code they test | vitest | `test-frontend` | `frontend unit tests` |
| JupyterHub | `services/jupyterhub/tests/` | pytest, in the hub image | `test-jupyterhub` | `jupyterhub unit tests` |
| util | `util/tests/test_*.sh` | bash | `test-util` | `util unit tests` |
| Docs | `util/check_docs.py`, tested by `util/tests/test_check_docs.sh` | Python | `docs-check` | `docs check (report-only)` |
| PACS (manual) | `services/pacs/tests/` | Python scripts against a running Orthanc | none | none |

There are no automated tests for the Airflow DAGs, the nginx configs, the Keycloak realm template, SEEK, MinIO, HAPI FHIR or PostgreSQL init scripts, and no end-to-end tests. The root `tests/` folder is an empty placeholder.

## Writing a test

- **API:** add `services/api/tests/test_<area>.py`. Most unit tests stub outside services with `monkeypatch` or mocks. A test that needs a real Postgres or MinIO must use one of the live-service fixtures below and carry `@pytest.mark.integration`, or collection fails. The suite runs with `--strict-markers`, so a mistyped marker fails too.
- **Builder:** add `services/builder/tests/test_<area>.py`. The package's `tests/__init__.py` points the database at a temporary SQLite file and refuses to load when `BUILDER_DB_HOST` is set. Some tests read files outside the builder (see "How a run works"); if yours needs another one, mount it read-only in the `test-builder` target and add it to the builder CI filter.
- **Portal frontend:** put `<Name>.spec.ts` in a `__tests__/` folder beside the component or module. `yarn test` runs `vitest run` with the `test` block in `vite.config.ts`, which only picks up `src/**/__tests__/**/*.spec.ts` and mounts components with a real Vuetify (helpers in `src/testing/`).
- **util:** add `util/tests/test_<name>.sh`, ending with a non-zero exit on failure. `make test-util` runs every `test_*.sh` in that folder. Build temporary fixtures with `mktemp -d`, as `test_compose_file.sh` does.

## Manual tests (PACS)

`services/pacs/tests/` holds Python scripts that upload, pull, download and de-identify DICOM against a running Orthanc. They read `ORTHANC_URL`, `ORTHANC_USER` and `ORTHANC_PASSWORD`, and default to a local development Orthanc. They aren't in `make test` or CI. Run them only against a development stack: they write studies to whatever Orthanc they're pointed at.

## Docs check

`make docs-check` runs `util/check_docs.py` on the repo's tracked files. It fails when:
- a relative link in a Markdown file doesn't resolve (it skips `docs/artifacts/`, which is history, and `TEMPLATE.md` files);
- a folder in `services/` isn't named in [codemap.md](codemap.md);
- an entry in `util/` isn't listed in [util/SCRIPTS.md](../util/SCRIPTS.md);
- an agent pointer file (`CLAUDE.md`, `GEMINI.md`, `.github/copilot-instructions.md`, `.agents/rules/*.md`) holds more than its pointer to `AGENTS.md` ([ADR](decisions/2026-10-28-agents-md-single-source.md)).

Only tracked files are checked, piped into the container as a tar so `.env` and `secrets.env` never reach it. `git add` a new file before running the check.

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
| any `*.md` file, anything in `services/` or `util/` | docs |
| `Makefile`, `.github/workflows/` | all suites, and docs |
| anything else | no tests |

Gitleaks runs on every PR. It scans only the PR's own commits, not the full history.

A suite that isn't needed shows as *skipped*. GitHub counts a skipped required check as passing.

These checks block merging:
- `api unit tests`
- `builder unit tests`
- `frontend unit tests`
- `jupyterhub unit tests`
- `lint` (ruff, eslint and vue-tsc; runs when api, builder, frontend or jupyterhub code changes)
- `gitleaks (PR commits)`

`util unit tests` runs too, but isn't a required check.

`docs check (report-only)` never fails: read its log for broken links or missing map entries.

These six checks are required by the repo ruleset "CI required checks" (Settings → Rules). The ruleset matches checks by job `name:` in `.github/workflows/ci.yml`. If you rename a job, update the ruleset in the same change, or every PR will wait for a check that never reports.

## Safety rules

- **Never run the builder tests (`services/builder/tests/`) inside the live `builder` container,** or in any shell where `BUILDER_DB_HOST` is set. They drop and recreate every table. `services/builder/tests/__init__.py` refuses to load when `BUILDER_DB_HOST` is set, and it always points SQLite at a temporary file.
- Don't point the API integration tests at a production database. They need `CREATEDB` rights on whatever `POSTGRES_*` names.
