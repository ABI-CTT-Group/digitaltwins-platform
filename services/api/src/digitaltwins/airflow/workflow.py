
import requests
from requests import RequestException

from ..settings import load_settings


class Workflow(object):
    def __init__(self):
        airflow = load_settings().airflow
        self._airflow_endpoint = airflow.endpoint
        self._username = airflow.username
        self._password = airflow.password

        for required in [self._airflow_endpoint, self._username, self._password]:
            if not required:
                raise ValueError("Airflow configuration is incomplete. Please check your environment variables.")

    def _post(self, url, **kwargs):
        try:
            response = requests.post(url, timeout=30, **kwargs)
            response.raise_for_status()
            return response
        except RequestException as exc:
            raise RuntimeError(f"Airflow request failed for {url}: {exc}") from exc

    def get_api_token(self):
        url = f"{self._airflow_endpoint}/auth/token"
        headers = {"Content-Type": "application/json"}
        payload = {
            "username": self._username,
            "password": self._password
        }
        response = self._post(url, headers=headers, json=payload)
        try:
            access_token = response.json().get("access_token")
        except ValueError as exc:
            raise RuntimeError("Airflow returned a non-JSON token response") from exc
        if not access_token:
            raise RuntimeError("Airflow token response did not include an access_token")
        return access_token
