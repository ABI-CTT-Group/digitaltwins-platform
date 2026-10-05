"""Dashboard routes behind the assay config dialog's workflow selector."""
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.router.dashboard import get_client

client = TestClient(app)

DETAILS = {
    "uuid": "",
    "seek_id": "42",
    "workflow": {"uuid": "", "seek_id": "39", "inputs": [], "outputs": []},
    "number_of_participants": [1, 2],
    "is_assay_ready_to_launch": False,
}


def _json_response(payload):
    res = MagicMock()
    res.json.return_value = payload
    return res


@pytest.fixture
def api():
    mock = AsyncMock()
    app.dependency_overrides[get_client] = lambda: mock
    yield mock
    app.dependency_overrides.pop(get_client, None)


def test_save_assay_details_asks_the_api_to_link_the_workflow(api):
    api.post.return_value = _json_response({"message": "ok"})
    res = client.post("/api/dashboard/assay-details", json=DETAILS)
    assert res.status_code == 200
    path, body = api.post.call_args.args
    assert path == "/assays"
    assert body["workflow_seek_id"] == 39
    assert body["link_workflow"] is True


def test_save_assay_details_without_a_workflow_is_rejected(api):
    details = {**DETAILS, "workflow": {**DETAILS["workflow"], "seek_id": ""}}
    res = client.post("/api/dashboard/assay-details", json=details)
    assert res.status_code == 400
    assert res.json()["detail"] == "Select a workflow"
    api.post.assert_not_called()


def test_assay_card_uses_the_first_sop_that_links_a_workflow(api):
    study = {"study": {"relationships": {"assays": {"data": [{"id": "42", "type": "assays"}]}}}}
    # The API walks Assay -> SOPs: a plain protocol SOP first (no workflows), then the workflow link.
    assay = {"assay": {"id": "42", "type": "assays",
                       "attributes": {"title": "Test Assay 2: script", "tags": ["script"], "description": None},
                       "relationships": {"workflows": [[], [{"id": "39", "type": "workflows"}]]}}}
    api.get.side_effect = lambda path, *a, **kw: _json_response(study if path == "/studies/11" else assay)
    res = client.get("/api/dashboard/category-children", params={"seek_id": "11", "category": "Studies"})
    assert res.status_code == 200
    [card] = res.json()
    assert card["workflow_seek_id"] == "39"
    assert card["tag"] == "script"


def test_assay_card_carries_the_assays_projects(api):
    study = {"study": {"relationships": {"assays": {"data": [{"id": "42", "type": "assays"}]}}}}
    assay = {"assay": {"id": "42", "type": "assays",
                       "attributes": {"title": "Test Assay 2: script", "tags": ["script"], "description": None},
                       "relationships": {"workflows": [],
                                         "projects": {"data": [{"id": "12", "type": "projects"}]}}}}
    api.get.side_effect = lambda path, *a, **kw: _json_response(study if path == "/studies/11" else assay)
    res = client.get("/api/dashboard/category-children", params={"seek_id": "11", "category": "Studies"})
    [card] = res.json()
    assert card["project_ids"] == ["12"]


def test_workflow_list_carries_each_workflows_projects(api):
    listing = {"workflows": [{"id": "89", "attributes": {"title": "Workflow - Image conversion"}}]}
    detail = {"workflow": {"id": "89", "attributes": {"tags": ["workflow", "script"]},
                           "relationships": {"projects": {"data": [{"id": "12", "type": "projects"}]}}}}
    api.get.side_effect = lambda path, *a, **kw: _json_response(listing if path == "/workflows" else detail)
    res = client.get("/api/dashboard/workflows")
    assert res.json() == [{"seek_id": "89", "uuid": "", "name": "Workflow - Image conversion",
                           "type": "script", "project_ids": ["12"]}]
