# Run tests through a Makefile in pinned toolchain containers, locally and in CI

- **Date:** 2026-10-16
- **Status:** Accepted

## Context

The platform has four automated unit-test suites: the API (pytest, Python 3.11), the portal backend (unittest/pytest, Python 3.9), the portal frontend (vitest, Node 20) and JupyterHub (pytest). There was no CI. The suites ran through ad-hoc `docker run` recipes that lived only in feature walkthroughs, and some of those runs touched live data:

- A portal-backend run wiped the working-directory SQLite registry.
- Legacy API scripts wrote to the live Postgres and MinIO through the repo `.env`.

Developer machines don't have the service toolchains (no uv, and Node 18 is too old for vitest 3), so every run needs a container anyway. We need a gate on PRs to `main` that gives the same result locally and on GitHub, and that cannot reach live services.

## Alternatives Considered

### Option A: Root Makefile running each suite in a pinned public toolchain image
CI jobs call the same `make` targets.
- Pros:
  - One definition per suite, so local and CI runs behave the same.
  - Images are pinned by tag and digest, so runs are reproducible.
  - Unit runs use `--network none` and mount only the service directory, so they cannot reach live services or see `.env`.
  - No change to the production Dockerfiles.
- Cons:
  - Tests run on the production Python/Node version but not in the exact production image.
  - Image digests must be bumped by hand.

### Option B: GitHub-native toolchains (setup-python, setup-uv, setup-node), with a Docker Makefile for local runs
- Pros:
  - The most conventional GitHub setup.
  - Best built-in caching and fastest runs.
- Cons:
  - Each step is defined twice, once for CI and once locally, and the two drift.
  - System build dependencies (psycopg2 needs gcc and libpq) differ between the runner and the containers.

### Option C: A `test` stage in each service Dockerfile
- Pros:
  - Tests run in exactly the image that ships.
- Cons:
  - Slow: the portal-backend image installs Volta, Node and the Docker CLI.
  - Every Dockerfile edit can break CI.
  - A test stage has to be added to each production Dockerfile.

## Decision

Option A. The toolchain images are:
- API: `ghcr.io/astral-sh/uv:*-python3.11-bookworm`
- Portal backend: `ghcr.io/astral-sh/uv:*-python3.9-bookworm`
- Frontend: `node:20-alpine`
- Lint: the ruff image
- Secret scan: the gitleaks image, at the same version as the pre-commit hook
- JupyterHub: the hub image built from its Dockerfile

Each image matches the Python or Node version of its service's production Dockerfile.

The GitHub workflow:
- Runs on PRs to `main` (drafts skipped), on pushes to `main` and on manual dispatch.
- Runs only the suites a change touches. A first job computes the changed paths, and skipped jobs count as passing for required checks.
- Blocks on the unit suites and on a gitleaks scan of the PR's commits. Lint and type-check are report-only. (Lint became a required check on 2026-10-28: [2026-10-28-lint-required-check.md](2026-10-28-lint-required-check.md).)

## Consequences

- `make test` is the single documented way to run the unit suites. The same targets are the CI contract.
- Upgrading a service's Python or Node version means changing its Dockerfile and the matching Makefile image in the same PR.
- Integration tests that need Postgres or MinIO are out of the gate for now. They come in a later phase using a compose file that `make` starts both locally and in CI.
- Tests that need root (`test_workflow_dag.py` `skipif geteuid()!=0`) are skipped, because the containers run as the invoking user so they don't leave root-owned files.
- Gitleaks scans only the PR's commits, not the full history. Secrets already in the public history must be handled by rotating them, outside CI.
- Decided during implementation: ruff runs with an explicit `--select E4,E7,E9,F` (pyflakes plus syntax and statement errors). Ruff 0.17's defaults also enable import sorting and pyupgrade rules: 1,330 findings, mostly style, against 154 bug-class ones. A pinned rule set keeps the report actionable, and a future ruff upgrade can't silently change what is checked.
