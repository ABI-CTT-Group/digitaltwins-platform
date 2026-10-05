"""Launching a gui assay from the study dashboard: open its tool in /tool-view with the assay's input files.

Run from `backend/` (never inside the live container):
    python -m pytest tests/test_dashboard_assay_gui_launch.py
"""
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import HTTPException

from tests.tool_app import BACKEND_ROOT  # noqa: F401,I001  (sets DATABASE_PATH to a scratch SQLite first)
from app.main import app
from app.models.db_model import Base, BuildStatus, SessionLocal, Workflow, WorkflowBuild, engine
from app.router.dashboard import get_client, get_input_file_client, get_input_file_token
from fastapi.testclient import TestClient

client = TestClient(app)


def _json_response(payload):
    res = MagicMock()
    res.json.return_value = payload
    return res


def _assay(tag="gui", workflow_seek_id=95):
    return {"assay": {"id": "43", "attributes": {"title": "Test Assay 3: image visualisation", "tags": [tag]},
                      "configs": {"workflow_seek_id": workflow_seek_id, "cohort": ["1"], "inputs": [], "outputs": []}}}


GUI_INPUTS = {"workflow_seek_id": 95, "inputs": [{
    "name": "dicom_file", "dataset_uuid": "ds-1", "sample_type": "dicom",
    "files": [{"bucket": "measurements", "key": "ds-1/primary/sub-1/sam-1/a b.dcm", "name": "a b.dcm",
               "subject_id": "sub-1", "sample_id": "sam-1"}],
}]}


def add_gui_workflow(seek_id="95", age_minutes=0, **fields):
    """A gui workflow with one completed, bundled build registered against a SEEK workflow id."""
    expose = f"workflowvolview_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        wf = Workflow(name="workflow_volview", version="1.0", repository_url="local://v", source_type="local",
                      workflow_type="gui", is_sds=True)
        db.add(wf)
        db.flush()
        db.add(WorkflowBuild(workflow_id=wf.id, build_id=str(uuid.uuid4()), status=BuildStatus.COMPLETED.value,
                             expose_name=expose, seek_id=seek_id, tool_name="tool_volview",
                             bundle_path=f"tool-builds/{expose}/primary",
                             created_at=datetime(2026, 10, 5, 12) - timedelta(minutes=age_minutes), **fields))
        db.commit()
        return wf.id, expose


@pytest.fixture
def api():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    mock = AsyncMock()
    app.dependency_overrides[get_client] = lambda: mock
    app.dependency_overrides[get_input_file_client] = lambda: mock
    yield mock
    app.dependency_overrides.pop(get_client, None)
    app.dependency_overrides.pop(get_input_file_client, None)


# ── Launch ────────────────────────────────────────────────────────────


def test_gui_launch_opens_the_tool_view_for_the_assay(api):
    add_gui_workflow()
    api.get.return_value = _json_response(_assay())
    res = client.get("/api/dashboard/assay-launch", params={"seek_id": "43"})
    assert res.status_code == 200, res.text
    assert res.json() == {"type": "gui", "data": "/tool-view?assay=43"}
    api.post.assert_not_called()  # nothing to run server-side; the tool runs in the browser


def test_gui_launch_without_a_built_tool_explains_why(api):
    api.get.return_value = _json_response(_assay(workflow_seek_id=91))
    res = client.get("/api/dashboard/assay-launch", params={"seek_id": "43"})
    assert res.status_code == 200, res.text
    assert "no launchable GUI tool" in res.json()["message"]
    assert "type" not in res.json()


def test_script_launch_still_runs_the_assay(api):
    api.get.return_value = _json_response(_assay(tag="script", workflow_seek_id=89))
    api.post.return_value = _json_response({"monitor_url": "http://localhost/airflow/dags/workflow_89"})
    res = client.get("/api/dashboard/assay-launch", params={"seek_id": "43"})
    assert res.json() == {"type": "airflow", "data": "http://localhost/airflow/dags/workflow_89"}
    api.post.assert_called_once_with("/assays/43/run", {})


# ── Context for /tool-view (snake_case: the frontend's http client camelCases responses) ──


def _api_for_context(api, assay=None, gui_inputs=GUI_INPUTS):
    responses = {"/assays/43": _json_response(assay or _assay()), "/assays/43/gui-inputs": _json_response(gui_inputs)}
    api.get.side_effect = lambda path, *a, **kw: responses[path]


