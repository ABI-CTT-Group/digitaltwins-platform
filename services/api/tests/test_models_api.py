"""Model datasets once committed: GET /models, one-shot POST /datasets, FHIR endpoints, delete."""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.routers import auth, datasets
from digitaltwins import models
from test_model_pipeline import make_model

UPLOADER = {"username": "alice", "token": "t", "claims": {"realm_access": {"roles": ["researcher"]}}}


@pytest.fixture
def client(platform_db, minio_bucket, hapi, s3, tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_STAGING_DIR", str(tmp_path / "staging"))
    # Model uploads go to the throwaway bucket instead of the real ``models`` one.
    monkeypatch.setattr(models, "CATEGORY", minio_bucket)
    monkeypatch.setattr(datasets, "DATASET_CATEGORIES", {minio_bucket})
    app = create_app()
    app.dependency_overrides[auth.validate_credentials] = lambda: UPLOADER
    c = TestClient(app)
    c.bucket, c.db, c.hapi, c.s3, c.tmp = minio_bucket, platform_db, hapi, s3, tmp_path
    return c


def _parts(root: Path):
    return [("files", (f"{root.name}/{p.relative_to(root).as_posix()}", p.read_bytes(), "application/octet-stream"))
            for p in sorted(root.rglob("*")) if p.is_file()]


def _post(client, root: Path, **params):
    data = {}
    if "fhir_descriptions" in params:
        data["fhir_descriptions"] = json.dumps(params.pop("fhir_descriptions"))
    return client.post("/datasets", params={"category": client.bucket, **params}, files=_parts(root), data=data)


def _db_one(client, sql, params=None):
    conn = client.db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchone()


def _committed(client, **params) -> str:
    r = _post(client, make_model(client.tmp / "model_skin_test"), **params)
    assert r.status_code == 200, r.text
    return r.json()["dataset_uuid"]


@pytest.mark.integration
def test_one_shot_model_upload_is_committed_through_a_session(client):
    r = _post(client, make_model(client.tmp / "model_skin_test"))

    assert r.status_code == 200, r.text
    dataset_uuid = r.json()["dataset_uuid"]
    assert r.json()["fhir_status"] == "none"
    assert _db_one(client, "SELECT category, dataset_name FROM dataset WHERE dataset_uuid = %s",
                   (dataset_uuid,)) == (client.bucket, "model_skin_test")
    assert _db_one(client, "SELECT count(*) FROM upload_session WHERE dataset_uuid = %s", (dataset_uuid,)) == (1,)


@pytest.mark.integration
def test_one_shot_model_without_primary_files_is_rejected(client):
    root = make_model(client.tmp / "m")
    for path in sorted((root / "primary").rglob("*"), reverse=True):
        path.unlink() if path.is_file() else path.rmdir()
    (root / "README.md").write_text("x")

    r = _post(client, root)

    assert r.status_code == 400 and "primary/" in r.json()["detail"]
    assert _db_one(client, "SELECT count(*) FROM dataset") == (0,)


@pytest.mark.integration
def test_one_shot_model_with_descriptions_pushes_a_device(client):
    dataset_uuid = _committed(client, fhir_descriptions={"model": {"version": "2.1"}})

    # TestClient ran the background push
    assert _db_one(client, "SELECT fhir_status FROM dataset WHERE dataset_uuid = %s", (dataset_uuid,)) == ("completed",)
    [device] = client.hapi.search("Device", identifier=dataset_uuid)
    assert device["version"] == [{"value": "2.1"}]


@pytest.mark.integration
def test_one_shot_model_with_invalid_descriptions_is_rejected(client):
    r = _post(client, make_model(client.tmp / "m"), fhir_descriptions={"model": {"framework": "nnUNet"}})

    assert r.status_code == 400 and "framework" in r.json()["detail"]


@pytest.mark.integration
def test_models_endpoint_lists_only_model_datasets(client, monkeypatch):
    dataset_uuid = _committed(client)
    monkeypatch.setattr(models, "CATEGORY", "models")  # the endpoint lists the real category
    with client.db() as conn, conn.cursor() as cur:
        cur.execute("UPDATE dataset SET category = 'models' WHERE dataset_uuid = %s", (dataset_uuid,))
        cur.execute("INSERT INTO dataset (dataset_name, category) VALUES ('m1', 'measurements')")

    listed = client.get("/models").json()["models"]

    assert [d["dataset_uuid"] for d in listed] == [dataset_uuid]


@pytest.mark.integration
def test_committed_model_can_be_annotated_pushed_and_previewed(client):
    dataset_uuid = _committed(client)

    tree = client.get(f"/datasets/{dataset_uuid}/fhir/tree").json()
    assert tree["descriptions"]["model"]["uuid"] == dataset_uuid
    bad = client.put(f"/datasets/{dataset_uuid}/fhir/annotation", json={"descriptions": {"model": {"x": "1"}}})
    assert bad.status_code == 400
    r = client.put(f"/datasets/{dataset_uuid}/fhir/annotation",
                   json={"descriptions": {"model": {"uuid": "forged", "version": "3"}}})
    assert r.status_code == 200 and r.json()["descriptions"]["model"]["uuid"] == dataset_uuid
    assert client.get(f"/datasets/{dataset_uuid}/fhir/preview").json()["resourceType"] == "Device"

    assert client.post(f"/datasets/{dataset_uuid}/fhir/push").status_code == 202

    [device] = client.hapi.search("Device", identifier=dataset_uuid)
    assert device["version"] == [{"value": "3"}]
    assert client.get(f"/datasets/{dataset_uuid}/fhir/preview").json()["id"] == device["id"]  # the pushed Device


@pytest.mark.integration
def test_deleting_a_model_removes_its_device(client):
    dataset_uuid = _committed(client, fhir_descriptions={"model": {}})
    assert client.hapi.search("Device", identifier=dataset_uuid)

    r = client.delete(f"/datasets/{dataset_uuid}")

    assert r.status_code == 200, r.text
    assert r.json()["fhir_resources_deleted"] == {"Device": 1}
    assert client.hapi.search("Device", identifier=dataset_uuid) == []
    assert _db_one(client, "SELECT count(*) FROM dataset WHERE dataset_uuid = %s", (dataset_uuid,)) == (0,)
