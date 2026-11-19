"""The api service in docker-compose.yml passes the settings the API reads, and nothing it doesn't."""
from pathlib import Path

import yaml

API_ROOT = Path(__file__).resolve().parents[1]
API = yaml.safe_load((API_ROOT / "docker-compose.yml").read_text())["services"]["api"]


def test_no_configs_ini_bind_mount():
    assert not [v for v in API["volumes"] if "configs.ini" in v]


def test_airflow_port_is_not_passed():
    assert "AIRFLOW_PORT" not in API["environment"]


def test_keycloak_tls_settings_reach_the_api():
    env = API["environment"]
    assert env["KEYCLOAK_VERIFY_SSL"] == "${KEYCLOAK_VERIFY_SSL:-true}"
    assert env["KEYCLOAK_CA_CERT"] == "${KEYCLOAK_CA_CERT:-}"
