"""Launching a notebook assay: ``POST /assays/{id}/run`` stages ``assay_<id>/`` in the user's
JupyterHub server and returns its URL. It does not need Airflow, which script assays still do.
"""
import sys
from pathlib import Path

import pytest

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from fastapi.testclient import TestClient

from app.main import app
from app.routers import assays
from app.routers.auth import validate_credentials
from app.routers.dataset_uploads import get_conn
from app.routers.dependencies import get_jupyterhub, get_minio_downloader, get_querier
from digitaltwins.jupyterhub.hub import HubTimeout

CONFIGS = {
    "workflow_seek_id": 97,
    "cohort": ["1"],
    "inputs": [{"name": "#main/raw_dataset", "dataset_uuid": "ds-1", "sample_type": "pre", "category": "measurements"}],
    "outputs": [],
}


class FakeQuerier:
    def __init__(self, tags=("notebook",)):
        self.tags = list(tags) if tags is not None else None

    def get_assay(self, assay_id, get_configs=False):
        assay = {"id": str(assay_id), "attributes": {"tags": self.tags}}
        if get_configs:
            assay["configs"] = CONFIGS
        return assay

    def get_dataset_samples(self, dataset_uuid, sample_type=None):
        return [{"subject_id": "sub-1", "sample_id": "sam-1"}]


class FakeDownloader:
    objects = {
        "workflows": {"wf-1/code/nb.ipynb": b"{}"},
        "measurements": {"ds-1/primary/sub-1/sam-1/a.dcm": b"a"},
    }

    def find_bucket(self, dataset_uuid):
        return next((b for b, objs in self.objects.items() if any(k.startswith(f"{dataset_uuid}/") for k in objs)), None)

    def list_objects(self, bucket, prefix):
        return sorted(k for k in self.objects.get(bucket, {}) if k.startswith(prefix))

    def open_object(self, bucket, key):
        return iter([self.objects[bucket][key]]), 1


class FakeHub:
    def __init__(self, fail=None):
        self.fail = fail
        self.files = {}

    def ensure_server(self, username):
        if self.fail:
            raise self.fail

    def list_paths(self, username, root):
        return set()

    def mkdir(self, username, path):
        pass

    def put_file(self, username, path, chunks):
        self.files[path] = b"".join(chunks)


@pytest.fixture
def hub():
    return FakeHub()


@pytest.fixture
def client(hub, monkeypatch):
    monkeypatch.setattr(assays, "AIRFLOW_ENABLED", False)
    monkeypatch.setattr(assays, "workflow_uuid_by_seek_id", lambda conn, seek_id: "wf-1")
    app.dependency_overrides[validate_credentials] = lambda: {"username": "tester", "token": "t"}
    app.dependency_overrides[get_querier] = lambda: FakeQuerier()
    app.dependency_overrides[get_conn] = lambda: object()
    app.dependency_overrides[get_minio_downloader] = lambda: FakeDownloader()
    app.dependency_overrides[get_jupyterhub] = lambda: hub
    yield TestClient(app)
    for dep in (validate_credentials, get_querier, get_conn, get_minio_downloader, get_jupyterhub):
        app.dependency_overrides.pop(dep, None)


def test_notebook_launch_stages_the_workspace_without_airflow(client, hub):
    res = client.post("/assays/43/run")
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["url"].endswith("/user/tester/lab/tree/assay_43")
    assert body["staged"] == 2 and body["skipped"] == 0
    assert hub.files == {
        "assay_43/nb.ipynb": b"{}",
        "assay_43/inputs/datasets/raw_dataset/primary/sub-1/sam-1/a.dcm": b"a",
    }


def test_notebook_launch_finds_the_type_tag_anywhere_in_the_tags(client):
    app.dependency_overrides[get_querier] = lambda: FakeQuerier(tags=("demo", "notebook"))
    assert client.post("/assays/43/run").status_code == 200


def test_script_launch_still_needs_airflow(client):
    app.dependency_overrides[get_querier] = lambda: FakeQuerier(tags=("script",))
    assert client.post("/assays/43/run").status_code == 503


def test_an_untagged_assay_is_400(client):
    app.dependency_overrides[get_querier] = lambda: FakeQuerier(tags=None)
    assert client.post("/assays/43/run").status_code == 400


def test_an_unregistered_workflow_is_400(client, monkeypatch):
    def missing(conn, seek_id):
        raise LookupError("Workflow 97 is not registered in the platform.")
    monkeypatch.setattr(assays, "workflow_uuid_by_seek_id", missing)
    res = client.post("/assays/43/run")
    assert res.status_code == 400
    assert "not registered" in res.json()["detail"]


def test_a_server_that_does_not_start_is_504(client, hub):
    hub.fail = HubTimeout("did not start")
    assert client.post("/assays/43/run").status_code == 504


# ── Workspace download/upload: the token they send to the user's server ──


def test_workspace_reads_send_the_configured_token(monkeypatch, tmp_path):
    monkeypatch.setenv("JUPYTERHUB_API_TOKEN", "tok")
    sent = []

    class Listing:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"type": "directory", "content": []}

    monkeypatch.setattr(assays.requests, "get", lambda url, headers=None, **kw: sent.append(headers) or Listing())
    assays._download_jupyter_folder("tester", "assay_43/outputs/datasets", str(tmp_path))
    assert sent == [{"Authorization": "token tok"}]


def test_workspace_reads_without_a_token_fail_instead_of_using_a_default(monkeypatch, tmp_path):
    monkeypatch.delenv("JUPYTERHUB_API_TOKEN", raising=False)
    monkeypatch.setattr(assays.requests, "get", lambda *a, **kw: pytest.fail("must not call the hub"))
    with pytest.raises(KeyError, match="JUPYTERHUB_API_TOKEN"):
        assays._download_jupyter_folder("tester", "assay_43/outputs/datasets", str(tmp_path))
