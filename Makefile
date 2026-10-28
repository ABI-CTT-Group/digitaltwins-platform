# Test entry points, shared by local runs and CI (.github/workflows/ci.yml).
# Each suite runs in a pinned toolchain image matching its service's production
# Dockerfile. Dependencies install with network into .cache/ci/; tests then run
# with --network none, mounting only the service directory (never the repo root,
# so .env and secrets.env are not visible). See docs/testing.md.

SHELL := bash
.SHELLFLAGS := -euo pipefail -c

UID := $(shell id -u)
GID := $(shell id -g)
CACHE := $(CURDIR)/.cache/ci

# Pinned by tag and digest; resolve a new digest with: docker buildx imagetools inspect <tag>
PY311_IMAGE := ghcr.io/astral-sh/uv:0.9.30-python3.11-bookworm@sha256:58683a39536f1f4ed2e1dd79cf155edccfb47731aba8964bd0312aac942126cf
NODE_IMAGE  := node:20.20.2-alpine@sha256:fb4cd12c85ee03686f6af5362a0b0d56d50c58a04632e6c0fb8363f609372293
RUFF_IMAGE  := ghcr.io/astral-sh/ruff:0.17.1@sha256:eae3102808b46de58204237a3433001cae4d45d832f31be1c8121f7145a62661
GITLEAKS_IMAGE := ghcr.io/gitleaks/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f
HUB_IMAGE   := dtp-ci-jupyterhub

PYTEST_ARGS ?=
RUFF_FORMAT ?= concise
GITLEAKS_RANGE ?= origin/main..HEAD

RUN := docker run --rm --init --user $(UID):$(GID) -e HOME=/tmp \
	-e PYTHONDONTWRITEBYTECODE=1 -e UV_CACHE_DIR=/cache/uv -e UV_PYTHON_DOWNLOADS=never \
	-v $(CACHE):/cache
OFFLINE := --network none
# The frontend's node_modules comes from the cache, so the host's node_modules is never used or changed.
FE := -v $(CURDIR)/services/portal/frontend:/w -v $(CACHE)/frontend/node_modules:/w/node_modules -w /w

.PHONY: test test-api test-builder test-frontend test-jupyterhub test-util frontend-deps cache-dirs \
	lint lint-python lint-frontend gitleaks docs-check

test: test-api test-builder test-frontend test-jupyterhub test-util

# Created up front so docker doesn't create missing mount points as root.
cache-dirs:
	mkdir -p $(CACHE)/uv $(CACHE)/yarn $(CACHE)/frontend/node_modules services/portal/frontend/node_modules

test-api: cache-dirs
	$(RUN) -v $(CURDIR)/services/api:/w:ro -w /w $(PY311_IMAGE) sh -c \
	  'uv venv -q --allow-existing /cache/api/venv && uv pip install -q --python /cache/api/venv -r requirements-test.txt'
	$(RUN) $(OFFLINE) -v $(CURDIR)/services/api:/w/services/api -v $(CURDIR)/services/postgres:/w/services/postgres:ro \
	  -w /w/services/api $(PY311_IMAGE) \
	  /cache/api/venv/bin/python -m pytest -m "not integration" -p no:cacheprovider $(PYTEST_ARGS)

# Also mounted, read-only: the portal-frontend nginx template (a test checks which locations reach
# the builder), the root and API compose files (tests check the builder's environment and the
# Docker socket mount there; they hold no secrets) and the API's migration runner and Keycloak
# verifier (the builder's copies must match them).
test-builder: cache-dirs
	$(RUN) -v $(CURDIR)/services/builder:/w:ro -w /w $(PY311_IMAGE) sh -c \
	  'uv venv -q --allow-existing /cache/builder/venv && uv pip install -q --python /cache/builder/venv -r requirements-test.txt'
	$(RUN) $(OFFLINE) -v $(CURDIR)/services/builder:/w/services/builder \
	  -v $(CURDIR)/services/portal/frontend/nginx.conf.template:/w/services/portal/frontend/nginx.conf.template:ro \
	  -v $(CURDIR)/docker-compose.yml:/w/docker-compose.yml:ro \
	  -v $(CURDIR)/services/api/docker-compose.yml:/w/services/api/docker-compose.yml:ro \
	  -v $(CURDIR)/services/api/src/digitaltwins/postgres/migration_runner.py:/w/services/api/src/digitaltwins/postgres/migration_runner.py:ro \
	  -v $(CURDIR)/services/api/src/digitaltwins/core/keycloak_verifier.py:/w/services/api/src/digitaltwins/core/keycloak_verifier.py:ro \
	  -w /w/services/builder $(PY311_IMAGE) \
	  /cache/builder/venv/bin/python -m pytest -p no:cacheprovider $(PYTEST_ARGS)

