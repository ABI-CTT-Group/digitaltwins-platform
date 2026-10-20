"""GET /api/builder/workflow/gui-tool: the bundle /tool-view mounts for a SEEK workflow.

The platform API's dashboard asks this when it launches a gui assay; the portal owns the build registry.

Run from `services/builder/` (never inside the live container):
    python -m pytest tests/test_workflow_gui_tool_lookup.py
"""
import uuid
from datetime import datetime, timedelta

import pytest

from tests.tool_app import bearer, make_workflow_client  # noqa: I001  (sets DATABASE_PATH first)
from app.models.db_model import BuildStatus, SessionLocal, Workflow, WorkflowBuild


def add_gui_workflow(seek_id="95", age_minutes=0, workflow_type="gui", **fields):
    """A workflow with one completed, bundled build registered against a SEEK workflow id."""
    expose = f"workflowvolview_{uuid.uuid4().hex[:8]}"
    with SessionLocal() as db:
        wf = Workflow(name="workflow_volview", version="1.0", repository_url="local://v", source_type="local",
                      workflow_type=workflow_type, is_sds=True)
        db.add(wf)
        db.flush()
        db.add(WorkflowBuild(workflow_id=wf.id, build_id=str(uuid.uuid4()), status=BuildStatus.COMPLETED.value,
                             expose_name=expose, seek_id=seek_id, tool_name="tool_volview",
                             bundle_path=f"tool-builds/{expose}/primary",
                             created_at=datetime(2026, 10, 5, 12) - timedelta(minutes=age_minutes), **fields))
        db.commit()
        return wf.id, expose


@pytest.fixture
def client():
    return make_workflow_client()


def _lookup(client, seek_id="95", token="viewer"):
    return client.get("/api/builder/workflow/gui-tool", params={"workflow_seek_id": seek_id},
                      headers=bearer(token) if token else {})


def test_returns_the_registered_gui_build(client):
    _, expose = add_gui_workflow()
    res = _lookup(client)
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["name"], body["expose"]) == ("tool_volview", expose)
    assert body["path"].startswith(f"/tool-builds/{expose}/primary/my-app.umd.js?v="), body["path"]


def test_prefers_the_approved_build(client):
    wf_id, _ = add_gui_workflow(age_minutes=10, dataset_uuid="wf-v", tool_dataset_uuid="tool-v")
    with SessionLocal() as db:
        db.get(Workflow, wf_id).uuid = "wf-v"
        db.add(WorkflowBuild(workflow_id=wf_id, build_id=str(uuid.uuid4()), status=BuildStatus.COMPLETED.value,
                             expose_name="newer", seek_id="95", tool_name="tool_volview",
                             bundle_path="tool-builds/newer/primary", created_at=datetime(2026, 10, 5, 12)))
        db.commit()
    res = _lookup(client)
    assert res.json()["path"].startswith("/tools/tool-v/primary/my-app.umd.js?v="), res.text


@pytest.mark.parametrize("setup, seek_id", [
    (lambda: None, "95"),                                    # nothing registered
    (lambda: add_gui_workflow(workflow_type="script"), "95"),  # not a gui workflow
    (lambda: add_gui_workflow(seek_id="91"), "95"),          # another SEEK workflow
])
def test_without_a_launchable_build_is_404(client, setup, seek_id):
    setup()
    assert _lookup(client, seek_id).status_code == 404


def test_requires_a_token(client):
    add_gui_workflow()
    assert _lookup(client, token=None).status_code == 401
