"""The API and the builder share this codebase but run as separate services, and the split is the
security boundary: the builder holds the host Docker socket and runs untrusted plugin builds with its
own environment, so none of that may reach the API, and none of the API's credentials may reach it.
See docs/decisions/2026-10-20-merge-portal-backend-into-api-codebase.md.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

API_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = API_ROOT.parents[1]
DOCKER_SOCK = "/var/run/docker.sock"

# The API's credentials and handles the builder never needs. Plugin builds inherit the builder's
# environment, so any of these there would be readable by plugin code.
API_ONLY = re.compile(r"^(POSTGRES_|JUPYTERHUB_|AIRFLOW_|SEEK_)|^API_PUBLIC_URL$")


def _service(path, name):
    return yaml.safe_load(path.read_text())["services"][name]


def _env(service):
    env = service.get("environment") or {}
    if isinstance(env, list):
        env = dict(item.split("=", 1) for item in env)
    return env


@pytest.fixture(scope="module")
def api():
    return _service(API_ROOT / "docker-compose.yml", "api")


@pytest.fixture(scope="module")
def builder():
    """The builder as the platform runs it: the base file plus the root compose's additions."""
    base = _service(API_ROOT / "docker-compose.builder.yml", "builder")
    root = _service(REPO_ROOT / "docker-compose.yml", "builder")
    assert root["extends"] == {"file": "./services/api/docker-compose.builder.yml", "service": "builder"}
    return {**base, "environment": {**_env(base), **_env(root)},
            "volumes": base.get("volumes", []) + root.get("volumes", [])}


# ── Compose ───────────────────────────────────────────────────────────


def test_only_the_builder_mounts_the_docker_socket(api, builder):
    assert not any(DOCKER_SOCK in v for v in api.get("volumes", []))
    assert any(v.startswith(f"{DOCKER_SOCK}:") for v in builder["volumes"])


def test_the_builder_gets_none_of_the_apis_credentials(builder):
    assert sorted(k for k in builder["environment"] if API_ONLY.search(k)) == []


def test_the_builder_connects_as_the_portal_role_not_the_superuser(builder):
    assert builder["environment"]["PORTAL_DB_USER"] == "portal"


def test_each_service_builds_its_own_image_target(api, builder):
    assert api["build"]["target"] == "api"
    assert builder["build"]["target"] == "builder"


# ── Dockerfile targets ────────────────────────────────────────────────


def _stages():
    stages, name = {}, None
    for line in (API_ROOT / "Dockerfile").read_text().splitlines():
        m = re.match(r"^FROM\s+(\S+)\s+AS\s+(\S+)", line, re.I)
        if m:
            name = m.group(2)
            stages[name] = {"base": m.group(1), "body": ""}
        elif name and not line.lstrip().startswith("#"):
            stages[name]["body"] += line + "\n"
    return stages


def test_the_api_image_has_no_build_tooling_or_builder_code():
    body = _stages()["api"]["body"]
    for forbidden in ("docker-ce-cli", "docker-compose-plugin", "volta", " git", "COPY builder"):
        assert forbidden not in body, forbidden


def test_the_builder_image_has_no_api_code():
    stage = _stages()["builder"]
    assert stage["base"] != "api"  # FROM api would carry app/ and src/ into it
    assert "COPY app" not in stage["body"] and "COPY src" not in stage["body"]
    assert "builder.main:app" in stage["body"]


# ── Entry points ──────────────────────────────────────────────────────


def _loaded_after_import(module, tmp_path):
    env = {**os.environ, "PYTHONPATH": os.pathsep.join([str(API_ROOT / "src"), str(API_ROOT)]),
           "DATABASE_PATH": str(tmp_path / "registry.db"), "POSTGRES_ENABLED": "false"}
    env.pop("PORTAL_DB_HOST", None)
    r = subprocess.run([sys.executable, "-c", f"import sys, {module}; print(' '.join(sys.modules))"],
                       cwd=tmp_path, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return {m.split(".")[0] for m in r.stdout.split()}


def test_the_api_app_does_not_load_the_builder(tmp_path):
    assert "builder" not in _loaded_after_import("app.main", tmp_path)


def test_the_builder_app_does_not_load_the_api(tmp_path):
    assert not {"app", "digitaltwins"} & _loaded_after_import("builder.main", tmp_path)
