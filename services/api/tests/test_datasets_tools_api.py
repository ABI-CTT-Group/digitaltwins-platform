"""POST /datasets for tool datasets: validated, stored in MinIO + Postgres, registered in SEEK (faked)."""
import io
import sys
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.routers import auth, datasets
from digitaltwins import tools

DESCRIPTION = Path(__file__).parent / "data" / "example_sds_dataset" / "dataset_description.xlsx"
UPLOADER = {"username": "alice", "token": "t", "claims": {"realm_access": {"roles": ["admin"]}}}
CWL = """cwlVersion: v1.2
class: CommandLineTool
label: "Tool - convert"
baseCommand: [python, tool_convert.py]
inputs:
  src:
    type: Directory
    doc: measurements
outputs: []
"""


@pytest.fixture
def client(platform_db, minio_bucket, seek, s3, tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_STAGING_DIR", str(tmp_path / "staging"))
    # Tool uploads go to the throwaway bucket instead of the real ``tools`` one.
    monkeypatch.setattr(tools, "CATEGORY", minio_bucket)
    monkeypatch.setattr(datasets, "DATASET_CATEGORIES", {minio_bucket})
    app = create_app()
    app.dependency_overrides[auth.validate_credentials] = lambda: UPLOADER
    c = TestClient(app)
    c.bucket, c.db, c.seek, c.s3 = minio_bucket, platform_db, seek, s3
    return c


def _tool_files(cwl=True):
    files = {"dataset_description.xlsx": DESCRIPTION.read_bytes(), "code/tool_convert.py": b"print('hi')\n"}
    files["primary/tool_convert.cwl" if cwl else "primary/notes.txt"] = CWL.encode() if cwl else b"no tool here"
    return files


def _folder_parts(files, prefix="sds_tool_convert"):
    return [("files", (f"{prefix}/{name}", content, "application/octet-stream")) for name, content in files.items()]


def _post(client, parts, **params):
    params = {"category": client.bucket, "tool_type": "script", "seek_project_id": 11, **params}
    return client.post("/datasets", params={k: v for k, v in params.items() if v is not None}, files=parts)


def _db_one(client, sql, params=None):
    conn = client.db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def _keys(client):
    pages = client.s3.get_paginator("list_objects_v2").paginate(Bucket=client.bucket)
    try:
        return sorted(obj["Key"] for page in pages for obj in page.get("Contents", []))
    except client.s3.exceptions.NoSuchBucket:
        return []


@pytest.mark.integration
def test_tool_folder_is_stored_and_registered_in_seek(client):
    r = _post(client, _folder_parts(_tool_files()))

    assert r.status_code == 200, r.text
    body = r.json()
    uuid, seek_id = body["dataset_uuid"], body["seek_id"]
    assert _db_one(client, "SELECT category, dataset_name, seek_id FROM dataset WHERE dataset_uuid = %s",
                   (uuid,)) == (client.bucket, "sds_tool_convert", str(seek_id))
    assert f"{uuid}/primary/tool_convert.cwl" in _keys(client)
    assert f"{uuid}/code/tool_convert.py" in _keys(client)
    assert client.seek.workflows[seek_id] == {"cwl": "tool_convert.cwl", "tool_type": "script",
                                              "project_id": 11, "token": "t"}
    assert _db_one(client, "SELECT count(*) FROM upload_session") == (0,)


@pytest.mark.integration
def test_tool_zip_upload(client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in _tool_files().items():
            zf.writestr(f"sds_tool_convert/{name}", content)

    r = _post(client, [("files", ("sds_tool_convert.zip", buf.getvalue(), "application/zip"))])

    assert r.status_code == 200, r.text
    assert r.json()["seek_id"] in client.seek.workflows


@pytest.mark.integration
@pytest.mark.parametrize("missing", ["tool_type", "seek_project_id"])
def test_tool_upload_needs_tool_type_and_seek_project(client, missing):
    r = _post(client, _folder_parts(_tool_files()), **{missing: None})

    assert r.status_code == 400 and missing in r.json()["detail"]
    assert _db_one(client, "SELECT count(*) FROM dataset") == (0,)


@pytest.mark.integration
def test_unknown_tool_type_is_rejected(client):
    assert _post(client, _folder_parts(_tool_files()), tool_type="spreadsheet").status_code == 422


@pytest.mark.integration
def test_tool_without_cwl_is_rejected_before_anything_is_stored(client):
    r = _post(client, _folder_parts(_tool_files(cwl=False)))

    assert r.status_code == 400 and "tool_*.cwl" in r.json()["detail"]
    assert _db_one(client, "SELECT count(*) FROM dataset") == (0,)
    assert _keys(client) == []
    assert client.seek.workflows == {}


@pytest.mark.integration
def test_seek_failure_rolls_the_dataset_back(client):
    client.seek.fail_register = True

    r = _post(client, _folder_parts(_tool_files()))

    assert r.status_code == 502 and "not a member" in r.json()["detail"]
    assert _db_one(client, "SELECT count(*) FROM dataset") == (0,)
    assert _keys(client) == []


@pytest.mark.integration
def test_get_dataset_returns_the_tools_cwl(client):
    uuid = _post(client, _folder_parts(_tool_files())).json()["dataset_uuid"]

    r = client.get(f"/datasets/{uuid}", params={"get_cwl": True})

    assert r.status_code == 200, r.text
    cwl = r.json()["dataset"]["cwl"]
    assert cwl["label"] == "Tool - convert"
    assert cwl["inputs"]["src"]["doc"] == "measurements"


@pytest.mark.integration
def test_notebook_tool_is_registered_with_the_notebook_type(client):
    files = {**_tool_files(), "code/tool_convert.ipynb": b'{"cells": [], "nbformat": 4, "nbformat_minor": 5}'}
    del files["code/tool_convert.py"]

    r = _post(client, _folder_parts(files), tool_type="notebook")

    assert r.status_code == 200, r.text
    assert client.seek.workflows[r.json()["seek_id"]]["tool_type"] == "notebook"
    assert f"{r.json()['dataset_uuid']}/code/tool_convert.ipynb" in _keys(client)
