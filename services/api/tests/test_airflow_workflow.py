"""The Airflow client keeps only the token call; the old ``preprocessor`` DAG trigger is gone."""
from unittest import mock

import digitaltwins
from digitaltwins.airflow.workflow import Workflow


def test_package_no_longer_exports_workflow():
    assert not hasattr(digitaltwins, "Workflow")


def test_airflow_client_has_no_run():
    assert not hasattr(Workflow, "run")


def test_get_api_token_posts_credentials(monkeypatch):
    monkeypatch.delenv("AIRFLOW_VERSION", raising=False)
    monkeypatch.setenv("AIRFLOW_ENDPOINT", "http://airflow:8080/airflow")
    monkeypatch.setenv("AIRFLOW_API_URL", "http://airflow:8080/airflow/api/v2")
    monkeypatch.setenv("AIRFLOW_USERNAME", "user")
    monkeypatch.setenv("AIRFLOW_PASSWORD", "pw")

    response = mock.Mock()
    response.json.return_value = {"access_token": "tok"}
    with mock.patch("digitaltwins.airflow.workflow.requests.post", return_value=response) as post:
        assert Workflow().get_api_token() == "tok"

    post.assert_called_once()
    assert post.call_args.args[0] == "http://airflow:8080/airflow/auth/token"
    assert post.call_args.kwargs["json"] == {"username": "user", "password": "pw"}
