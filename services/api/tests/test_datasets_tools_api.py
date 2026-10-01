"""POST /datasets for tool datasets: validated, stored in MinIO + Postgres, registered in SEEK (faked)."""
import io
import json
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
def client(platform_db, minio_bucket, seek, hapi, s3, tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_STAGING_DIR", str(tmp_path / "staging"))
    # Tool uploads go to the throwaway bucket instead of the real ``tools`` one.
    monkeypatch.setattr(tools, "CATEGORY", minio_bucket)
    monkeypatch.setattr(datasets, "DATASET_CATEGORIES", {minio_bucket})
    app = create_app()
    app.dependency_overrides[auth.validate_credentials] = lambda: UPLOADER
    c = TestClient(app)
    c.bucket, c.db, c.seek, c.s3, c.hapi = minio_bucket, platform_db, seek, s3, hapi
    return c


def _tool_files(cwl=True):
    files = {"dataset_description.xlsx": DESCRIPTION.read_bytes(), "code/tool_convert.py": b"print('hi')\n"}
    files["primary/tool_convert.cwl" if cwl else "primary/notes.txt"] = CWL.encode() if cwl else b"no tool here"
    return files


def _folder_parts(files, prefix="sds_tool_convert"):
    return [("files", (f"{prefix}/{name}", content, "application/octet-stream")) for name, content in files.items()]


def _post(client, parts, data=None, **params):
    params = {"category": client.bucket, "tool_type": "script", "seek_project_id": 11, **params}
    return client.post("/datasets", params={k: v for k, v in params.items() if v is not None}, files=parts, data=data)


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


@pytest.mark.integration
def test_gui_tool_is_registered_with_the_gui_type(client):
    files = {**_tool_files(), "code/index.html": b"<html></html>", "code/src/main.ts": b"export {}\n"}
    del files["code/tool_convert.py"]

    r = _post(client, _folder_parts(files), tool_type="gui")

    assert r.status_code == 200, r.text
    assert client.seek.workflows[r.json()["seek_id"]]["tool_type"] == "gui"
    assert f"{r.json()['dataset_uuid']}/code/src/main.ts" in _keys(client)


@pytest.mark.integration
def test_seek_is_registered_before_the_dataset_is_stored(client, monkeypatch):
    # The caller's token is only good for minutes, so SEEK must be called
    # before the (possibly long) MinIO upload, not after it.
    from digitaltwins.core.uploader import Uploader

    events, upload = [], Uploader.upload_dataset
    register = client.seek.register_tool
    monkeypatch.setattr(client.seek, "register_tool", lambda *a: events.append("seek") or register(*a))
    monkeypatch.setattr(Uploader, "upload_dataset", lambda *a, **kw: events.append("store") or upload(*a, **kw))

    r = _post(client, _folder_parts(_tool_files()))

    assert r.status_code == 200, r.text
    assert events == ["seek", "store"]


@pytest.mark.integration
def test_storage_failure_after_seek_removes_the_seek_workflow(client, monkeypatch):
    from digitaltwins.core.uploader import Uploader

    def fail(*a, **kw):
        raise RuntimeError("MinIO unreachable")

    monkeypatch.setattr(Uploader, "upload_dataset", fail)

    r = _post(client, _folder_parts(_tool_files()))

    assert r.status_code == 500 and "MinIO unreachable" in r.json()["detail"]
    assert client.seek.workflows == {} and client.seek.deleted == [101]
    assert _db_one(client, "SELECT count(*) FROM dataset") == (0,)


@pytest.mark.integration
def test_a_failing_rollback_still_reports_the_seek_error(client, monkeypatch):
    from digitaltwins.core.deleter import Deleter
    from digitaltwins.tools import pipeline

    def fail(*a, **kw):
        raise RuntimeError("boom")

    monkeypatch.setattr(pipeline, "_link", fail)
    monkeypatch.setattr(Deleter, "delete_dataset", fail)

    r = _post(client, _folder_parts(_tool_files()))

    assert r.status_code == 502 and "boom" in r.json()["detail"]
    assert client.seek.deleted == [101]


SUBJECTS = Path(__file__).parent / "data" / "example_sds_dataset" / "subjects.xlsx"
SAMPLES = Path(__file__).parent / "data" / "example_sds_dataset" / "samples.xlsx"


@pytest.mark.integration
def test_tool_subjects_and_samples_are_stored_as_files_but_not_as_rows(client):
    files = {**_tool_files(), "subjects.xlsx": SUBJECTS.read_bytes(), "samples.xlsx": SAMPLES.read_bytes()}

    r = _post(client, _folder_parts(files))

    assert r.status_code == 200, r.text
    uuid = r.json()["dataset_uuid"]
    assert _db_one(client, "SELECT count(*) FROM subject") == (0,)
    assert _db_one(client, "SELECT count(*) FROM sample") == (0,)
    assert _db_one(client, "SELECT count(*) FROM dataset_mapping") == (0,)
    assert {f"{uuid}/subjects.xlsx", f"{uuid}/samples.xlsx"} <= set(_keys(client))


@pytest.mark.integration
def test_tool_type_is_stored_on_the_dataset(client):
    r = _post(client, _folder_parts(_tool_files()), tool_type="notebook")

    assert r.status_code == 200, r.text
    assert _db_one(client, "SELECT tool_type FROM dataset WHERE dataset_uuid = %s",
                   (r.json()["dataset_uuid"],)) == ("notebook",)


def _activity_definitions(client):
    return [r for ref, r in client.hapi.store.items() if ref.startswith("ActivityDefinition/")]


def _fhir_status(client, uuid):
    return _db_one(client, "SELECT fhir_status FROM dataset WHERE dataset_uuid = %s", (uuid,))[0]


@pytest.mark.integration
def test_tool_without_fhir_pushes_nothing(client):
    r = _post(client, _folder_parts(_tool_files()))

    assert r.status_code == 200, r.text
    assert _fhir_status(client, r.json()["dataset_uuid"]) == "none"
    assert _activity_definitions(client) == []


@pytest.mark.integration
def test_auto_fhir_pushes_an_activity_definition_keyed_by_the_dataset_uuid(client):
    r = _post(client, _folder_parts(_tool_files()), fhir="auto")

    assert r.status_code == 200, r.text
    uuid = r.json()["dataset_uuid"]
    assert r.json()["fhir_status"] == "pending"
    assert _fhir_status(client, uuid) == "completed"  # TestClient ran the background push
    [ad] = _activity_definitions(client)
    assert ad["identifier"][0]["value"] == uuid and ad["name"] == "sds_tool_convert"


@pytest.mark.integration
def test_supplied_descriptions_are_stored_with_server_owned_ids(client):
    wt = {"version": "1.0.0", "input": [{"id": "src", "resourceType": "ImagingStudy"}]}

    r = _post(client, _folder_parts(_tool_files()), data={"fhir_descriptions": json.dumps({"workflow_tool": wt})})

    assert r.status_code == 200, r.text
    uuid = r.json()["dataset_uuid"]
    stored = client.get(f"/datasets/{uuid}/fhir/annotation").json()["descriptions"]["workflow_tool"]
    assert (stored["uuid"], stored["title"], stored["version"]) == (uuid, "Tool - convert", "1.0.0")
    assert stored["input"] == wt["input"]
    assert _fhir_status(client, uuid) == "completed"


@pytest.mark.integration
def test_descriptions_naming_an_unknown_port_are_rejected_before_anything_is_stored(client):
    bad = {"workflow_tool": {"input": [{"id": "nope"}]}}

    r = _post(client, _folder_parts(_tool_files()), data={"fhir_descriptions": json.dumps(bad)})

    assert r.status_code == 400 and "nope" in r.json()["detail"]
    assert _db_one(client, "SELECT count(*) FROM dataset") == (0,)
    assert client.seek.workflows == {}


@pytest.mark.integration
def test_a_failed_tool_push_keeps_the_dataset_and_can_be_retried(client):
    client.hapi.fail_push = True
    uuid = _post(client, _folder_parts(_tool_files()), fhir="auto").json()["dataset_uuid"]
    assert _fhir_status(client, uuid) == "failed"
    assert _db_one(client, "SELECT seek_id FROM dataset WHERE dataset_uuid = %s", (uuid,))[0] is not None

    client.hapi.fail_push = False
    r = client.post(f"/datasets/{uuid}/fhir/push")

    assert r.status_code == 202, r.text
    assert _fhir_status(client, uuid) == "completed"
    assert len(_activity_definitions(client)) == 1


@pytest.mark.integration
def test_an_edited_tool_annotation_replaces_the_activity_definition(client):
    uuid = _post(client, _folder_parts(_tool_files()), fhir="auto").json()["dataset_uuid"]
    descriptions = client.get(f"/datasets/{uuid}/fhir/annotation").json()["descriptions"]
    descriptions["workflow_tool"]["description"] = "Edited"

    assert client.put(f"/datasets/{uuid}/fhir/annotation", json={"descriptions": descriptions}).status_code == 200
    assert client.post(f"/datasets/{uuid}/fhir/push").status_code == 202

    [ad] = _activity_definitions(client)
    assert ad["description"] == "Edited"


@pytest.mark.integration
def test_put_rejects_a_tool_annotation_naming_an_unknown_port(client):
    uuid = _post(client, _folder_parts(_tool_files()), fhir="auto").json()["dataset_uuid"]

    r = client.put(f"/datasets/{uuid}/fhir/annotation",
                   json={"descriptions": {"workflow_tool": {"output": [{"id": "nope"}]}}})

    assert r.status_code == 400 and "nope" in r.json()["detail"]


@pytest.mark.integration
def test_tool_tree_offers_prefilled_descriptions_and_the_cwl_ports(client):
    uuid = _post(client, _folder_parts(_tool_files())).json()["dataset_uuid"]

    tree = client.get(f"/datasets/{uuid}/fhir/tree").json()

    assert tree["descriptions"]["workflow_tool"]["uuid"] == uuid
    assert tree["ports"]["inputs"] == [{"id": "src", "type": "Directory", "doc": "measurements"}]


@pytest.mark.integration
def test_tool_preview_returns_the_descriptions(client):
    uuid = _post(client, _folder_parts(_tool_files()), fhir="auto").json()["dataset_uuid"]

    r = client.get(f"/datasets/{uuid}/fhir/preview")

    assert r.status_code == 200, r.text
    assert r.json()["workflow_tool"]["uuid"] == uuid


@pytest.mark.integration
def test_deleting_a_tool_removes_its_activity_definition(client):
    uuid = _post(client, _folder_parts(_tool_files()), fhir="auto").json()["dataset_uuid"]

    r = client.delete(f"/datasets/{uuid}")

    assert r.status_code == 200, r.text
    assert _activity_definitions(client) == []
    assert r.json()["fhir_resources_deleted"] == {"ActivityDefinition": 1}
