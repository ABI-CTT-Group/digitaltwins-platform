"""
preprocessor.py
===============
Airflow 3 DAG — Preprocessor

Fetches assay configuration from the platform API, discovers subjects
in the cohort by querying the dataset-samples endpoint, then triggers
one ``workflow_{workflow_seek_id}`` DAG run per subject.

Usage
-----
Trigger via the Airflow UI or REST API with JSON conf::

    {
        "assay_id": 4
    }
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any

from airflow.decorators import dag, task


# ---------------------------------------------------------------------------
# Auth helper — exchanges Basic credentials for a Keycloak Bearer token
# via the platform API's own /token endpoint
# ---------------------------------------------------------------------------

def _get_api_token(api_base: str, username: str, password: str) -> str:
    """Return a Bearer token for the digitaltwins platform API."""
    import requests
    from requests.auth import HTTPBasicAuth

    token_url = f"{api_base}/token"
    resp = requests.post(
        token_url,
        auth=HTTPBasicAuth(username, password),
        timeout=15,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise ValueError(f"No access_token in response from {token_url}: {resp.json()}")
    return token

# ---------------------------------------------------------------------------
# Platform API defaults (Airflow containers share the Docker network)
# ---------------------------------------------------------------------------
DEFAULT_API_BASE: str = os.environ.get(
    "DIGITALTWINS_API_BASE_URL", "http://digitaltwins-api"
)
DEFAULT_API_PORT: str = os.environ.get("DIGITALTWINS_API_PORT", "8000")

# Credentials for the digitaltwins platform API (via Keycloak Basic auth)
APIUSERNAME: str = os.environ.get("_AIRFLOW_WWW_USER_USERNAME", "admin")
APIPASSWORD: str = os.environ.get("_AIRFLOW_WWW_USER_PASSWORD", "admin")

# Airflow REST API — internal Docker service name (from docker-compose.yml: airflow-apiserver:8080)
AIRFLOW_ENDPOINT: str = os.environ.get("AIRFLOW_ENDPOINT", "http://airflow-apiserver:8080")
AIRFLOW_USERNAME: str = os.environ.get("AIRFLOW_USERNAME", "admin")
AIRFLOW_PASSWORD: str = os.environ.get("AIRFLOW_PASSWORD", "admin")

DEFAULT_BUCKET: str = "airflow-workspace"


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

@dag(
    dag_id="preprocessor",
    dag_display_name="Preprocessor",
    description=(
        "Fetch assay configs, discover cohort subjects, and trigger "
        "a workflow DAG run for each subject."
    ),
    schedule=None,
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["preprocessor", "orchestrator"],
    doc_md=__doc__,
)
def preprocessor() -> None:
    """Declare the preprocessor DAG."""

    # ------------------------------------------------------------------
    # Step 1 — Fetch assay configuration from the platform API
    # ------------------------------------------------------------------
    @task()
    def fetch_assay_configs(**context: Any) -> dict[str, Any]:
        """Call GET /assays/{assay_id}?get_configs=true and return configs."""
        import requests  # available in the main Airflow env

        conf: dict[str, Any] = context["dag_run"].conf or {}
        assay_id = conf.get("assay_id")
        if not assay_id:
            raise ValueError("dag_run.conf must contain 'assay_id'")

        api_base = conf.get("api_base", f"{DEFAULT_API_BASE}:{DEFAULT_API_PORT}")

        # Obtain a Bearer token from the platform API
        token = _get_api_token(
            api_base,
            conf.get("api_username", APIUSERNAME),
            conf.get("api_password", APIPASSWORD),
        )
        headers = {"Authorization": f"Bearer {token}"}

        url = f"{api_base}/assays/{assay_id}"
        params = {"get_configs": "true"}

        resp = requests.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()

        assay = resp.json().get("assay", {})
        configs = assay.get("configs")
        if not configs:
            raise ValueError(
                f"No configs found for assay {assay_id}. "
                "Ensure the assay has been registered in Postgres."
            )

        return {
            "assay_id": assay_id,
            "api_base": api_base,
            "workflow_seek_id": configs.get("workflow_seek_id"),
            "inputs": configs.get("inputs", []),
            "outputs": configs.get("outputs", []),
            "bucket": conf.get("bucket", DEFAULT_BUCKET),
        }

    # ------------------------------------------------------------------
    # Step 2 — Discover subjects by querying dataset samples
    # ------------------------------------------------------------------
    @task()
    def discover_subjects(configs: dict[str, Any], **context: Any) -> list[dict]:
        """For each input, query /datasets/{uuid}/samples to find subjects."""
        import requests

        conf: dict[str, Any] = context["dag_run"].conf or {}
        api_base = configs.get("api_base", conf.get("api_base", f"{DEFAULT_API_BASE}:{DEFAULT_API_PORT}"))

        # Reuse the Bearer token
        token = _get_api_token(
            api_base,
            conf.get("api_username", APIUSERNAME),
            conf.get("api_password", APIPASSWORD),
        )
        headers = {"Authorization": f"Bearer {token}"}

        inputs = configs.get("inputs", [])
        if not inputs:
            raise ValueError("No inputs found in assay configs.")

        # Collect unique subjects across all inputs
        subjects: list[dict] = []
        seen_subjects: set[str] = set()

        for inp in inputs:
            dataset_uuid = inp.get("dataset_uuid")
            sample_type = inp.get("sample_type")
            input_name = inp.get("name", "input")

            if not dataset_uuid:
                continue

            url = f"{api_base}/datasets/{dataset_uuid}/samples"
            params = {}
            if sample_type:
                params["sample_type"] = sample_type

            resp = requests.get(url, params=params, headers=headers, timeout=30)
            resp.raise_for_status()
            samples = resp.json().get("samples", [])

            for sample in samples:
                subject_id = sample.get("subject_id")
                if subject_id and subject_id not in seen_subjects:
                    seen_subjects.add(subject_id)
                    subjects.append({
                        "subject_id": subject_id,
                        "dataset_uuid": dataset_uuid,
                        "sample_type": sample_type,
                        "input_name": input_name,
                    })

        if not subjects:
            raise ValueError(
                "No subjects found for the given inputs. "
                "Check dataset_uuid and sample_type in assay configs."
            )

        return subjects

    # ------------------------------------------------------------------
    # Step 3 — Trigger workflow DAG for each subject
    # ------------------------------------------------------------------
    @task()
    def trigger_workflow_runs(
        configs: dict[str, Any],
        subjects: list[dict],
    ) -> list[dict]:
        """Trigger workflow_{workflow_seek_id} once per subject."""
        import requests as req
        from datetime import timezone

        workflow_seek_id = configs.get("workflow_seek_id")
        if not workflow_seek_id:
            raise ValueError("workflow_seek_id missing from configs.")

        bucket = configs.get("bucket", DEFAULT_BUCKET)
        dag_id = f"workflow_{workflow_seek_id}"

        # Authenticate with Airflow 3 API
        token_url = f"{AIRFLOW_ENDPOINT}/auth/token"
        token_resp = req.post(
            token_url,
            json={"username": AIRFLOW_USERNAME, "password": AIRFLOW_PASSWORD},
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        token_resp.raise_for_status()
        access_token = token_resp.json().get("access_token")

        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        trigger_url = f"{AIRFLOW_ENDPOINT}/api/v2/dags/{dag_id}/dagRuns"
        results: list[dict] = []

        for idx, subject in enumerate(subjects):
            logical_date = datetime.now(timezone.utc).isoformat()
            run_id = f"{dag_id}/run_{idx}"
            payload = {
                "logical_date": logical_date,
                "conf": {
                    "bucket": bucket,
                    "subject_id": subject["subject_id"],
                    "dataset_uuid": subject["dataset_uuid"],
                    "sample_type": subject.get("sample_type", ""),
                    "input_name": subject.get("input_name", "input"),
                    "run_id": run_id,
                    "run_index": idx,
                },
            }

            resp = req.post(trigger_url, headers=headers, json=payload, timeout=30)
            if resp.status_code in (200, 201):
                results.append({
                    "subject_id": subject["subject_id"],
                    "dag_run": resp.json(),
                })
            else:
                results.append({
                    "subject_id": subject["subject_id"],
                    "error": f"HTTP {resp.status_code}: {resp.text}",
                })

        return results

    # Wire the tasks
    configs = fetch_assay_configs()
    subjects = discover_subjects(configs)
    trigger_workflow_runs(configs, subjects)


# Instantiate the DAG
preprocessor()