def test_gui_context_resolves_the_tool_and_maps_files_to_portal_urls(api):
    _, expose = add_gui_workflow()
    _api_for_context(api)
    res = client.get("/api/dashboard/assay-gui-context", params={"seek_id": "43"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["assay_id"] == "43"
    assert (body["tool"]["name"], body["tool"]["expose"]) == ("tool_volview", expose)
    assert body["tool"]["path"].startswith(f"/tool-builds/{expose}/primary/my-app.umd.js?v="), body["tool"]["path"]
    assert body["inputs"] == [{
        "name": "dicom_file", "dataset_uuid": "ds-1", "sample_type": "dicom",
        "files": [{"name": "a b.dcm", "subject_id": "sub-1", "sample_id": "sam-1",
                   "url": "/api/dashboard/assays/43/input-files/measurements/ds-1/primary/sub-1/sam-1/a%20b.dcm"}],
    }]


def test_gui_context_prefers_the_approved_build(api):
    wf_id, _ = add_gui_workflow(age_minutes=10, dataset_uuid="wf-v", tool_dataset_uuid="tool-v")
    with SessionLocal() as db:
        db.get(Workflow, wf_id).uuid = "wf-v"
        db.add(WorkflowBuild(workflow_id=wf_id, build_id=str(uuid.uuid4()), status=BuildStatus.COMPLETED.value,
                             expose_name="newer", seek_id="95", tool_name="tool_volview",
                             bundle_path="tool-builds/newer/primary", created_at=datetime(2026, 10, 5, 12)))
        db.commit()
    _api_for_context(api)
    res = client.get("/api/dashboard/assay-gui-context", params={"seek_id": "43"})
    assert res.json()["tool"]["path"].startswith("/tools/tool-v/primary/my-app.umd.js?v=")


def test_gui_context_without_a_built_tool_is_404(api):
    _api_for_context(api, assay=_assay(workflow_seek_id=91))
    res = client.get("/api/dashboard/assay-gui-context", params={"seek_id": "43"})
    assert res.status_code == 404
    assert "no launchable GUI tool" in res.json()["detail"]


def test_gui_context_passes_the_apis_input_error_through(api):
    add_gui_workflow()
    request = httpx.Request("GET", "http://api/assays/43/gui-inputs")
    error = httpx.HTTPStatusError("400", request=request,
                                  response=httpx.Response(400, json={"detail": "No samples found"}, request=request))
    responses = {"/assays/43": _json_response(_assay())}
    api.get.side_effect = lambda path, *a, **kw: responses[path] if path in responses else (_ for _ in ()).throw(error)
    res = client.get("/api/dashboard/assay-gui-context", params={"seek_id": "43"})
    assert res.status_code == 400
    assert "No samples found" in res.json()["detail"]


# ── File proxy ────────────────────────────────────────────────────────


def test_input_file_proxy_streams_the_apis_object(api):
    upstream = AsyncMock()
    upstream.headers = {"Content-Type": "application/dicom", "Content-Length": "7"}

    async def chunks():
        yield b"dicom"
        yield b"-a"

    upstream.aiter_bytes = chunks
    api.get_stream.return_value = upstream
    res = client.get("/api/dashboard/assays/43/input-files/measurements/ds-1/primary/sub-1/sam-1/a%20b.dcm")
    assert res.status_code == 200, res.text
    assert res.content == b"dicom-a"
    assert res.headers["content-type"] == "application/dicom"
    assert res.headers["content-length"] == "7"
    api.get_stream.assert_called_once_with("/assays/43/input-files/measurements/ds-1/primary/sub-1/sam-1/a%20b.dcm")


def test_input_file_proxy_passes_the_apis_refusal_through(api):
    request = httpx.Request("GET", "http://api/assays/43/input-files/measurements/other/x.dcm")
    api.get_stream.side_effect = httpx.HTTPStatusError(
        "403", request=request, response=httpx.Response(403, json={"detail": "Not one of this assay's input files."},
                                                        request=request))
    res = client.get("/api/dashboard/assays/43/input-files/measurements/other/x.dcm")
    assert res.status_code == 403
    assert "input files" in res.json()["detail"]


# VolView downloads `urls=` with the browser's plain fetch (no Authorization header), so /tool-view
# puts the user's token in a cookie scoped to the assay's input-files path and the proxy accepts it.


def test_input_file_token_comes_from_the_authorization_header_first():
    assert get_input_file_token(authorization="Bearer from-header", dt_assay_file_token="from-cookie") == "from-header"


def test_input_file_token_falls_back_to_the_scoped_cookie():
    assert get_input_file_token(authorization=None, dt_assay_file_token="from-cookie") == "from-cookie"


def test_input_file_without_any_token_is_401():
    with pytest.raises(HTTPException) as exc:
        get_input_file_token(authorization=None, dt_assay_file_token=None)
    assert exc.value.status_code == 401
