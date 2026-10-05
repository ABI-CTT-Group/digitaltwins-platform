"""POST /assays: save an assay's config, and with ``link_workflow`` also link the workflow in SEEK."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import create_app
from app.routers import assays, auth
from app.routers.dependencies import get_uploader
from digitaltwins.core.assay_workflow_link import WorkflowNotInAssayProject

RESEARCHER = {"username": "alice", "token": "t", "claims": {"realm_access": {"roles": ["researcher"]}}}
CLINICIAN = {"username": "bob", "token": "t", "claims": {"realm_access": {"roles": ["clinician"]}}}
CONFIG = {"assay_seek_id": 42, "workflow_seek_id": 39, "cohort": ["1"], "ready": True, "inputs": [], "outputs": []}


class FakeUploader:
    def __init__(self):
        self.saved = []
        self.fail = False

    def configure_assay(self, payload):
        if self.fail:
            raise RuntimeError("db down")
        self.saved.append(payload)
        return "uuid-1"


@pytest.fixture
def seek_link(monkeypatch):
    calls = {"link": [], "undo": 0, "fail": None}

    def fake_link(token, assay_id, workflow_id):
        if isinstance(calls["fail"], Exception):
            raise calls["fail"]
        if calls["fail"]:
            raise RuntimeError(calls["fail"])
        calls["link"].append((token, assay_id, workflow_id))

        def undo():
            calls["undo"] += 1
        return undo

    monkeypatch.setattr(assays, "_link_workflow_in_seek", fake_link)
    return calls


def _client(user, uploader):
    app = create_app()
    app.dependency_overrides[auth.validate_credentials] = lambda: user
    app.dependency_overrides[get_uploader] = lambda: uploader
    return TestClient(app)


def test_config_without_link_does_not_touch_seek(seek_link):
    uploader = FakeUploader()
    res = _client(CLINICIAN, uploader).post("/assays", json=CONFIG)
    assert res.status_code == 200
    assert seek_link["link"] == []
    assert uploader.saved[0]["workflow_seek_id"] == 39


def test_link_workflow_links_in_seek_then_saves(seek_link):
    uploader = FakeUploader()
    res = _client(RESEARCHER, uploader).post("/assays", json={**CONFIG, "link_workflow": True})
    assert res.status_code == 200, res.text
    assert seek_link["link"] == [("t", 42, 39)]
    assert "link_workflow" not in uploader.saved[0]
    assert seek_link["undo"] == 0


def test_link_workflow_requires_an_upload_role(seek_link):
    uploader = FakeUploader()
    res = _client(CLINICIAN, uploader).post("/assays", json={**CONFIG, "link_workflow": True})
    assert res.status_code == 403
    assert seek_link["link"] == [] and uploader.saved == []


def test_seek_failure_is_a_bad_gateway_and_nothing_is_saved(seek_link):
    seek_link["fail"] = "SEEK SOP create failed (422): not a member"
    uploader = FakeUploader()
    res = _client(RESEARCHER, uploader).post("/assays", json={**CONFIG, "link_workflow": True})
    assert res.status_code == 502
    assert "not a member" in res.json()["detail"]
    assert uploader.saved == []


def test_failed_save_undoes_the_seek_link(seek_link):
    uploader = FakeUploader()
    uploader.fail = True
    res = _client(RESEARCHER, uploader).post("/assays", json={**CONFIG, "link_workflow": True})
    assert res.status_code == 500
    assert seek_link["undo"] == 1


def test_workflow_from_another_project_is_a_bad_request(seek_link):
    seek_link["fail"] = WorkflowNotInAssayProject("Workflow 39 is not in any of assay 42's projects (12).")
    uploader = FakeUploader()
    res = _client(RESEARCHER, uploader).post("/assays", json={**CONFIG, "link_workflow": True})
    assert res.status_code == 400
    assert "not in any of assay 42's projects" in res.json()["detail"]
    assert uploader.saved == []
