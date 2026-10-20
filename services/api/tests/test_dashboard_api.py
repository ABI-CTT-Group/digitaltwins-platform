"""The portal's study dashboard: SEEK's programme tree, assay config and launch, reshaped for the frontend.

Served at /api/dashboard (moved here from portal-backend). Responses are snake_case: the frontend's
http client camelCases them.
"""
import pytest
import requests
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.routers import assays, dashboard
from app.routers.auth import validate_credentials
from app.routers.dataset_uploads import get_conn
from app.routers.dependencies import get_jupyterhub, get_minio_downloader, get_querier, get_uploader
from test_assay_gui_launch import FakeDownloader

CONFIGS = {
    "assay_seek_id": 43, "assay_uuid": "a-1", "workflow_seek_id": 95, "workflow_uuid": "w-1", "cohort": ["1", "x"],
    "ready": True,
    "inputs": [{"name": "dicom_file", "dataset_uuid": "ds-1", "sample_type": "dicom", "category": "measurements"}],
    "outputs": [{"name": "out", "category": "measurements", "dataset_name": "Result", "sample_name": "seg"}],
}


class FakeQuerier:
    """SEEK as a few canned resources; an assay's tags and configs can be set per test."""

    def __init__(self, tags=("gui",), configs=CONFIGS):
        self.tags, self.configs = list(tags), configs
        self.study = {"id": "11", "type": "studies", "relationships": {"assays": {"data": [{"id": "43", "type": "assays"}]}}}
        self.assay_relationships = {"workflows": [], "study": {"data": {"id": "11"}},
                                    "investigation": {"data": {"id": "7"}}}

    def get_programs(self, get_details=False):
        return [{"id": "1", "type": "programmes", "attributes": {"title": "P", "description": "d"}}]

    def get_program(self, program_id):
        return {"id": str(program_id), "relationships": {"projects": {"data": [{"id": "12", "type": "projects"}]}}}

    def get_project(self, project_id):
        return {"id": str(project_id), "type": "projects", "attributes": {"title": "Proj", "description": None}}

    def get_investigation(self, investigation_id):
        return {"id": str(investigation_id), "type": "investigations", "attributes": {"title": "I", "description": None}}

    def get_study(self, study_id):
        return self.study

    def get_assay(self, assay_id, get_configs=False):
        assay = {"id": str(assay_id), "type": "assays",
                 "attributes": {"title": "Test Assay 3", "tags": self.tags, "description": None},
                 "relationships": self.assay_relationships}
        if get_configs:
            assay["configs"] = self.configs
        return assay

    def get_workflows(self):
        return [{"id": "89", "attributes": {"title": "Workflow - Image conversion"}}]

    def get_workflow(self, workflow_id):
        return {"id": str(workflow_id),
                "attributes": {"title": "Workflow - Image conversion", "tags": ["workflow", "script"],
                               "internals": {"inputs": [{"id": "in", "name": None, "description": "measurements"}],
                                             "outputs": [{"id": "o", "name": "seg", "description": "measurements"}]}},
                "relationships": {"projects": {"data": [{"id": "12", "type": "projects"}]}}}

    def get_datasets(self, descriptions=False, categories=None, keywords=None):
        assert (descriptions, categories, keywords) == (False, ["measurements"], None)
        return [{"dataset_uuid": "ds-1", "dataset_name": "Scans"}]

    def get_dataset_sample_types(self, dataset_uuid):
        return ["dicom"]

    # Used by the assays routes behind gui-inputs and input-files.
    def get_dataset_samples(self, dataset_uuid, sample_type=None):
        return [{"subject_id": "sub-1", "sample_id": "sam-1"}]


@pytest.fixture
def seek():
    return FakeQuerier()


@pytest.fixture
def client(seek, monkeypatch):
    overrides = {
        validate_credentials: lambda: {"username": "tester", "token": "t", "claims": {}},
        get_querier: lambda: seek,
        dashboard.get_input_file_querier: lambda: seek,
        get_minio_downloader: lambda: FakeDownloader(),
        get_conn: lambda: "conn",
        get_jupyterhub: lambda: "hub",
        get_uploader: lambda: "uploader",
    }
    app.dependency_overrides.update(overrides)
    # gui launches ask portal-backend for the tool; tests that care replace this.
    monkeypatch.setattr(dashboard, "_fetch_gui_tool", lambda workflow_seek_id, token: None)
    yield TestClient(app, root_path="/api")
    for dep in overrides:
        app.dependency_overrides.pop(dep, None)


