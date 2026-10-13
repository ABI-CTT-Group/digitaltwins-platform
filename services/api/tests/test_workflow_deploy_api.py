"""POST /workflows/{dataset_uuid}/deploy: an admin deploys a registered script workflow's DAG into Airflow;
a script workflow an admin registers (REST upload, or an upload session's commit) is deployed straight away.

The DAG folder is written to a temporary dags dir; Airflow's REST API is faked.
"""
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.routers import auth, datasets
from digitaltwins import tools, workflows
from digitaltwins.workflows import deploy
from test_dataset_uploads_workflows_api import _files as _session_parts, _upload
from test_datasets_workflows_api import _folder_parts, gui_files, script_files, tool_bucket  # noqa: F401

ADMIN = {"username": "alice", "token": "t", "claims": {"realm_access": {"roles": ["admin"]}}}
RESEARCHER = {"username": "rita", "token": "t", "claims": {"realm_access": {"roles": ["researcher"]}}}

GOOD_DAG = b"""from pathlib import Path
from airflow.decorators import dag

DAG_ID = Path(__file__).parent.name

@dag(dag_id=DAG_ID, schedule=None)
def convert():
    pass

convert()
"""
LITERAL_DAG = GOOD_DAG.replace(b"Path(__file__).parent.name", b"'workflow_89'")


class _Resp:
    def __init__(self, status_code, body=None):
        self.status_code, self._body = status_code, body or {}

    def json(self):
        return self._body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise deploy.requests.HTTPError(f"{self.status_code}")


class FakeAirflow:
    """Airflow's REST API: ``parsed`` lists what GET /dags/{id} returns on each poll (None = 404)."""

    def __init__(self, parsed=(), import_errors=()):
        self.parsed, self.import_errors = list(parsed), list(import_errors)
        self.patches, self.polls = [], 0

    def get(self, url, params=None, timeout=None):
        if url.endswith("/importErrors"):
            return _Resp(200, {"import_errors": self.import_errors, "total_entries": len(self.import_errors)})
        dag_id = url.rsplit("/", 1)[1]
        when = self.parsed[min(self.polls, len(self.parsed) - 1)] if self.parsed else None
        self.polls += 1
        if when is None:
            return _Resp(404)
        return _Resp(200, {"dag_id": dag_id, "last_parsed_time": when.isoformat().replace("+00:00", "Z")})

    def patch(self, url, json=None, timeout=None):
        self.patches.append((url, json))
        return _Resp(200, {"is_paused": False})


def _now(seconds=0):
    return datetime.now(timezone.utc) + timedelta(seconds=seconds)


