# The builder as its own service, in services/builder

- **Date:** 2026-10-21
- **Status:** Accepted. Supersedes, in part, [2026-10-20-merge-portal-backend-into-api-codebase](2026-10-20-merge-portal-backend-into-api-codebase.md): the code's location and the CI layout change; its security analysis stands.

## Context

The 2026-10-20 decision moved the portal backend into the platform API's folder as the `builder` package. It kept the builder as its own service, built from a second target of the API's Dockerfile. The goal was one codebase: one place for code, one image definition, one test suite, one dependency set.

The same decision made the builder's security boundary a rule: the builder may not share code, image contents or environment with the API. Once that was enforced, the shared folder held nothing shared:

- **Code:** the builder imports neither the API's `app` nor its `digitaltwins` package. Tests forbade both.
- **Image:** the builder image contained none of the API's code and did not derive from the API's stage.
- **Dependencies:** the builder installed the API's whole `requirements-prod.txt`, including packages it never imports (`python-irodsclient`, `pydicom`). So an API dependency change rebuilt the builder image for nothing.
- **Convention:** every other service has its own `services/<name>/` folder with its own `docker-compose.yml`. The builder had a `docker-compose.builder.yml` beside the API's and a dual-target Dockerfile.

## Alternatives Considered

### Option A: keep the builder in services/api
- Pros: one test job; no further move.
- Cons: everything above. The co-location is nominal and costs dependency coupling and an odd layout.

### Option B (chosen): its own service folder, services/builder
- Pros:
  - It matches the repo's convention.
  - The security boundary becomes structural: separate folder, build context, Dockerfile and requirements, so there is nothing to import or copy across.
  - The builder pins only what it uses.
- Cons:
  - A required CI check comes back.
  - Unifying the Keycloak verifier or migrations with the API later means installing the API's `digitaltwins` package rather than importing it in place.

## Decision

Option B.

- **Layout:** `services/builder/` holds `app/` (the package), `tests/`, `Dockerfile`, `requirements.txt`, `requirements-test.txt`, `pyproject.toml` (pytest only), `docker-compose.yml` and `README.md`.
  - The package is `app` (`app.main:app`), as in `services/api/app` and the old portal backend. `services/builder/builder/` would repeat the name, and a flat layout would turn `models`, `utils` and `client` into generic top-level modules.
  - The container works in `/app`, as the portal backend did.
- **Dependencies:** the builder pins its own, at the versions its tests run against. That includes `sparc-me`'s spreadsheet stack (`openpyxl`, `pandas`, `styleframe`), which otherwise resolves to versions that fail on import.
- **Tests:** `make test-builder` and CI's **"builder unit tests"**. The repo ruleset swaps "portal-backend unit tests" for it.
- **Separation tests:** `services/builder/tests/test_service_separation.py` keeps the compose checks:
  - the Docker socket is mounted on `builder` only
  - the builder gets none of the API's credentials
  - the builder connects as the `portal` role
  - the root compose extends `services/builder/docker-compose.yml`

  The image-target and cross-import checks are gone: separate folders and build contexts make those failures impossible.
- **Unchanged:**
  - the service name `builder` and the path `/api/builder/...`
  - the `BUILDER_*` variables and the kept `portal` schema, role and volumes
  - Python 3.11
  - the HTTP gui-tool lookup from the API
  - the API service itself, whose Dockerfile, requirements and test run are back to how they were before the builder arrived

## Consequences

- Each service builds, pins and tests on its own. A change to one doesn't rebuild or retest the other, except through the compose files both read.
- Five required CI checks again: the ruleset needs "builder unit tests" in place of "portal-backend unit tests" before this merges.
- The security position is unchanged from the 2026-10-20 decision: builds are still not sandboxed, and the builder still holds the host Docker socket. The follow-ups recorded there still apply.
