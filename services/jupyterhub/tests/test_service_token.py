"""The digitaltwins-api service token: required, and previously configured ones are revoked.

Runs ``jupyterhub_config.py`` the way the hub does (``get_config()`` in its working
directory) against a database built with the hub's own ORM. Run inside the hub image:

    docker run --rm -v $PWD/services/jupyterhub:/src -w /src --entrypoint sh \
        digitaltwins-platform-jupyterhub -c "pip install -q pytest; python -m pytest -q tests"
"""
import runpy
from pathlib import Path

import pytest
from jupyterhub import orm
from traitlets.config import Config

CONFIG = Path(__file__).resolve().parent.parent / "jupyterhub_config.py"
ENV = {
    "DOCKER_NETWORK_NAME": "net",
    "JUPYTERHUB_CLIENT_SECRET": "client-secret",
    "JUPYTERHUB_PUBLIC_URL": "http://localhost/jupyter",
    "KEYCLOAK_INTERNAL_URL": "http://keycloak:8080/auth",
    "KEYCLOAK_PUBLIC_URL": "http://localhost/auth",
    "KEYCLOAK_REALM": "digitaltwins",
    "JUPYTERHUB_API_TOKEN": "new-service-token",
}


@pytest.fixture
def hub_dir(tmp_path, monkeypatch):
    for key, value in ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def load_config():
    c = Config()
    runpy.run_path(str(CONFIG), init_globals={"get_config": lambda: c})
    return c


def make_db(path):
    """A hub database holding the tokens a deployment that ran with the old default would have."""
    db = orm.new_session_factory(f"sqlite:///{path}")()
    api = orm.Service(name="digitaltwins-api")
    other = orm.Service(name="other-service")
    alice = orm.User(name="alice")
    # Tokens belong to an OAuth client; a running hub always has its own, "jupyterhub".
    db.add_all([api, other, alice, orm.OAuthClient(identifier="jupyterhub")])
    db.commit()
    api.new_api_token("old-public-token", note="from config")
    api.new_api_token("issued-by-api", note="requested")
    other.new_api_token("other-config-token", note="from config")
    alice.new_api_token("alice-token", note="mine")
    db.commit()
    db.close()


def tokens(path):
    db = orm.new_session_factory(f"sqlite:///{path}")()
    try:
        return {
            "old-public-token": orm.APIToken.find(db, "old-public-token") is not None,
            "issued-by-api": orm.APIToken.find(db, "issued-by-api") is not None,
            "other-config-token": orm.APIToken.find(db, "other-config-token") is not None,
            "alice-token": orm.APIToken.find(db, "alice-token") is not None,
        }
    finally:
        db.close()


def test_the_service_gets_the_token_from_the_environment(hub_dir):
    [service] = load_config().JupyterHub.services
    assert service["name"] == "digitaltwins-api"
    assert service["api_token"] == "new-service-token"


def test_a_missing_token_is_an_error_not_a_default(hub_dir, monkeypatch):
    monkeypatch.delenv("JUPYTERHUB_API_TOKEN")
    with pytest.raises(KeyError, match="JUPYTERHUB_API_TOKEN"):
        load_config()


def test_previously_configured_service_tokens_are_revoked(hub_dir):
    make_db(hub_dir / "jupyterhub.sqlite")
    load_config()
    assert tokens(hub_dir / "jupyterhub.sqlite") == {
        "old-public-token": False,
        "issued-by-api": True,
        "other-config-token": True,
        "alice-token": True,
    }


def test_a_fresh_install_gets_no_database_from_the_config(hub_dir):
    load_config()
    assert not (hub_dir / "jupyterhub.sqlite").exists()