GUI_TOOL = {"name": "tool_volview", "path": "/tool-builds/x/primary/my-app.umd.js?v=1", "expose": "x"}


# ── The programme tree ────────────────────────────────────────────────


def test_programmes_are_reshaped(client):
    res = client.get("/dashboard/programmes")
    assert res.status_code == 200, res.text
    assert res.json() == [{"seek_id": "1", "name": "P", "category": "Programmes", "description": "d"}]


def test_a_programmes_children_are_its_projects(client):
    res = client.get("/dashboard/category-children", params={"seek_id": "1", "category": "Programmes"})
    assert res.json() == [{"seek_id": "12", "name": "Proj", "category": "Projects", "description": None}]


def test_assay_card_uses_the_first_sop_that_links_a_workflow(client, seek):
    # The API walks Assay -> SOPs: a plain protocol SOP first (no workflows), then the workflow link.
    seek.tags = ["script"]
    seek.assay_relationships = {"workflows": [[], [{"id": "39", "type": "workflows"}]]}
    res = client.get("/dashboard/category-children", params={"seek_id": "11", "category": "Studies"})
    assert res.status_code == 200, res.text
    [card] = res.json()
    assert (card["workflow_seek_id"], card["tag"]) == ("39", "script")


def test_assay_card_tag_is_the_type_tag_wherever_it_is(client, seek):
    seek.tags = ["demo", "Notebook"]
    [card] = client.get("/dashboard/category-children", params={"seek_id": "11", "category": "Studies"}).json()
    assert card["tag"] == "notebook"


def test_assay_card_carries_the_assays_projects(client, seek):
    seek.assay_relationships = {"workflows": [], "projects": {"data": [{"id": "12", "type": "projects"}]}}
    [card] = client.get("/dashboard/category-children", params={"seek_id": "11", "category": "Studies"}).json()
    assert card["project_ids"] == ["12"]


def test_assays_have_no_children(client):
    res = client.get("/dashboard/category-children", params={"seek_id": "43", "category": "Assays"})
    assert (res.status_code, res.json()) == (200, None)


def test_an_assays_place_in_the_tree(client):
    res = client.get("/dashboard/assays/43")
    assert res.json() == {"seek_id": "43", "name": "Test Assay 3",
                          "relationships": {"study_seek_id": "11", "investigation_seek_id": "7"}}


# ── Workflows and datasets for the config dialog ──────────────────────


def test_workflow_list_carries_each_workflows_type_and_projects(client):
    res = client.get("/dashboard/workflows")
    assert res.json() == [{"seek_id": "89", "uuid": "", "name": "Workflow - Image conversion",
                           "type": "script", "project_ids": ["12"]}]


def test_workflow_detail_lists_its_inputs_and_outputs(client):
    res = client.get("/dashboard/workflow-detail", params={"seek_id": "89"})
    assert res.json() == {
        "seek_id": "89", "uuid": "", "name": "Workflow - Image conversion",
        "inputs": [{"input": {"name": "in", "category": "measurements"},
                    "dataset_selected_uuid": "", "sample_selected_type": ""}],
        "outputs": [{"output": {"name": "seg", "category": "measurements"},
                     "dataset_name": "New dataset", "sample_name": "seg"}],
    }


def test_datasets_of_a_category(client):
    res = client.get("/dashboard/datasets", params={"category": "measurements"})
    assert res.json() == [{"uuid": "ds-1", "name": "Scans"}]


def test_dataset_detail_is_its_sample_types(client):
    assert client.get("/dashboard/dataset-detail", params={"uuid": "ds-1"}).json() == ["dicom"]


# ── Assay config ──────────────────────────────────────────────────────


DETAILS = {
    "uuid": "",
    "seek_id": "42",
    "workflow": {"uuid": "", "seek_id": "39", "inputs": [], "outputs": []},
    "number_of_participants": [1, 2],
    "is_assay_ready_to_launch": False,
}


