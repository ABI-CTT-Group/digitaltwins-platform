# Plan: move the builder out of services/api into its own service folder, services/builder

## Context

On branch `refactor/merge-portal-backend-into-api` (4 local, unpushed commits), the portal backend became the `builder` service. Its code lives in `services/api/builder`, with a second Dockerfile target and a `docker-compose.builder.yml` side file.

A review found that the shared folder buys almost nothing:
- **Code:** the builder imports neither `app` nor `digitaltwins`, and the separation tests forbid it.
- **Image:** the builder image holds no API code.
- **Dependencies:** the builder installs the API's whole `requirements-prod.txt`, including packages it never uses (`python-irodsclient`, `pydicom`). An API dependency bump therefore changes the builder image too.
- **Convention:** every other service has its own `services/<name>/` folder and `docker-compose.yml`.

The user chose:
- **Location:** a separate service folder, `services/builder`, with the code in `services/builder/app/`. That matches `services/api/app/` and the old portal backend's `app/`. `services/builder/builder/` would stutter, and a flat layout would turn `models`, `utils`, `client` and similar folders into generic top-level modules.
- **History:** a new commit on top of the 4 (not a rewrite).
- **CI:** an own job, "builder unit tests".

**Unchanged from the branch:**
- the service name `builder` and the public path `/api/builder/{tools,workflow}`
- the `BUILDER_*` / `PLATFORM_DOMAIN` / `KEYCLOAK_PUBLIC_URL` env vars, and the kept `portal` schema, role and volumes
- Python 3.11
- the HTTP gui-tool lookup from the API
- the four separations, now enforced by layout plus the compose tests

## Target layout

```
services/builder/
  app/                the package (was services/api/builder; inside unchanged: main.py, router/, engine/, services/, models/, database/, client/, cli/, utils/)
  tests/              was services/api/tests/builder_tests/ (a package again: imports `tests.…`)
  Dockerfile          single stage: today's `builder` target (python:3.11-slim + git, Volta node 22/yarn, docker-ce-cli + compose plugin)
  requirements.txt    only what builder/ imports (pins taken from the versions tested today)
  requirements-test.txt  -r requirements.txt + pytest==8.4.2
  pyproject.toml      [tool.pytest.ini_options] only: testpaths=["tests"], pythonpath=["."]
  docker-compose.yml  was services/api/docker-compose.builder.yml (build context `.`, no target)
  .gitignore          runtime files: /tmp/, /app.log, /plugin_registry.db, /data/, /datasets_tool/, /datasets_workflow/
  README.md           was services/api/docs/builder.md, adjusted
```

The package is `app`, so imports change `builder.` → `app.`, including the `mock.patch("builder.…")` strings and the CLI usage lines (`python -m app.cli.<name>`). uvicorn runs `app.main:app`. The container goes back to the old portal backend's paths: `WORKDIR /app`, `PYTHONPATH=/app`, and `portal_datasets` mounted at `/app/data`. `DATABASE_PATH=/data/...` and the other mounts are unchanged. The API also has a top-level `app`, but the two never share a path: separate folders, images and test runs.

## Steps (tests first where behaviour is pinned)

1. **Move, with history kept.**
   - `git mv services/api/builder services/builder/app`
   - `git mv services/api/tests/builder_tests services/builder/tests`
   - `git mv services/api/docker-compose.builder.yml services/builder/docker-compose.yml`
   - `git mv services/api/docs/builder.md services/builder/README.md`
   - `git mv services/api/requirements-builder.txt services/builder/requirements.txt`, then trim it to the builder's own pins: no `-r requirements-prod.txt`. List the packages explicitly:
     - fastapi, uvicorn[standard], python-multipart, python-dotenv, psycopg2-binary, requests, urllib3, boto3
     - python-jose[cryptography], sparc-me, fhir-cda, digitaltwins-on-fhir
     - sqlalchemy, httpx, python-keycloak, pyyaml

     Each takes the version installed today, so the test results stay comparable.
2. **Imports:** `builder.` → `app.` in the package and the tests, and `builder_tests.` → `tests.` in the tests. Repoint the tests' path constants:
   - `BACKEND_ROOT` becomes `services/builder` (`parents[1]`).
   - The live-DB guard test goes back to `cwd=BACKEND_ROOT` with `import tests`.
   - The nginx template path goes back to `parents[3] / "services/portal/frontend/nginx.conf.template"`.
   - The "Run from" docstrings become `services/builder/`.
3. **Separation tests:** move `services/api/tests/test_service_separation.py` to `services/builder/tests/test_service_separation.py` and keep only the compose checks:
   - only `builder` mounts the Docker socket; `api` doesn't
   - the builder's env has none of `POSTGRES_*`, `JUPYTERHUB_*`, `AIRFLOW_*`, `SEEK_*` or `API_PUBLIC_URL`
   - `BUILDER_DB_USER=portal`
   - the root `builder` extends `./services/builder/docker-compose.yml`

   The Dockerfile-target and cross-import tests are dropped. They can't fail any more: separate build contexts and folders. Red first: point the test at the new paths before moving the compose file.
