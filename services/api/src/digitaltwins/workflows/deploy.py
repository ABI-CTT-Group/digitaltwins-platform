"""Deploy a registered script workflow's DAG into Airflow (admin only).

The workflow's ``code/`` folder is fetched from MinIO, checked (``dag.find_dag_file``),
written to ``<AIRFLOW_DAGS_DIR>/workflow_<seek_id>/``, and Airflow is polled until
it has parsed the new files (then the DAG is unpaused) or reports an import error.
The outcome is stored in ``dataset.dag_status`` / ``dag_error``.
See docs/decisions/2026-10-13-deploy-script-workflow-dags.md.
"""
import logging
import os
import tempfile
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import requests

from digitaltwins import workflows
from .dag import dag_id_for, dags_dir, find_dag_file, write_dag_folder
from ..measurements.staging import staging_root

logger = logging.getLogger(__name__)

POLL_INTERVAL = 5  # seconds between Airflow polls


class NotScriptWorkflow(Exception):
    """Only script workflows have an Airflow DAG."""


class DeployUnavailable(RuntimeError):
    """Deploying is not configured here, or MinIO / Airflow could not be reached."""


def _airflow_session() -> requests.Session:
    """A session authenticated against Airflow's REST API with the platform's Airflow account."""
    from ..airflow.workflow import Workflow

    session = requests.Session()
    session.headers["Authorization"] = f"Bearer {Workflow().get_api_token()}"
    return session


def _time(value: Optional[str]) -> datetime:
    return datetime.fromisoformat(value) if value else datetime.min.replace(tzinfo=timezone.utc)


def wait_for_dag(session, dag_id: str, dag_file: str, started: datetime, timeout: float) -> Tuple[str, Optional[str]]:
    """Poll Airflow until it parses ``dag_id`` after ``started`` (then unpause it) or reports an import error.

    Returns ``("deployed", None)`` or ``("failed", reason)``. Earlier parses and
    import errors are ignored, so a redeploy waits for the new files.
    """
    base = f"{os.environ['AIRFLOW_ENDPOINT']}/api/v2"
    deadline = time.monotonic() + timeout
    while True:
        r = session.get(f"{base}/dags/{dag_id}", timeout=30)
        if r.status_code != 404:
            r.raise_for_status()
            if _time(r.json().get("last_parsed_time")) >= started:
                session.patch(f"{base}/dags/{dag_id}", json={"is_paused": False}, timeout=30).raise_for_status()
                return "deployed", None
        r = session.get(f"{base}/importErrors", params={"limit": 100, "order_by": "-id"}, timeout=30)
        r.raise_for_status()
        for error in r.json().get("import_errors", []):
            if ("/" + error.get("filename", "")).endswith(f"/{dag_id}/{dag_file}") \
                    and _time(error.get("timestamp")) >= started:
                return "failed", error.get("stack_trace") or "Airflow could not import the DAG."
        if time.monotonic() >= deadline:
            return "failed", f"Airflow did not load {dag_id} within {timeout:g}s; deploy again to re-check."
        time.sleep(POLL_INTERVAL)


def _set_status(conn, dataset_uuid: str, status: str, error: Optional[str]) -> None:
    with conn.cursor() as cur:
        cur.execute("UPDATE dataset SET dag_status = %s, dag_error = %s WHERE dataset_uuid = %s",
                    (status, error, dataset_uuid))
    conn.commit()


def _workflow_row(conn, dataset_uuid: str) -> Tuple[Any, str]:
    try:
        uuid.UUID(dataset_uuid)
    except ValueError:
        raise LookupError(f"No workflow dataset {dataset_uuid}") from None
    with conn.cursor() as cur:
        cur.execute("SELECT seek_id, workflow_type FROM dataset WHERE dataset_uuid = %s AND workflow_type IS NOT NULL",
                    (dataset_uuid,))
        row = cur.fetchone()
    conn.commit()
    if row is None:
        raise LookupError(f"No workflow dataset {dataset_uuid}")
    return row


def deploy_workflow(conn, dataset_uuid: str) -> Dict[str, Any]:
    """Deploy the workflow's DAG; return ``{dataset_uuid, dag_id, dag_status, dag_error}``.

    Raises LookupError (no such workflow), NotScriptWorkflow, ValueError (the
    DAG fails the static check; stored as ``failed``) or DeployUnavailable.
    """
    seek_id, workflow_type = _workflow_row(conn, dataset_uuid)
    if workflow_type != "script":
        raise NotScriptWorkflow(f"A {workflow_type} workflow has no Airflow DAG to deploy")
    dags = dags_dir()
    if dags is None:
        raise DeployUnavailable("DAG deployment is not configured (AIRFLOW_DAGS_DIR is unset)")
    dag_id = dag_id_for(seek_id)

    staging_root().mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=staging_root()) as tmp:
        code = Path(tmp) / "code"
        try:
            from ..minio.downloader import Downloader
            Downloader().download_folder(workflows.CATEGORY, f"{dataset_uuid}/code/", str(code))
        except FileNotFoundError:
            pass  # no code/ at all: find_dag_file says so
        except (ConnectionError, RuntimeError) as exc:
            raise DeployUnavailable(f"Could not fetch the workflow from MinIO: {exc}") from exc
        try:
            dag_file = find_dag_file(code)
        except ValueError as exc:
            _set_status(conn, dataset_uuid, "failed", str(exc))
            raise
        started = datetime.now(timezone.utc)
        write_dag_folder(code, dags, dag_id, dag_file.name)

    timeout = float(os.getenv("AIRFLOW_DAG_DEPLOY_TIMEOUT", "120"))
    try:
        status, error = wait_for_dag(_airflow_session(), dag_id, dag_file.name, started, timeout)
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        _set_status(conn, dataset_uuid, "failed", f"Could not check the DAG in Airflow: {exc}")
        raise DeployUnavailable(f"Could not check the DAG in Airflow: {exc}") from exc
    _set_status(conn, dataset_uuid, status, error)
    logger.info("Deployed DAG %s for workflow %s: %s", dag_id, dataset_uuid, status)
    return {"dataset_uuid": dataset_uuid, "dag_id": dag_id, "dag_status": status, "dag_error": error}


def auto_deploy(dataset_uuid: str) -> None:
    """Deploy a just-registered script workflow's DAG; run in the background after an admin's commit.

    Never raises: the registration stands whatever happens here. The outcome is
    in ``dag_status`` (left ``pending`` when deploying is not set up, or on an
    unexpected error, so an admin can deploy by hand).
    """
    from ..core.connection import Connection

    conn, _ = Connection().connect()
    try:
        deploy_workflow(conn, dataset_uuid)
    except (LookupError, NotScriptWorkflow):
        pass
    except Exception:  # a failed static check or Airflow check is already stored as "failed"
        logger.exception("Automatic DAG deploy of workflow %s did not complete", dataset_uuid)
    finally:
        conn.close()