def test_save_assay_details_links_the_workflow(client, monkeypatch):
    saved = []

    async def configure(assay_data, uploader, credentials):
        saved.append((assay_data, uploader, credentials["token"]))
        return {"message": "ok"}

    monkeypatch.setattr(assays, "configure_assay", configure)
    res = client.post("/dashboard/assay-details", json=DETAILS)
    assert (res.status_code, res.json()) == (200, True)
    [(data, uploader, token)] = saved
    assert (data.assay_seek_id, data.workflow_seek_id, data.cohort, data.link_workflow) == (42, 39, ["1", "2"], True)
    assert (uploader, token) == ("uploader", "t")


def test_save_assay_details_without_a_workflow_is_rejected(client, monkeypatch):
    monkeypatch.setattr(assays, "configure_assay", lambda *a, **kw: pytest.fail("must not save"))
    details = {**DETAILS, "workflow": {**DETAILS["workflow"], "seek_id": ""}}
    res = client.post("/dashboard/assay-details", json=details)
    assert (res.status_code, res.json()["detail"]) == (400, "Select a workflow")


def test_save_assay_details_with_an_invalid_config_is_422(client, monkeypatch):
    monkeypatch.setattr(assays, "configure_assay", lambda *a, **kw: pytest.fail("must not save"))
    res = client.post("/dashboard/assay-details", json={**DETAILS, "seek_id": "not-a-number"})
    assert res.status_code == 422


def test_saved_assay_details_are_reshaped_for_the_dialog(client):
    res = client.get("/dashboard/assay-details", params={"seek_id": "43"})
    assert res.json() == {
        "seek_id": "43", "uuid": "a-1",
        "workflow": {
            "seek_id": "95", "uuid": "w-1",
            "inputs": [{"input": {"name": "dicom_file", "category": "measurements"},
                        "dataset_selected_uuid": "ds-1", "sample_selected_type": "dicom"}],
            "outputs": [{"output": {"name": "out", "category": "measurements"},
                         "dataset_name": "Result", "sample_name": "seg"}],
        },
        "number_of_participants": [1],
        "is_assay_ready_to_launch": True,
    }


def test_an_unconfigured_assay_has_no_details(client, seek):
    seek.configs = None
    assert client.get("/dashboard/assay-details", params={"seek_id": "43"}).json() is None


# ── Launch ────────────────────────────────────────────────────────────


@pytest.fixture
def runs(monkeypatch):
    calls = []

    def run(assay_id, credentials, querier, conn, downloader, hub):
        calls.append((assay_id, credentials["token"], conn, hub))
        return {"monitor_url": "http://localhost/airflow/dags/workflow_89", "url": "http://localhost/jupyter/u"}

    monkeypatch.setattr(assays, "run_assay", run)
    return calls


def test_gui_launch_opens_the_tool_view_for_the_assay(client, runs, monkeypatch):
    asked = []
    monkeypatch.setattr(dashboard, "_fetch_gui_tool", lambda seek_id, token: asked.append((seek_id, token)) or GUI_TOOL)
    res = client.get("/dashboard/assay-launch", params={"seek_id": "43"})
    assert res.json() == {"type": "gui", "data": "/tool-view?assay=43"}
    assert asked == [(95, "t")]
    assert runs == []  # nothing to run server-side; the tool runs in the browser


def test_gui_launch_without_a_built_tool_explains_why(client, runs):
    body = client.get("/dashboard/assay-launch", params={"seek_id": "43"}).json()
    assert "no launchable GUI tool" in body["message"]
    assert "type" not in body


def test_script_launch_runs_the_assay(client, seek, runs, monkeypatch):
    seek.tags = ["script"]
    monkeypatch.setattr(dashboard, "_fetch_gui_tool", lambda *a: pytest.fail("script launches don't ask the portal"))
    res = client.get("/dashboard/assay-launch", params={"seek_id": "43"})
    assert res.json() == {"type": "airflow", "data": "http://localhost/airflow/dags/workflow_89"}
    assert runs == [(43, "t", "conn", "hub")]


def test_notebook_launch_finds_the_type_tag_anywhere_in_the_tags(client, seek, runs):
    seek.tags = ["demo", "notebook"]
    res = client.get("/dashboard/assay-launch", params={"seek_id": "43"})
    assert res.json() == {"type": "notebook", "data": "http://localhost/jupyter/u"}
    assert len(runs) == 1