4. **Clean up my own mess:** remove the ignored runtime files that the builder tests left in `services/api` (`app.log`, `datasets_tool/`, `datasets_workflow/`, `tmp/` if present). Look at each first; they're untracked and generated by the test runs.
5. **Restore the API to its pre-builder state** (from `refactor/api-prefix-and-rename`):
   - `services/api/Dockerfile`: single stage again.
   - `services/api/docker-compose.yml`: drop `target: api` and keep `BUILDER_URL`.
   - `requirements-test.txt` back to `-r requirements-prod.txt` + pytest + httpx.
   - Remove the builder lines from `services/api/.gitignore`.
   - Drop the README pointer, or repoint it to `services/builder/README.md`.
6. **Root `docker-compose.yml`:** `builder` extends `./services/builder/docker-compose.yml`. The rest is unchanged: `BUILDER_DB_*`, `depends_on: database`, and portal-frontend's `depends_on: builder`.
7. **Makefile:**
   - New target `test-builder`: `PY311_IMAGE`, a venv at `/cache/builder/venv` installed from `services/builder/requirements-test.txt`. Tests run with `--network none`, mounting `services/builder`, plus read-only mounts of `services/portal/frontend/nginx.conf.template`, the root `docker-compose.yml` and `services/api/docker-compose.yml`.
   - Add it to `test` and `.PHONY`.
   - `test-api` goes back to its original mounts.
   - `lint-python` adds `services/builder`.
8. **CI (`.github/workflows/ci.yml`):**
   - `api` filter back to `^services/(api|postgres)/`.
   - New `builder` filter: `^services/builder/|^services/portal/frontend/nginx\.conf\.template$|^docker-compose\.yml$|^services/api/docker-compose\.yml$`.
   - New job `builder` named **"builder unit tests"** running `make test-builder`; add it to `all` and `code`.
   - Ruleset command for an admin (not run): replace "portal-backend unit tests" with "builder unit tests" in ruleset 25213776, using the `jq` approach already in the walkthrough.
9. **Docs and code comments** (every mention of the old layout gets updated):
   - `services/api/builder/...` → `services/builder/app/...`, and `python -m builder.cli.…` → `python -m app.cli.…`, and `docker-compose.builder.yml` → `services/builder/docker-compose.yml`.
   - "`services/api/Dockerfile`, target `builder`" → `services/builder/Dockerfile`, and `services/api/docs/builder.md` → `services/builder/README.md`.
   - Files to touch:
     - the comments in the root compose and the builder compose
     - `util/README.md` (arm64 note)
     - the frontend `utils.ts` comment
     - `docs/testing.md` (add `make test-builder`, the filter table, required checks: "builder unit tests")
     - `services/nginx/README.md`
     - `services/portal/docs/{deployment-guide,plugin-system-architecture}.md`
     - `services/keycloak/REALM.md`
     - `docs/deployment.md` (upgrade section, build command unchanged: `api builder portal-frontend`)
   - Also:
     - `services/portal/docs/deployment-guide.md`: the CLI commands become `docker compose run --rm builder python -m app.cli.migrate_sqlite_to_postgres`.
     - Comments in the builder's own code that cite `builder.*` modules or the merge ADR.
     - `services/api/app/routers/dashboard.py`: the comment that names the builder.
   - Gate: `git grep -nE "services/api/builder|docker-compose\.builder|requirements-builder|builder_tests|api/docs/builder|builder\.(main|cli|engine|models|router|services|client|database|utils)\b"` over the live tree returns nothing, apart from the artifacts and decisions.
10. **ADR:**
   - New `docs/decisions/2026-10-21-builder-as-its-own-service.md`, which supersedes the 10-20 merge ADR in part. It records why the shared folder was empty (no shared code, image or dependencies), the move to `services/builder`, the own CI job, and that the security analysis stands unchanged.
   - Set the 10-20 merge ADR's status to "Superseded in part by …".
   - Code comments that cite the merge ADR cite the new one.
11. **Artifacts:** a new folder `docs/artifacts/<YYYY-MM-DD-HHMMSS>-builder-own-service/` with `implementation_plan.md`, `tasks.md` and `walkthrough.md`. Synced immediately and after each update; no secrets, local paths or local live details.

## Commits (local only)

1. `refactor(builder)!: move the builder into its own service folder, services/builder`: steps 1–9 (code, tests, Dockerfile, compose, Makefile, CI, references).
2. `docs: …`: the ADR, the README adjustments and the artifacts.

Each commit leaves `make test` green.

## Verification

- `make test`
  - expected: api ≈ 362 (361 + the `BUILDER_URL` default test)
  - builder ≈ 216 (208 moved + 3 new + the compose separation tests)
  - frontend 162, hub 5
- `make lint-python`: 136 findings, unchanged. `make gitleaks` over the new commits.
- `docker compose build api builder`, then inspect both images:
  - the API image is back to its original contents
  - the builder image has git, Node and docker, and holds `app/` (the builder's) only
- `docker compose config -q`, with key names only and **never** `config <service>` (it printed a dependency's password last time).
- Live (the stack is running): `docker compose up -d builder api`, then repeat the short matrix:
  - `/api/builder/*` returns the builder's 401
  - authenticated Tool Hub list, metadata, logs and SSE
  - upload-source returns 422
  - the GUI assay launch works
  - the builder CLIs `--dry-run` connect as `portal`
- Rename gate (step 8) and a relative-link check on the edited markdown.

## Flagged

- The ruleset change is now a **swap**: "portal-backend unit tests" out, "builder unit tests" in. It must happen before merge.
- The pre-existing builder bugs and the unsandboxed builds stay as recorded in the merge ADR.
