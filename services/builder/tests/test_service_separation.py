"""The builder is its own service, apart from the platform API, and the split is the security
boundary: the builder holds the host Docker socket and runs untrusted plugin builds with its own
environment, so the socket must not reach the API, and the API's credentials must not reach it.
Separate folders and images keep the code apart; these checks keep the compose wiring apart.
See docs/decisions/2026-10-21-builder-as-its-own-service.md.

Run from `services/builder/`:
    python -m pytest tests/test_service_separation.py
"""
import re
from pathlib import Path

import pytest
import yaml

SERVICE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = SERVICE_ROOT.parents[1]
DOCKER_SOCK = "/var/run/docker.sock"

# The API's credentials and handles the builder never needs. Plugin builds inherit the builder's
# environment, so any of these there would be readable by plugin code. The builder only verifies
# tokens with the realm's public key, so the `api` client's secret has no use there either.
API_ONLY = re.compile(r"^(POSTGRES_|JUPYTERHUB_|AIRFLOW_|SEEK_)|^(API_PUBLIC_URL|KEYCLOAK_CLIENT_SECRET)$")


def _service(path, name):
    return yaml.safe_load(path.read_text())["services"][name]


def _env(service):
    env = service.get("environment") or {}
    if isinstance(env, list):
        env = dict(item.split("=", 1) for item in env)
    return env


@pytest.fixture(scope="module")
def api():
    return _service(REPO_ROOT / "services" / "api" / "docker-compose.yml", "api")


@pytest.fixture(scope="module")
def root_builder():
    return _service(REPO_ROOT / "docker-compose.yml", "builder")


@pytest.fixture(scope="module")
def builder(root_builder):
    """The builder as the platform runs it: its own compose file plus the root compose's additions."""
    base = _service(SERVICE_ROOT / "docker-compose.yml", "builder")
    return {**base, "environment": {**_env(base), **_env(root_builder)},
            "volumes": base.get("volumes", []) + root_builder.get("volumes", [])}


def test_the_platform_runs_the_builder_from_its_own_service_folder(root_builder):
    assert root_builder["extends"] == {"file": "./services/builder/docker-compose.yml", "service": "builder"}


def test_only_the_builder_mounts_the_docker_socket(api, builder):
    assert not any(DOCKER_SOCK in v for v in api.get("volumes", []))
    assert any(v.startswith(f"{DOCKER_SOCK}:") for v in builder["volumes"])


def test_the_builder_gets_none_of_the_apis_credentials(builder):
    assert sorted(k for k in builder["environment"] if API_ONLY.search(k)) == []


def test_the_builder_connects_as_the_portal_role_not_the_superuser(builder):
    assert builder["environment"]["BUILDER_DB_USER"] == "portal"
