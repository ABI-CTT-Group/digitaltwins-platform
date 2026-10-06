"""Launching a gui assay: the files its configured inputs resolve to, and streaming one of them.

``GET /assays/{id}/gui-inputs`` lists, per non-model input, the MinIO objects of the samples
``_discover_samples`` picks (configured sample type, cohort subjects).
``GET /assays/{id}/input-files/{bucket}/{key}`` streams one such object, and refuses keys
outside the assay's input datasets.
"""
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from fastapi.testclient import TestClient

from app.main import app
from app.routers.auth import validate_credentials
from app.routers.dependencies import get_minio_downloader, get_querier

CONFIGS = {
    "workflow_seek_id": 95,
    "cohort": ["1"],
    "inputs": [
        {"name": "dicom_file", "dataset_uuid": "ds-1", "sample_type": "dicom", "category": "measurements"},
        {"name": "model", "dataset_uuid": "m-1", "sample_type": None, "category": "models"},
    ],
    "outputs": [],
}


class FakeQuerier:
    def __init__(self, configs=CONFIGS):
        self.configs = configs

    def get_assay(self, assay_id, get_configs=False):
        assay = {"id": str(assay_id), "attributes": {"tags": ["gui"]}}
        if get_configs:
            assay["configs"] = self.configs
        return assay

    def get_dataset_samples(self, dataset_uuid, sample_type=None):
        assert (dataset_uuid, sample_type) == ("ds-1", "dicom")
        return [{"subject_id": "sub-1", "sample_id": "sam-1"}, {"subject_id": "sub-2", "sample_id": "sam-2"}]


class FakeDownloader:
    """MinIO as two buckets of ``key -> bytes``."""

    def __init__(self):
        self.buckets = {
            "measurements": {
                "ds-1/primary/sub-1/sam-1/a.dcm": b"dicom-a",
                "ds-1/primary/sub-1/sam-1/b.dcm": b"dicom-b",
                "ds-1/primary/sub-2/sam-2/c.dcm": b"dicom-c",
                "other/primary/sub-1/sam-1/secret.dcm": b"not-yours",
            },
            "models": {"m-1/primary/model.h5": b"weights"},
        }

    def find_bucket(self, dataset_uuid):
        return next((b for b, objs in self.buckets.items() if any(k.startswith(f"{dataset_uuid}/") for k in objs)), None)

    def list_objects(self, bucket, prefix):
        return sorted(k for k in self.buckets.get(bucket, {}) if k.startswith(prefix))

    def open_object(self, bucket, key):
        body = self.buckets.get(bucket, {}).get(key)
        if body is None:
            raise FileNotFoundError(key)
        return iter([body]), len(body)


@pytest.fixture
def client():
    app.dependency_overrides[validate_credentials] = lambda: {"username": "tester", "token": "t"}
    app.dependency_overrides[get_querier] = lambda: FakeQuerier()
    app.dependency_overrides[get_minio_downloader] = lambda: FakeDownloader()
    yield TestClient(app)
    for dep in (validate_credentials, get_querier, get_minio_downloader):
        app.dependency_overrides.pop(dep, None)


def test_gui_inputs_lists_the_cohorts_sample_files_per_input(client):
    res = client.get("/assays/43/gui-inputs")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["workflow_seek_id"] == 95
    [inp] = body["inputs"]  # the model input is not a file input
    assert (inp["name"], inp["dataset_uuid"], inp["sample_type"]) == ("dicom_file", "ds-1", "dicom")
    assert inp["files"] == [
        {"bucket": "measurements", "key": "ds-1/primary/sub-1/sam-1/a.dcm", "name": "a.dcm",
         "subject_id": "sub-1", "sample_id": "sam-1"},
        {"bucket": "measurements", "key": "ds-1/primary/sub-1/sam-1/b.dcm", "name": "b.dcm",
         "subject_id": "sub-1", "sample_id": "sam-1"},
    ]


def test_gui_inputs_without_a_saved_config_is_400(client):
    app.dependency_overrides[get_querier] = lambda: FakeQuerier(configs=None)
    res = client.get("/assays/43/gui-inputs")
    assert res.status_code == 400
    assert "No configs found" in res.json()["detail"]


def test_input_file_streams_the_object(client):
    res = client.get("/assays/43/input-files/measurements/ds-1/primary/sub-1/sam-1/a.dcm")
    assert res.status_code == 200, res.text
    assert res.content == b"dicom-a"
    assert res.headers["content-type"] == "application/dicom"
    assert res.headers["content-length"] == "7"


def test_input_file_outside_the_assays_input_datasets_is_403(client):
    res = client.get("/assays/43/input-files/measurements/other/primary/sub-1/sam-1/secret.dcm")
    assert res.status_code == 403


def test_input_file_of_a_model_input_is_403(client):
    res = client.get("/assays/43/input-files/models/m-1/primary/model.h5")
    assert res.status_code == 403


def test_input_file_with_a_dot_dot_segment_is_403(client):
    # Encoded so the client does not collapse the segment before the request is sent.
    res = client.get("/assays/43/input-files/measurements/ds-1/primary/%2e%2e/other/primary/sub-1/sam-1/secret.dcm")
    assert res.status_code == 403


def test_missing_input_file_is_404(client):
    res = client.get("/assays/43/input-files/measurements/ds-1/primary/sub-1/sam-1/missing.dcm")
    assert res.status_code == 404
    assert "missing.dcm" in res.json()["detail"]
