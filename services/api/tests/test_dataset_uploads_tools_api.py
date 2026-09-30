"""/datasets/uploads for tool datasets: chunked session → validated → committed + registered in SEEK (faked)."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.routers import auth
from digitaltwins import tools

DESCRIPTION = Path(__file__).parent / "data" / "example_sds_dataset" / "dataset_description.xlsx"
UPLOADER = {"username": "alice", "token": "t", "claims": {"realm_access": {"roles": ["researcher"]}}}
CWL = b"cwlVersion: v1.2\nclass: CommandLineTool\nlabel: Tool - convert\ninputs: []\noutputs: []\n"


@pytest.fixture
def client(platform_db, minio_bucket, seek, tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_STAGING_DIR", str(tmp_path / "staging"))
    monkeypatch.setattr(tools, "CATEGORY", minio_bucket)
    app = create_app()
    app.dependency_overrides[auth.validate_credentials] = lambda: UPLOADER
    c = TestClient(app)
    c.bucket, c.db, c.seek = minio_bucket, platform_db, seek
    return c


def _files(cwl=True):
    files = [("sds_tool_convert/dataset_description.xlsx", DESCRIPTION.read_bytes()),
             ("sds_tool_convert/code/tool_convert.py", b"print('hi')\n")]
    files.append(("sds_tool_convert/primary/tool_convert.cwl", CWL) if cwl
                 else ("sds_tool_convert/primary/notes.txt", b"no tool here"))
    return files


def _create(client, files, **body):
    manifest = [{"rel_path": rel, "size": len(data), "parts": 1} for rel, data in files]
    return client.post("/datasets/uploads", json={
        "name": "Convert tool", "category": client.bucket, "source_kind": "folder", "manifest": manifest,
        "tool_type": "script", "seek_project_id": 11, **body,
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


def _db_one(client, sql, params=None):
    conn = client.db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


@pytest.mark.integration
def test_tool_session_is_committed_and_registered_in_seek(client):
    upload_id = _upload(client, _files())

    r = client.post(f"/datasets/uploads/{upload_id}/finalize")

    assert r.status_code == 202, r.text
    assert r.json()["warnings"] == []
    session = client.get(f"/datasets/uploads/{upload_id}").json()  # TestClient ran the background job
    assert session["status"] == "completed", session
    assert (session["tool_type"], session["seek_project_id"]) == ("script", 11)
    [seek_id] = _db_one(client, "SELECT seek_id FROM dataset WHERE dataset_uuid = %s", (session["dataset_uuid"],))
    assert client.seek.workflows[int(seek_id)] == {"cwl": "tool_convert.cwl", "tool_type": "script",
                                                   "project_id": 11, "token": "t"}


@pytest.mark.integration
def test_staged_tool_session_registers_on_approval(client):
    upload_id = _upload(client, _files(), commit_mode="on_approve")

    assert client.post(f"/datasets/uploads/{upload_id}/finalize").json()["status"] == "staged"
    assert client.seek.workflows == {}
    assert client.post(f"/datasets/uploads/{upload_id}/approve").status_code == 202

    assert client.get(f"/datasets/uploads/{upload_id}").json()["status"] == "completed"
    assert len(client.seek.workflows) == 1


@pytest.mark.integration
@pytest.mark.parametrize("body, detail", [
    ({"tool_type": None}, "tool_type"),
    ({"seek_project_id": None}, "seek_project_id"),
    ({"fhir": "auto"}, "FHIR"),
    ({"fhir_descriptions": {"patients": []}}, "FHIR"),
])
def test_tool_session_options_are_checked_at_creation(client, body, detail):
    r = _create(client, _files(), **body)

    assert r.status_code == 400 and detail in r.json()["detail"]
    assert _db_one(client, "SELECT count(*) FROM upload_session") == (0,)


@pytest.mark.integration
def test_tool_session_without_cwl_fails_finalize_and_keeps_receiving(client):
    upload_id = _upload(client, _files(cwl=False))

    r = client.post(f"/datasets/uploads/{upload_id}/finalize")

    assert r.status_code == 400 and "tool_*.cwl" in r.json()["detail"]
    assert client.get(f"/datasets/uploads/{upload_id}").json()["status"] == "receiving"


@pytest.mark.integration
def test_seek_failure_fails_the_session_and_approve_retries(client):
    client.seek.fail_register = True
    upload_id = _upload(client, _files())

    assert client.post(f"/datasets/uploads/{upload_id}/finalize").status_code == 202
    session = client.get(f"/datasets/uploads/{upload_id}").json()
    assert (session["status"], session["failure_stage"]) == ("failed", "commit")
    assert "not a member" in session["failure_message"]
    assert _db_one(client, "SELECT count(*) FROM dataset") == (0,)

    client.seek.fail_register = False
    assert client.post(f"/datasets/uploads/{upload_id}/approve").status_code == 202
    assert client.get(f"/datasets/uploads/{upload_id}").json()["status"] == "completed"


@pytest.mark.integration
def test_notebook_tool_session_is_registered_with_the_notebook_type(client):
    upload_id = _upload(client, _files(), tool_type="notebook")

    assert client.post(f"/datasets/uploads/{upload_id}/finalize").status_code == 202

    session = client.get(f"/datasets/uploads/{upload_id}").json()
    assert (session["status"], session["tool_type"]) == ("completed", "notebook")
    assert [w["tool_type"] for w in client.seek.workflows.values()] == ["notebook"]