@pytest.fixture
def client(platform_db, minio_bucket, tool_bucket, seek, hapi, s3, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("DATASET_STAGING_DIR", str(tmp_path / "staging"))
    monkeypatch.setenv("AIRFLOW_DAGS_DIR", str(tmp_path / "dags"))
    monkeypatch.setenv("AIRFLOW_ENDPOINT", "http://airflow.test/airflow")
    monkeypatch.setenv("AIRFLOW_DAG_DEPLOY_TIMEOUT", "30")
    monkeypatch.setattr(deploy, "POLL_INTERVAL", 0)
    monkeypatch.setattr(workflows, "CATEGORY", minio_bucket)
    monkeypatch.setattr(tools, "CATEGORY", tool_bucket)
    monkeypatch.setattr(datasets, "DATASET_CATEGORIES", {minio_bucket, tool_bucket})
    (tmp_path / "dags").mkdir()
    app = create_app()
    app.dependency_overrides[auth.validate_credentials] = lambda: ADMIN
    c = TestClient(app)
    c.app_, c.bucket, c.db, c.dags = app, minio_bucket, platform_db, tmp_path / "dags"
    c.airflow = FakeAirflow(parsed=[None, _now(3600)])
    monkeypatch.setattr(deploy, "_airflow_session", lambda: c.airflow)
    return c


def _as(client, creds):
    client.app_.dependency_overrides[auth.validate_credentials] = lambda: creds


def _register(client, dag=GOOD_DAG, files=None, workflow_type="script", as_=RESEARCHER):
    """Register a workflow through the REST upload as ``as_`` (a researcher's stays pending), then act as admin."""
    files = files or {**script_files(), "code/workflow_convert.py": dag}
    _as(client, as_)
    r = client.post("/datasets", params={"category": client.bucket, "workflow_type": workflow_type,
                                         "seek_project_id": 11}, files=_folder_parts(files))
    _as(client, ADMIN)
    assert r.status_code == 200, r.text
    return r.json()["dataset_uuid"], r.json()["seek_id"]


def _status(client, dataset_uuid):
    conn = client.db()
    with conn.cursor() as cur:
        cur.execute("SELECT dag_status, dag_error FROM dataset WHERE dataset_uuid = %s", (dataset_uuid,))
        return cur.fetchone()


def _files(folder):
    return sorted(str(p.relative_to(folder)) for p in folder.rglob("*") if p.is_file())


@pytest.mark.integration
def test_admin_deploy_writes_the_dag_folder_unpauses_it_and_records_deployed(client):
    dataset_uuid, seek_id = _register(client)

    r = client.post(f"/workflows/{dataset_uuid}/deploy")

    assert r.status_code == 200, r.text
    dag_id = f"workflow_{seek_id}"
    assert r.json() == {"dataset_uuid": dataset_uuid, "dag_id": dag_id, "dag_status": "deployed", "dag_error": None}
    target = client.dags / dag_id
    assert _files(target) == [".airflowignore", "tool_to_nifti.py", "tool_to_nrrd.py", "workflow_convert.py"]
    assert (target / ".airflowignore").read_text() == "*.py\n!/workflow_convert.py\n"
    assert (target / "workflow_convert.py").read_bytes() == GOOD_DAG
    assert client.airflow.patches == [(f"http://airflow.test/airflow/api/v2/dags/{dag_id}", {"is_paused": False})]
    assert _status(client, dataset_uuid) == ("deployed", None)


@pytest.mark.integration
def test_a_researcher_cannot_deploy(client):
    dataset_uuid, _ = _register(client)
    _as(client, RESEARCHER)

    r = client.post(f"/workflows/{dataset_uuid}/deploy")

    assert r.status_code == 403
    assert list(client.dags.iterdir()) == []
    assert _status(client, dataset_uuid) == ("pending", None)


@pytest.mark.integration
def test_only_script_workflows_have_a_dag(client):
    dataset_uuid, _ = _register(client, files=gui_files(), workflow_type="gui")

    r = client.post(f"/workflows/{dataset_uuid}/deploy")

    assert r.status_code == 409
    assert list(client.dags.iterdir()) == []


@pytest.mark.integration
@pytest.mark.parametrize("dataset_uuid", [str(uuid.uuid4()), "not-a-uuid"])
def test_unknown_workflow_is_404(client, dataset_uuid):
    assert client.post(f"/workflows/{dataset_uuid}/deploy").status_code == 404


@pytest.mark.integration
def test_a_hardcoded_dag_id_is_rejected_before_anything_is_written(client):
    dataset_uuid, _ = _register(client, dag=LITERAL_DAG)

    r = client.post(f"/workflows/{dataset_uuid}/deploy")

    assert r.status_code == 422
    assert "Path(__file__).parent.name" in r.json()["detail"]
    assert list(client.dags.iterdir()) == []
    status, error = _status(client, dataset_uuid)
    assert status == "failed" and "'workflow_89'" in error


@pytest.mark.integration
def test_an_import_error_marks_the_deploy_failed_with_the_stack_trace(client):
    dataset_uuid, seek_id = _register(client)
    client.airflow = FakeAirflow(parsed=[None], import_errors=[
        {"filename": f"workflow_{seek_id}/workflow_convert.py", "timestamp": _now(60).isoformat(),
         "stack_trace": "ModuleNotFoundError: No module named 'nibabel'"}])

    r = client.post(f"/workflows/{dataset_uuid}/deploy")

    assert r.status_code == 200, r.text
    assert r.json()["dag_status"] == "failed"
    assert "nibabel" in r.json()["dag_error"]
    assert _status(client, dataset_uuid) == ("failed", "ModuleNotFoundError: No module named 'nibabel'")
    assert client.airflow.patches == []


@pytest.mark.integration
def test_an_old_import_error_is_ignored_and_a_dag_that_never_loads_times_out(client, monkeypatch):
    dataset_uuid, seek_id = _register(client)
    monkeypatch.setenv("AIRFLOW_DAG_DEPLOY_TIMEOUT", "0")
    client.airflow = FakeAirflow(parsed=[None], import_errors=[
        {"filename": f"/opt/airflow/dags/workflow_{seek_id}/workflow_convert.py",
         "timestamp": _now(-3600).isoformat(), "stack_trace": "an earlier attempt"}])

    r = client.post(f"/workflows/{dataset_uuid}/deploy")

    assert r.status_code == 200
    assert r.json()["dag_status"] == "failed"
    assert "did not load" in r.json()["dag_error"] and "deploy again" in r.json()["dag_error"]


@pytest.mark.integration
def test_redeploy_waits_for_airflow_to_parse_the_new_files(client):
    dataset_uuid, seek_id = _register(client)
    (client.dags / f"workflow_{seek_id}").mkdir()
    (client.dags / f"workflow_{seek_id}" / "stale.py").write_text("old")
    client.airflow = FakeAirflow(parsed=[_now(-3600), _now(-3600), _now(3600)])

    r = client.post(f"/workflows/{dataset_uuid}/deploy")

    assert r.json()["dag_status"] == "deployed"
    assert client.airflow.polls == 3
    assert not (client.dags / f"workflow_{seek_id}" / "stale.py").exists()


@pytest.mark.integration
def test_deploy_is_unavailable_without_a_dags_folder(client, monkeypatch):
    dataset_uuid, _ = _register(client)
    monkeypatch.delenv("AIRFLOW_DAGS_DIR")

    r = client.post(f"/workflows/{dataset_uuid}/deploy")

    assert r.status_code == 503
    assert _status(client, dataset_uuid) == ("pending", None)


# ── Automatic deploy when an admin registers the workflow ──────────────


@pytest.mark.integration
def test_an_admin_rest_upload_deploys_the_dag_straight_away(client):
    dataset_uuid, seek_id = _register(client, as_=ADMIN)

    assert _status(client, dataset_uuid) == ("deployed", None)
    assert (client.dags / f"workflow_{seek_id}" / "workflow_convert.py").read_bytes() == GOOD_DAG
    assert client.airflow.patches == [(f"http://airflow.test/airflow/api/v2/dags/workflow_{seek_id}",
                                       {"is_paused": False})]


@pytest.mark.integration
def test_a_researcher_rest_upload_waits_for_an_admin(client):
    dataset_uuid, _ = _register(client)

    assert _status(client, dataset_uuid) == ("pending", None)
    assert list(client.dags.iterdir()) == []


@pytest.mark.integration
def test_an_admin_upload_of_a_gui_workflow_deploys_nothing(client):
    dataset_uuid, _ = _register(client, files=gui_files(), workflow_type="gui", as_=ADMIN)

    assert _status(client, dataset_uuid) == (None, None)
    assert list(client.dags.iterdir()) == []


@pytest.mark.integration
def test_an_admin_upload_with_a_bad_dag_is_registered_and_says_why_it_was_not_deployed(client):
    dataset_uuid, _ = _register(client, dag=LITERAL_DAG, as_=ADMIN)

    status, error = _status(client, dataset_uuid)
    assert status == "failed" and "'workflow_89'" in error
    assert list(client.dags.iterdir()) == []


@pytest.mark.integration
def test_an_admin_upload_stays_pending_where_deploying_is_not_set_up(client, monkeypatch):
    monkeypatch.delenv("AIRFLOW_DAGS_DIR")

    dataset_uuid, _ = _register(client, as_=ADMIN)

    assert _status(client, dataset_uuid) == ("pending", None)


@pytest.mark.integration
def test_an_unexpected_deploy_error_does_not_fail_the_registration(client, monkeypatch):
    def boom(conn, dataset_uuid):
        raise OSError("disk full")
    monkeypatch.setattr(deploy, "deploy_workflow", boom)

    dataset_uuid, _ = _register(client, as_=ADMIN)

    assert _status(client, dataset_uuid) == ("pending", None)


def _session_files():
    return _session_parts({**script_files(), "code/workflow_convert.py": GOOD_DAG})


@pytest.mark.integration
def test_an_admin_upload_session_deploys_after_the_commit(client):
    upload_id = _upload(client, _session_files())

    assert client.post(f"/datasets/uploads/{upload_id}/finalize").status_code == 202

    session = client.get(f"/datasets/uploads/{upload_id}").json()  # TestClient ran the background job
    assert session["status"] == "completed", session
    assert _status(client, session["dataset_uuid"]) == ("deployed", None)


@pytest.mark.integration
def test_a_staged_session_deploys_when_an_admin_approves_it(client):
    _as(client, RESEARCHER)
    upload_id = _upload(client, _session_files(), commit_mode="on_approve")
    assert client.post(f"/datasets/uploads/{upload_id}/finalize").json()["status"] == "staged"

    _as(client, ADMIN)
    assert client.post(f"/datasets/uploads/{upload_id}/approve").status_code == 202

    session = client.get(f"/datasets/uploads/{upload_id}").json()
    assert _status(client, session["dataset_uuid"]) == ("deployed", None)


@pytest.mark.integration
def test_a_session_a_researcher_commits_waits_for_an_admin(client):
    _as(client, RESEARCHER)
    upload_id = _upload(client, _session_files())
    client.post(f"/datasets/uploads/{upload_id}/finalize")

    session = client.get(f"/datasets/uploads/{upload_id}").json()
    assert session["status"] == "completed", session
    assert _status(client, session["dataset_uuid"]) == ("pending", None)
    assert list(client.dags.iterdir()) == []