@pytest.mark.parametrize("tags", [[], ["demo"], ["script", "notebook"]])
def test_launch_without_exactly_one_type_tag_explains_why(client, seek, runs, tags):
    seek.tags = tags
    res = client.get("/dashboard/assay-launch", params={"seek_id": "43"})
    assert "exactly one of script, notebook or gui" in res.json()["message"]
    assert runs == []


# ── Context for /tool-view ────────────────────────────────────────────


def test_gui_context_resolves_the_tool_and_maps_files_to_dashboard_urls(client, seek, monkeypatch):
    monkeypatch.setattr(dashboard, "_fetch_gui_tool", lambda seek_id, token: GUI_TOOL)
    seek.configs = {**CONFIGS, "cohort": ["1"]}
    res = client.get("/dashboard/assay-gui-context", params={"seek_id": "43"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert (body["assay_id"], body["tool"]) == ("43", GUI_TOOL)
    [inp] = body["inputs"]
    assert (inp["name"], inp["dataset_uuid"], inp["sample_type"]) == ("dicom_file", "ds-1", "dicom")
    # Under the API's public prefix, so the browser (and VolView) reach this router again.
    assert inp["files"][0] == {"name": "a.dcm", "subject_id": "sub-1", "sample_id": "sam-1",
                               "url": "/api/dashboard/assays/43/input-files/measurements/ds-1/primary/sub-1/sam-1/a.dcm"}


def test_gui_context_quotes_file_urls(client, monkeypatch):
    monkeypatch.setattr(dashboard, "_fetch_gui_tool", lambda seek_id, token: GUI_TOOL)
    monkeypatch.setattr(assays, "get_assay_gui_inputs", lambda assay_id, querier, downloader: {"inputs": [{
        "name": "dicom_file", "files": [{"bucket": "measurements", "key": "ds-1/primary/sub-1/sam-1/a b.dcm",
                                         "name": "a b.dcm", "subject_id": "sub-1", "sample_id": "sam-1"}]}]})
    [inp] = client.get("/dashboard/assay-gui-context", params={"seek_id": "43"}).json()["inputs"]
    assert inp["files"][0]["url"] == "/api/dashboard/assays/43/input-files/measurements/ds-1/primary/sub-1/sam-1/a%20b.dcm"


def test_gui_context_without_a_built_tool_is_404(client):
    res = client.get("/dashboard/assay-gui-context", params={"seek_id": "43"})
    assert res.status_code == 404
    assert "no launchable GUI tool" in res.json()["detail"]


def test_gui_context_passes_the_input_error_through(client, seek, monkeypatch):
    monkeypatch.setattr(dashboard, "_fetch_gui_tool", lambda seek_id, token: GUI_TOOL)
    seek.configs = {**CONFIGS, "inputs": []}
    res = client.get("/dashboard/assay-gui-context", params={"seek_id": "43"})
    assert res.status_code == 400
    assert "No inputs found" in res.json()["detail"]


# ── File proxy (VolView fetches these with a cookie, not a header) ────


def test_input_file_streams_the_object(client):
    res = client.get("/dashboard/assays/43/input-files/measurements/ds-1/primary/sub-1/sam-1/a.dcm")
    assert res.status_code == 200, res.text
    assert res.content == b"dicom-a"
    assert (res.headers["content-type"], res.headers["content-length"]) == ("application/dicom", "7")


def test_input_file_outside_the_assays_inputs_is_403(client):
    res = client.get("/dashboard/assays/43/input-files/measurements/other/primary/sub-1/sam-1/secret.dcm")
    assert res.status_code == 403


def test_input_file_token_comes_from_the_authorization_header_first():
    assert dashboard.get_input_file_token(authorization="Bearer from-header", dt_assay_file_token="c") == "from-header"


def test_input_file_token_falls_back_to_the_scoped_cookie():
    assert dashboard.get_input_file_token(authorization=None, dt_assay_file_token="from-cookie") == "from-cookie"


def test_input_file_without_any_token_is_401():
    with pytest.raises(HTTPException) as exc:
        dashboard.get_input_file_token(authorization=None, dt_assay_file_token=None)
    assert exc.value.status_code == 401


def test_an_invalid_cookie_token_is_401(client, monkeypatch):
    # The cookie token is verified like a bearer token before anything is read as its user.
    app.dependency_overrides.pop(dashboard.get_input_file_querier)

    def reject(credentials):
        assert (credentials.scheme, credentials.credentials) == ("Bearer", "stale")
        raise HTTPException(status_code=401, detail="Signature has expired")

    monkeypatch.setattr(dashboard, "auth_bearer", reject)
    client.cookies.set("dt_assay_file_token", "stale")
    res = client.get("/dashboard/assays/43/input-files/measurements/ds-1/primary/sub-1/sam-1/a.dcm")
    assert res.status_code == 401


# ── Results ───────────────────────────────────────────────────────────


def test_results_submit_uploads_the_workspace_datasets(client, monkeypatch):
    async def upload(assay_id, timestamp, uploader, querier, credentials):
        return {"uploaded": [assay_id, timestamp, uploader]}

    monkeypatch.setattr(assays, "upload_workspace_datasets", upload)
    res = client.post("/dashboard/assay-results-submit", params={"seek_id": "38"})
    assert res.json() == {"uploaded": [38, None, "uploader"]}


def test_assay_download_streams_the_workspace_zip(client, monkeypatch):
    from fastapi.responses import StreamingResponse

    def download(assay_id, timestamp, querier, credentials):
        assert (assay_id, timestamp) == (38, None)
        return StreamingResponse(iter([b"zip-1", b"zip-2"]), media_type="application/zip",
                                 headers={"Content-Disposition": 'attachment; filename="assay_38_results.zip"'})

    monkeypatch.setattr(assays, "download_workspace_dataset", download)
    res = client.get("/dashboard/assay-download", params={"seek_id": "38"})
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/zip"
    assert res.headers["content-disposition"] == 'attachment; filename="assay_38_results.zip"'
    assert res.content == b"zip-1zip-2"


def test_assay_download_needs_an_assay(client):
    assert client.get("/dashboard/assay-download").status_code == 400


# ── Asking portal-backend for the gui tool ────────────────────────────


class _Response:
    def __init__(self, status_code, payload=None):
        self.status_code, self._payload = status_code, payload

    def json(self):
        return self._payload


@pytest.fixture
def portal(monkeypatch):
    monkeypatch.setenv("PORTAL_BACKEND_URL", "http://portal-backend:8000")
    calls = []

    def get(url, params=None, headers=None, timeout=None):
        calls.append((url, params, headers))
        return portal.response

    monkeypatch.setattr(dashboard.requests, "get", get)
    portal.calls = calls
    return portal


def test_fetch_gui_tool_asks_the_portal_as_the_user(portal):
    portal.response = _Response(200, GUI_TOOL)
    assert dashboard._fetch_gui_tool(95, "tok") == GUI_TOOL
    assert portal.calls == [("http://portal-backend:8000/api/portal/workflow/gui-tool",
                             {"workflow_seek_id": 95}, {"Authorization": "Bearer tok"})]


def test_fetch_gui_tool_without_a_tool_is_none(portal):
    portal.response = _Response(404, {"detail": "none"})
    assert dashboard._fetch_gui_tool(95, "tok") is None


@pytest.mark.parametrize("seek_id", [None, ""])
def test_fetch_gui_tool_without_a_workflow_asks_nothing(portal, seek_id):
    assert dashboard._fetch_gui_tool(seek_id, "tok") is None
    assert portal.calls == []


def test_fetch_gui_tool_when_the_portal_fails_is_502(portal):
    portal.response = _Response(500)
    with pytest.raises(HTTPException) as exc:
        dashboard._fetch_gui_tool(95, "tok")
    assert exc.value.status_code == 502


def test_fetch_gui_tool_when_the_portal_is_unreachable_is_502(portal, monkeypatch):
    def unreachable(*a, **kw):
        raise requests.ConnectionError("no route to portal-backend")

    monkeypatch.setattr(dashboard.requests, "get", unreachable)
    with pytest.raises(HTTPException) as exc:
        dashboard._fetch_gui_tool(95, "tok")
    assert exc.value.status_code == 502


# ── Routes ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("path", ["/dashboard/health", "/dashboard/workflow-cwl", "/dashboard/workflow",
                                  "/dashboard/assay-project"])
def test_disabled_stubs_are_gone(client, path):
    assert client.get(path).status_code == 404


def test_no_route_repeats_the_public_prefix():
    # The /api prefix lives outside the app (gateway + uvicorn --root-path); a route under /api would be
    # stripped twice.
    assert [r.path for r in app.routes if r.path.startswith("/api")] == []
