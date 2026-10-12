"""/datasets/uploads for model datasets: chunked session → validated → staged/approved → committed, optional Device."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.routers import auth
from digitaltwins import models

DESCRIPTION = Path(__file__).parent / "data" / "example_sds_dataset" / "dataset_description.xlsx"
UPLOADER = {"username": "alice", "token": "t", "claims": {"realm_access": {"roles": ["researcher"]}}}
TRAINER = "model_skin_test/primary/nnUNetTrainer__nnUNetPlans__3d_fullres"


@pytest.fixture
def client(platform_db, minio_bucket, hapi, tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_STAGING_DIR", str(tmp_path / "staging"))
    monkeypatch.setattr(models, "CATEGORY", minio_bucket)
    app = create_app()
    app.dependency_overrides[auth.validate_credentials] = lambda: UPLOADER
    c = TestClient(app)
    c.bucket, c.db, c.hapi = minio_bucket, platform_db, hapi
    return c


def _files(primary=True):
    files = [("model_skin_test/dataset_description.xlsx", DESCRIPTION.read_bytes())]
    if primary:
        files += [(f"{TRAINER}/fold_0/checkpoint_final.pth", b"weights"),
                  (f"{TRAINER}/dataset.json", b'{"labels": {"background": 0}}')]
    else:
        files.append(("model_skin_test/README.md", b"no primary"))
    return files


def _create(client, files, **body):
    manifest = [{"rel_path": rel, "size": len(data), "parts": 1} for rel, data in files]
    return client.post("/datasets/uploads", json={
        "name": "Skin model", "description": "From upload", "category": client.bucket,
        "source_kind": "folder", "manifest": manifest, **body,
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
def test_model_session_is_committed_on_finalize(client):
    upload_id = _upload(client, _files())

    r = client.post(f"/datasets/uploads/{upload_id}/finalize")

    assert r.status_code == 202, r.text
    assert r.json()["warnings"] == []
    session = client.get(f"/datasets/uploads/{upload_id}").json()  # TestClient ran the background job
    assert session["status"] == "completed", session
    assert _db_one(client, "SELECT category, fhir_status FROM dataset WHERE dataset_uuid = %s",
                   (session["dataset_uuid"],)) == (client.bucket, "none")


@pytest.mark.integration
def test_model_without_files_in_primary_fails_finalize_and_stays_receiving(client):
    upload_id = _upload(client, _files(primary=False))

    r = client.post(f"/datasets/uploads/{upload_id}/finalize")

    assert r.status_code == 400 and "primary/" in r.json()["detail"]
    assert client.get(f"/datasets/uploads/{upload_id}").json()["status"] == "receiving"


@pytest.mark.integration
def test_model_fhir_descriptions_must_be_a_model_object(client):
    r = _create(client, _files(), fhir_descriptions={"patients": []})

    assert r.status_code == 400 and "model" in r.json()["detail"]


@pytest.mark.integration
def test_unknown_inline_model_field_is_rejected_at_finalize(client):
    upload_id = _upload(client, _files(), fhir_descriptions={"model": {"framework": "nnUNet"}})

    r = client.post(f"/datasets/uploads/{upload_id}/finalize")

    assert r.status_code == 400 and "framework" in r.json()["detail"]


@pytest.mark.integration
def test_staged_model_is_annotated_then_approved_and_its_device_pushed(client):
    upload_id = _upload(client, _files(), commit_mode="on_approve")
    r = client.post(f"/datasets/uploads/{upload_id}/finalize")
    assert r.status_code == 200 and r.json() == {"upload_id": upload_id, "status": "staged", "warnings": []}

    tree = client.get(f"/datasets/uploads/{upload_id}/fhir/tree").json()
    assert tree["descriptions"]["model"] == {"uuid": "", "name": "Skin model", "description": "From upload",
                                             "version": ""}
    bad = client.put(f"/datasets/uploads/{upload_id}/fhir/annotation", json={"descriptions": {"model": {"x": "1"}}})
    assert bad.status_code == 400
    draft = {"model": {"description": "nnUNet skin", "version": "2.1"}}
    assert client.put(f"/datasets/uploads/{upload_id}/fhir/annotation",
                      json={"descriptions": draft}).status_code == 200
    preview = client.get(f"/datasets/uploads/{upload_id}/fhir/preview").json()
    assert preview["resourceType"] == "Device" and preview["version"] == [{"value": "2.1"}]

    assert client.post(f"/datasets/uploads/{upload_id}/approve").status_code == 202
    session = client.get(f"/datasets/uploads/{upload_id}").json()
    assert session["status"] == "completed", session
    dataset_uuid = session["dataset_uuid"]
    assert _db_one(client, "SELECT fhir_status FROM dataset WHERE dataset_uuid = %s", (dataset_uuid,)) == ("completed",)
    [device] = client.hapi.search("Device", identifier=dataset_uuid)
    assert device["note"] == [{"text": "nnUNet skin"}]


@pytest.mark.integration
def test_open_sessions_can_be_listed_per_category(client):
    model = _upload(client, _files(), commit_mode="on_approve")
    client.post(f"/datasets/uploads/{model}/finalize")
    other = client.post("/datasets/uploads", json={
        "name": "m", "category": "measurements", "source_kind": "folder",
        "manifest": [{"rel_path": "a", "size": 1, "parts": 1}],
    }).json()["upload_id"]

    listed = client.get("/datasets/uploads", params={"category": client.bucket}).json()["uploads"]
    everything = client.get("/datasets/uploads").json()["uploads"]

    assert [s["upload_id"] for s in listed] == [model]
    assert {s["upload_id"] for s in everything} == {model, other}
