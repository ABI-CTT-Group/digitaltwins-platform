"""Every environment variable the API and this package read, with its type and default.

Call ``load_settings()`` where a value is needed. It reads the environment on every call, so a value
set by the deployment or by a test (``monkeypatch.setenv``) is always seen. Add a new variable here
first, then to ``docker-compose.yml`` and the root ``.env.template``.

docs/decisions/2026-11-18-api-settings-module.md
"""
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from .utils.config_loader import is_truthy

# The package's only .env loading; it never overrides variables already set.
load_dotenv()


@dataclass(frozen=True)
class Enabled:
    postgres: bool
    seek: bool
    minio: bool
    airflow: bool
    gen3: bool
    irods: bool


@dataclass(frozen=True)
class Postgres:
    host: Optional[str]
    port: Optional[str]
    db: Optional[str]
    user: Optional[str]
    password: Optional[str]


@dataclass(frozen=True)
class Minio:
    endpoint: Optional[str]
    access_key: Optional[str]
    secret_key: Optional[str]


@dataclass(frozen=True)
class Seek:
    base_url: Optional[str]


@dataclass(frozen=True)
class Airflow:
    endpoint: str  # internal API, e.g. http://airflow-apiserver:8080/airflow
    base_url: str  # public UI, for monitor links
    username: Optional[str]
    password: Optional[str]
    dags_dir: Optional[Path]  # None when DAG deploy is not set up
    deploy_timeout: float


@dataclass(frozen=True)
class JupyterHub:
    public_url: str
    internal_url: str
    api_token: Optional[str]  # no default: the hub would accept it, and a default would be public


@dataclass(frozen=True)
class Keycloak:
    base_url: Optional[str]
    realm: str
    client_id: str
    client_secret: Optional[str]


@dataclass(frozen=True)
class Uploads:
    staging_dir: Path
    max_upload_mb: int
    part_size_bytes: int  # chunk size clients split on; the API reports it so both sides agree
    manifest_max_files: int


@dataclass(frozen=True)
class Settings:
    enabled: Enabled
    postgres: Postgres
    minio: Minio
    seek: Seek
    airflow: Airflow
    jupyterhub: JupyterHub
    keycloak: Keycloak
    uploads: Uploads
    api_public_url: str  # public URL of this API, used in FHIR endpoint URLs
    fhir_endpoint: str
    builder_url: str
    workflow_timezone: str


def load_settings() -> Settings:
    env = os.environ
    return Settings(
        enabled=Enabled(
            postgres=is_truthy(env.get("POSTGRES_ENABLED")),
            seek=is_truthy(env.get("SEEK_ENABLED")),
            minio=is_truthy(env.get("MINIO_ENABLED")),
            airflow=is_truthy(env.get("AIRFLOW_ENABLED")),
            gen3=is_truthy(env.get("GEN3_ENABLED")),
            irods=is_truthy(env.get("IRODS_ENABLED")),
        ),
        postgres=Postgres(
            host=env.get("POSTGRES_HOST"),
            port=env.get("POSTGRES_PORT"),
            db=env.get("POSTGRES_DB"),
            user=env.get("POSTGRES_USER"),
            password=env.get("POSTGRES_PASSWORD"),
        ),
        minio=Minio(
            endpoint=env.get("MINIO_ENDPOINT"),
            access_key=env.get("MINIO_SERVER_ACCESS_KEY"),
            secret_key=env.get("MINIO_SERVER_SECRET_KEY"),
        ),
        seek=Seek(base_url=env.get("SEEK_BASE_URL")),
        airflow=Airflow(
            endpoint=env.get("AIRFLOW_ENDPOINT", "http://airflow-apiserver:8080/airflow"),
            base_url=env.get("AIRFLOW_BASE_URL", f"http://{env.get('HOSTNAME')}/airflow"),
            username=env.get("AIRFLOW_USERNAME"),
            password=env.get("AIRFLOW_PASSWORD"),
            dags_dir=Path(env["AIRFLOW_DAGS_DIR"]) if env.get("AIRFLOW_DAGS_DIR") else None,
            deploy_timeout=_number(float, "AIRFLOW_DAG_DEPLOY_TIMEOUT", 120.0),
        ),
        jupyterhub=JupyterHub(
            public_url=env.get("JUPYTERHUB_PUBLIC_URL", "http://localhost/jupyter"),
            internal_url=env.get("JUPYTERHUB_INTERNAL_URL", "http://digitaltwins-platform-jupyterhub:8000/jupyter"),
            api_token=env.get("JUPYTERHUB_API_TOKEN"),
        ),
        keycloak=Keycloak(
            base_url=env.get("KEYCLOAK_BASE_URL"),
            realm=env.get("KEYCLOAK_REALM", "digitaltwins"),
            client_id=env.get("KEYCLOAK_CLIENT_ID", "api"),
            client_secret=env.get("KEYCLOAK_CLIENT_SECRET"),
        ),
        uploads=Uploads(
            staging_dir=Path(env.get("DATASET_STAGING_DIR", "./dataset_staging")),
            max_upload_mb=_number(int, "MAX_UPLOAD_MB", 20480),
            part_size_bytes=_number(int, "UPLOAD_PART_SIZE_BYTES", 8 * 1024 * 1024),
            manifest_max_files=_number(int, "UPLOAD_MANIFEST_MAX_FILES", 100000),
        ),
        api_public_url=env.get("API_PUBLIC_URL", "http://localhost/api"),
        fhir_endpoint=env.get("FHIR_ENDPOINT", "localhost:8080/fhir"),
        builder_url=env.get("BUILDER_URL", "http://builder:8000"),
        workflow_timezone=env.get("WORKFLOW_TIMEZONE", env.get("TZ", "Pacific/Auckland")),
    )


def require(value: Optional[str], name: str) -> str:
    """``value``, or ``KeyError(name)`` when a setting with no safe default is missing."""
    if value is None:
        raise KeyError(name)
    return value


def _number(kind, name: str, default):
    try:
        return kind(os.environ.get(name, default))
    except ValueError:
        return default