frontend-deps: cache-dirs
	$(RUN) $(FE) $(NODE_IMAGE) yarn install -s --frozen-lockfile --non-interactive --cache-folder /cache/yarn

test-frontend: frontend-deps
	$(RUN) $(OFFLINE) $(FE) $(NODE_IMAGE) yarn -s test

# The hub test loads jupyterhub_config.py with the hub's own packages, so it runs in the hub image.
test-jupyterhub: cache-dirs
	docker build -q -t $(HUB_IMAGE) services/jupyterhub >/dev/null
	$(RUN) --entrypoint pip $(HUB_IMAGE) install -q --disable-pip-version-check --upgrade --target /cache/hub/site pytest==8.4.2
	$(RUN) $(OFFLINE) -e PYTHONPATH=/cache/hub/site -v $(CURDIR)/services/jupyterhub:/w -w /w --entrypoint python \
	  $(HUB_IMAGE) -m pytest -p no:cacheprovider -ra tests $(PYTEST_ARGS)

# Shell tests for util/ (which compose files gen-env.sh merges, and the docs checker). Also mounted,
# read-only: the two Airflow compose files the test checks for the GPU reservation. Neither holds secrets.
test-util: cache-dirs
	$(RUN) $(OFFLINE) -v $(CURDIR)/util:/w/util:ro \
	  -v $(CURDIR)/services/airflow/docker-compose.yml:/w/services/airflow/docker-compose.yml:ro \
	  -v $(CURDIR)/services/airflow/gpu.override.yml:/w/services/airflow/gpu.override.yml:ro \
	  -w /w $(PY311_IMAGE) bash -c 'rc=0; for t in util/tests/test_*.sh; do bash "$$t" || rc=1; done; exit $$rc'

# Static checks; report-only in CI for now. Runs both, fails if either finds problems.
# ruff is pinned to the bug-class rules (pyflakes + syntax/statement errors), not style.
lint:
	$(MAKE) -k lint-python lint-frontend

lint-python:
	docker run --rm --user $(UID):$(GID) $(OFFLINE) -v $(CURDIR)/services:/w/services:ro -w /w $(RUFF_IMAGE) \
	  check --no-cache --select E4,E7,E9,F --output-format=$(RUFF_FORMAT) services/api services/builder services/jupyterhub

lint-frontend: frontend-deps
	$(RUN) $(OFFLINE) $(FE) $(NODE_IMAGE) sh -c 'rc=0; yarn -s lint:check || rc=1; yarn -s type-check || rc=1; exit $$rc'

# Docs links, the code map, util/SCRIPTS.md and agent pointer files (util/check_docs.py). Only tracked
# files go in, piped as a tar, so .env and secrets.env never reach the container; stage new files first.
# --no-recursion keeps submodules as empty folders.
docs-check:
	git ls-files -z | while IFS= read -r -d '' f; do if [ -e "$$f" ]; then printf '%s\0' "$$f"; fi; done \
	  | tar --null --no-recursion -T - -cf - \
	  | docker run --rm -i --user $(UID):$(GID) $(OFFLINE) $(PY311_IMAGE) \
	    sh -c 'mkdir /tmp/repo && tar -xf - -C /tmp/repo && python /tmp/repo/util/check_docs.py /tmp/repo'

# Scans commits in GITLEAKS_RANGE (not the full history, which predates the hook).
gitleaks:
	docker run --rm --user $(UID):$(GID) -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0='*' \
	  -v $(CURDIR):/repo:ro $(GITLEAKS_IMAGE) git --log-opts="$(GITLEAKS_RANGE)" --redact -v --exit-code 1 /repo
