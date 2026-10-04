"""/datasets/uploads for workflow datasets: chunked session → validated → the workflow and its
tools committed + registered in SEEK (faked)."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.routers import auth
from digitaltwins import tools, workflows
from test_datasets_workflows_api import script_files, tool_bucket  # noqa: F401  (fixture)

UPLOADER = {"username": "alice", "token": "t", "claims": {"realm_access": {"roles": ["researcher"]}}}


@pytest.fixture
def client(platform_db, minio_bucket, tool_bucket, seek, hapi, tmp_path, monkeypatch):  # noqa: F811
    monkeypatch.setenv("DATASET_STAGING_DIR", str(tmp_path / "staging"))
    monkeypatch.setattr(workflows, "CATEGORY", minio_bucket)
    monkeypatch.setattr(tools, "CATEGORY", tool_bucket)
    app = create_app()
    app.dependency_overrides[auth.validate_credentials] = lambda: UPLOADER
    c = TestClient(app)
    c.bucket, c.db, c.seek, c.hapi = minio_bucket, platform_db, seek, hapi
    return c


def _files(files=None):
    return [(f"wf_convert/{rel}", data) for rel, data in (files or script_files()).items()]


def _create(client, files, **body):
    manifest = [{"rel_path": rel, "size": len(data), "parts": 1} for rel, data in files]
    return client.post("/datasets/uploads", json={
        "name": "Convert workflow", "category": client.bucket, "source_kind": "folder", "manifest": manifest,
        "workflow_type": "script", "seek_project_id": 11, **body,
    })


def _upload(client, files, **body):
    r = _create(client, files, **body)
    assert r.status_code == 200, r.text
    upload_id = r.json()["upload_id"]
    for rel, data in files:
        r = client.put(f"/datasets/uploads/{upload_id}/parts/{rel}", params={"n": 0, "of": 1}, content=data,
                       headers={"Content-Type": "application/octet-stream"})
        assert r.status_code == 200, r.text
    return upload_id


def _db(client, sql, params=None):
    conn = client.db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


@pytest.mark.integration
def test_workflow_session_commits_the_workflow_and_its_tools(client):
    upload_id = _upload(client, _files())

    r = client.post(f"/datasets/uploads/{upload_id}/finalize")

    assert r.status_code == 202, r.text
    assert r.json()["warnings"] == []
    session = client.get(f"/datasets/uploads/{upload_id}").json()  # TestClient ran the background job
    assert session["status"] == "completed", session
    assert (session["workflow_type"], session["seek_project_id"]) == ("script", 11)
    assert _db(client, "SELECT dataset_name, workflow_type FROM dataset WHERE dataset_uuid = %s",
               (session["dataset_uuid"],)) == [("Convert workflow", "script")]
    assert _db(client, "SELECT count(*) FROM workflow_tool WHERE workflow_dataset_uuid = %s",
               (session["dataset_uuid"],)) == [(2,)]
    assert sorted(w.get("workflow_type", "tool") for w in client.seek.workflows.values()) == ["script", "tool", "tool"]


@pytest.mark.integration
def test_staged_workflow_session_registers_on_approval(client):
    upload_id = _upload(client, _files(), commit_mode="on_approve")

    assert client.post(f"/datasets/uploads/{upload_id}/finalize").json()["status"] == "staged"
    assert client.seek.workflows == {}
    assert client.post(f"/datasets/uploads/{upload_id}/approve").status_code == 202

    assert client.get(f"/datasets/uploads/{upload_id}").json()["status"] == "completed"
    assert len(client.seek.workflows) == 3


@pytest.mark.integration
@pytest.mark.parametrize("body, detail", [
    ({"workflow_type": None}, "workflow_type"),
    ({"seek_project_id": None}, "seek_project_id"),
    ({"fhir_descriptions": {"patients": []}}, "workflow"),
])
def test_workflow_session_options_are_checked_at_creation(client, body, detail):
    r = _create(client, _files(), **body)

    assert r.status_code == 400 and detail in r.json()["detail"]
    assert _db(client, "SELECT count(*) FROM upload_session") == [(0,)]


@pytest.mark.integration
def test_invalid_workflow_fails_finalize_and_keeps_receiving(client):
    upload_id = _upload(client, _files(), workflow_type="gui")

    r = client.post(f"/datasets/uploads/{upload_id}/finalize")

    assert r.status_code == 400 and "exactly one step" in r.json()["detail"]
    assert client.get(f"/datasets/uploads/{upload_id}").json()["status"] == "receiving"


@pytest.mark.integration
def test_seek_failure_fails_the_session_and_approve_retries(client):
    client.seek.fail_register_workflow = True
    upload_id = _upload(client, _files())

    assert client.post(f"/datasets/uploads/{upload_id}/finalize").status_code == 202
    session = client.get(f"/datasets/uploads/{upload_id}").json()
    assert session["status"] == "failed" and "not a member" in session["failure_message"]
    assert client.seek.workflows == {} and _db(client, "SELECT count(*) FROM dataset") == [(0,)]

    client.seek.fail_register_workflow = False
    assert client.post(f"/datasets/uploads/{upload_id}/approve").status_code == 202
    assert client.get(f"/datasets/uploads/{upload_id}").json()["status"] == "completed"
    assert len(client.seek.workflows) == 3


@pytest.mark.integration
def test_workflow_session_with_fhir_pushes_tools_and_plan(client):
    upload_id = _upload(client, _files(), fhir="auto")

    assert client.post(f"/datasets/uploads/{upload_id}/finalize").status_code == 202

    session = client.get(f"/datasets/uploads/{upload_id}").json()
    assert session["status"] == "completed", session
    assert _db(client, "SELECT fhir_status FROM dataset WHERE dataset_uuid = %s",
               (session["dataset_uuid"],)) == [("completed",)]
    assert client.hapi.types() == {"ActivityDefinition": 2, "PlanDefinition": 1}


@pytest.mark.integration
def test_workflow_session_descriptions_are_checked_at_finalize(client):
    upload_id = _upload(client, _files(), fhir_descriptions={"workflow_tools": {"zzz": {}}})

    r = client.post(f"/datasets/uploads/{upload_id}/finalize")

    assert r.status_code == 400 and "zzz" in r.json()["detail"]
    assert client.get(f"/datasets/uploads/{upload_id}").json()["status"] == "receiving"
