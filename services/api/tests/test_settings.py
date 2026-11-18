"""The API reads its environment through ``digitaltwins.settings`` and nowhere else.

docs/decisions/2026-11-18-api-settings-module.md
"""
import re
from pathlib import Path

import pytest

from digitaltwins.settings import load_settings, require

API_ROOT = Path(__file__).resolve().parents[1]

VARS = [
    "POSTGRES_ENABLED", "SEEK_ENABLED", "MINIO_ENABLED", "AIRFLOW_ENABLED", "GEN3_ENABLED", "IRODS_ENABLED",
    "POSTGRES_HOST", "POSTGRES_PORT", "POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD",
    "MINIO_ENDPOINT", "MINIO_SERVER_ACCESS_KEY", "MINIO_SERVER_SECRET_KEY",
    "SEEK_BASE_URL",
    "AIRFLOW_ENDPOINT", "AIRFLOW_BASE_URL", "HOSTNAME", "AIRFLOW_USERNAME", "AIRFLOW_PASSWORD",
    "AIRFLOW_DAGS_DIR", "AIRFLOW_DAG_DEPLOY_TIMEOUT",
    "JUPYTERHUB_PUBLIC_URL", "JUPYTERHUB_INTERNAL_URL", "JUPYTERHUB_API_TOKEN",
    "KEYCLOAK_BASE_URL", "KEYCLOAK_REALM", "KEYCLOAK_CLIENT_ID", "KEYCLOAK_CLIENT_SECRET",
    "DATASET_STAGING_DIR", "MAX_UPLOAD_MB", "UPLOAD_PART_SIZE_BYTES", "UPLOAD_MANIFEST_MAX_FILES",
    "API_PUBLIC_URL", "FHIR_ENDPOINT", "BUILDER_URL", "WORKFLOW_TIMEZONE", "TZ",
]


@pytest.fixture
def empty_env(monkeypatch):
    for name in VARS:
        monkeypatch.delenv(name, raising=False)
    return monkeypatch


def test_defaults_with_an_empty_environment(empty_env):
    s = load_settings()

    assert not any(vars(s.enabled).values())
    assert vars(s.postgres) == {"host": None, "port": None, "db": None, "user": None, "password": None}
    assert vars(s.minio) == {"endpoint": None, "access_key": None, "secret_key": None}
    assert s.seek.base_url is None
    assert s.airflow.endpoint == "http://airflow-apiserver:8080/airflow"
    assert s.airflow.username is None and s.airflow.password is None  # no hard-coded credentials
    assert s.airflow.dags_dir is None
    assert s.airflow.deploy_timeout == 120.0
    assert s.jupyterhub.public_url == "http://localhost/jupyter"
    assert s.jupyterhub.internal_url == "http://digitaltwins-platform-jupyterhub:8000/jupyter"
    assert s.jupyterhub.api_token is None
    assert s.keycloak.base_url is None
    assert s.keycloak.realm == "digitaltwins"
    assert s.keycloak.client_id == "api"
    assert s.keycloak.client_secret is None
    assert s.uploads.staging_dir == Path("./dataset_staging")
    assert s.uploads.max_upload_mb == 20480
    assert s.uploads.part_size_bytes == 8 * 1024 * 1024
    assert s.uploads.manifest_max_files == 100000
    assert s.api_public_url == "http://localhost/api"
    assert s.fhir_endpoint == "localhost:8080/fhir"
    assert s.builder_url == "http://builder:8000"
    assert s.workflow_timezone == "Pacific/Auckland"


def test_values_come_from_the_environment_with_types(empty_env):
    empty_env.setenv("SEEK_ENABLED", "yes")
    empty_env.setenv("AIRFLOW_ENABLED", "1")
    empty_env.setenv("POSTGRES_HOST", "db")
    empty_env.setenv("MINIO_ENDPOINT", "http://minio:9000")
    empty_env.setenv("AIRFLOW_DAGS_DIR", "/opt/dags")
    empty_env.setenv("AIRFLOW_DAG_DEPLOY_TIMEOUT", "2.5")
    empty_env.setenv("DATASET_STAGING_DIR", "/staging")
    empty_env.setenv("MAX_UPLOAD_MB", "5")
    empty_env.setenv("UPLOAD_PART_SIZE_BYTES", "1024")
    empty_env.setenv("UPLOAD_MANIFEST_MAX_FILES", "7")

    s = load_settings()

    assert s.enabled.seek is True and s.enabled.airflow is True and s.enabled.postgres is False
    assert s.postgres.host == "db"
    assert s.minio.endpoint == "http://minio:9000"
    assert s.airflow.dags_dir == Path("/opt/dags")
    assert s.airflow.deploy_timeout == 2.5
    assert s.uploads.staging_dir == Path("/staging")
    assert (s.uploads.max_upload_mb, s.uploads.part_size_bytes, s.uploads.manifest_max_files) == (5, 1024, 7)


def test_a_malformed_number_falls_back_to_its_default(empty_env):
    empty_env.setenv("MAX_UPLOAD_MB", "lots")
    assert load_settings().uploads.max_upload_mb == 20480


def test_airflow_base_url_falls_back_to_the_platform_hostname(empty_env):
    empty_env.setenv("HOSTNAME", "platform.example.org")
    assert load_settings().airflow.base_url == "http://platform.example.org/airflow"
    empty_env.setenv("AIRFLOW_BASE_URL", "https://other/airflow")
    assert load_settings().airflow.base_url == "https://other/airflow"


def test_workflow_timezone_falls_back_to_tz(empty_env):
    empty_env.setenv("TZ", "UTC")
    assert load_settings().workflow_timezone == "UTC"
    empty_env.setenv("WORKFLOW_TIMEZONE", "Europe/London")
    assert load_settings().workflow_timezone == "Europe/London"


def test_every_call_reads_the_environment_afresh(empty_env):
    assert load_settings().seek.base_url is None
    empty_env.setenv("SEEK_BASE_URL", "http://seek")
    assert load_settings().seek.base_url == "http://seek"


def test_settings_are_frozen(empty_env):
    with pytest.raises(AttributeError):
        load_settings().seek.base_url = "x"


def test_require_names_the_missing_variable():
    assert require("tok", "JUPYTERHUB_API_TOKEN") == "tok"
    with pytest.raises(KeyError, match="JUPYTERHUB_API_TOKEN"):
        require(None, "JUPYTERHUB_API_TOKEN")


# Files that still read the environment themselves, and why.
ALLOWED = {
    "src/digitaltwins/settings.py",
    # Byte-identical with the builder's copy (services/builder/tests/test_shared_with_api.py).
    "src/digitaltwins/core/keycloak_verifier.py",
    # Inactive iRODS and Gen3 backends, listed for removal in docs/future_refactoring.md.
    "src/digitaltwins/core/querier_factory.py",
    "src/digitaltwins/core/uploader_gen3.py",
}
ALLOWED_DIRS = ("src/digitaltwins/irods/", "src/digitaltwins/gen3/")


def test_no_module_reads_the_environment_outside_settings():
    offenders = []
    for path in sorted([*API_ROOT.glob("app/**/*.py"), *API_ROOT.glob("src/digitaltwins/**/*.py")]):
        rel = path.relative_to(API_ROOT).as_posix()
        if rel in ALLOWED or rel.startswith(ALLOWED_DIRS):
            continue
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if re.search(r"\bos\.(getenv|environ)\b|\bload_dotenv\b", line):
                offenders.append(f"{rel}:{n}: {line.strip()}")
    assert offenders == [], "read settings via digitaltwins.settings.load_settings():\n" + "\n".join(offenders)
