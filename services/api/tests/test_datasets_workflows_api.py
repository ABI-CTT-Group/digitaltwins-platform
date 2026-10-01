"""POST /datasets for workflow datasets: each tool stored as its own tool dataset, the workflow
stored and linked to them, everything registered in SEEK (faked) — all or nothing."""
import io
import sys
import uuid
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.routers import auth, datasets
from digitaltwins import tools, workflows
from digitaltwins.core.uploader import Uploader

DESCRIPTION = Path(__file__).parent / "data" / "example_sds_dataset" / "dataset_description.xlsx"
UPLOADER = {"username": "alice", "token": "t", "claims": {"realm_access": {"roles": ["admin"]}}}

TOOL_CWL = """cwlVersion: v1.2
class: CommandLineTool
label: "Tool - {name}"
baseCommand: [python, tool_{name}.py]
inputs:
  src: {{type: Directory, inputBinding: {{prefix: --input}}}}
outputs:
  out: {{type: File, outputBinding: {{glob: "*.out"}}}}
"""
SCRIPT_WORKFLOW_CWL = """cwlVersion: v1.2
class: Workflow
label: "Workflow - convert"
doc: Converts twice.
inputs: {src: Directory}
outputs:
  nifti: {type: File, outputSource: to_nifti/out}
  nrrd: {type: File, outputSource: to_nrrd/out}
steps:
  to_nifti: {run: tool_to_nifti.cwl, in: {src: src}, out: [out]}
  to_nrrd: {run: tool_to_nrrd.cwl, in: {src: src}, out: [out]}
"""
SINGLE_WORKFLOW_CWL = """cwlVersion: v1.2
class: Workflow
label: "Workflow - {name}"
inputs: {{src: Directory}}
outputs:
  result: {{type: File, outputSource: {name}/out}}
steps:
  {name}: {{run: tool_{name}.cwl, in: {{src: src}}, out: [out]}}
"""


def script_files():
    return {
        "dataset_description.xlsx": DESCRIPTION.read_bytes(),
        "README.md": b"# convert\n",
        "primary/workflow_convert.cwl": SCRIPT_WORKFLOW_CWL.encode(),
        "primary/tool_to_nifti.cwl": TOOL_CWL.format(name="to_nifti").encode(),
        "primary/tool_to_nrrd.cwl": TOOL_CWL.format(name="to_nrrd").encode(),
        "code/workflow_convert.py": b"# the DAG\n",
        "code/tool_to_nifti.py": b"print('nifti')\n",
        "code/tool_to_nrrd.py": b"print('nrrd')\n",
    }


def gui_files():
    return {
        "dataset_description.xlsx": DESCRIPTION.read_bytes(),
        "primary/workflow_viewer.cwl": SINGLE_WORKFLOW_CWL.format(name="viewer").encode(),
        "primary/tool_viewer.cwl": TOOL_CWL.format(name="viewer").encode(),
        "code/package.json": b"{}",
        "code/src/app.ts": b"export {}\n",
    }


def notebook_files():
    return {
        "dataset_description.xlsx": DESCRIPTION.read_bytes(),
        "primary/workflow_select.cwl": SINGLE_WORKFLOW_CWL.format(name="select").encode(),
        "primary/tool_select.cwl": TOOL_CWL.format(name="select").encode(),
        "code/tool_select/select.ipynb": b"{}",
        "code/notes.txt": b"workflow-only\n",
    }


@pytest.fixture
def tool_bucket(s3, minio_bucket):
    """A second throwaway bucket for the tool datasets (``minio_bucket`` holds the workflows)."""
    bucket = f"dt-test-{uuid.uuid4().hex[:10]}"
    try:
        yield bucket
    finally:
        try:
            for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket):
                for obj in page.get("Contents", []):
                    s3.delete_object(Bucket=bucket, Key=obj["Key"])
            s3.delete_bucket(Bucket=bucket)
        except s3.exceptions.ClientError:
            pass  # never created


@pytest.fixture
def client(platform_db, minio_bucket, tool_bucket, seek, hapi, s3, tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_STAGING_DIR", str(tmp_path / "staging"))
    monkeypatch.setattr(workflows, "CATEGORY", minio_bucket)
    monkeypatch.setattr(tools, "CATEGORY", tool_bucket)
    monkeypatch.setattr(datasets, "DATASET_CATEGORIES", {minio_bucket, tool_bucket})
    app = create_app()
    app.dependency_overrides[auth.validate_credentials] = lambda: UPLOADER
    c = TestClient(app)
    c.bucket, c.tool_bucket, c.db, c.seek, c.s3, c.hapi = minio_bucket, tool_bucket, platform_db, seek, s3, hapi
    return c


def _folder_parts(files, prefix="wf_convert"):
    return [("files", (f"{prefix}/{name}", content, "application/octet-stream")) for name, content in files.items()]


def _post(client, parts, data=None, **params):
    params = {"category": client.bucket, "workflow_type": "script", "seek_project_id": 11, **params}
    return client.post("/datasets", params={k: v for k, v in params.items() if v is not None}, files=parts, data=data)


def _db(client, sql, params=None):
    conn = client.db()
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def _keys(client, bucket):
    pages = client.s3.get_paginator("list_objects_v2").paginate(Bucket=bucket)
    try:
        return sorted(obj["Key"] for page in pages for obj in page.get("Contents", []))
    except client.s3.exceptions.NoSuchBucket:
        return []


def _nothing_stored(client):
    assert _db(client, "SELECT count(*) FROM dataset") == [(0,)]
    assert _keys(client, client.bucket) == [] and _keys(client, client.tool_bucket) == []


@pytest.mark.integration
def test_script_workflow_stores_each_tool_as_a_tool_dataset_and_links_them(client):
    r = _post(client, _folder_parts(script_files()))

    assert r.status_code == 200, r.text
    body = r.json()
    wf_uuid, wf_seek = body["dataset_uuid"], body["seek_id"]
    steps = {t["step_id"]: t for t in body["tools"]}
    assert set(steps) == {"to_nifti", "to_nrrd"}

    assert _db(client, "SELECT category, dataset_name, seek_id, workflow_type, tool_type FROM dataset "
                       "WHERE dataset_uuid = %s", (wf_uuid,)) == [(client.bucket, "wf_convert", str(wf_seek), "script", None)]
    for step, name in (("to_nifti", "tool_to_nifti"), ("to_nrrd", "tool_to_nrrd")):
        tool = steps[step]
        assert _db(client, "SELECT category, dataset_name, seek_id, tool_type, workflow_type FROM dataset "
                           "WHERE dataset_uuid = %s", (tool["dataset_uuid"],)) == [
            (client.tool_bucket, name, str(tool["seek_id"]), "script", None)]
    assert sorted(_db(client, "SELECT step_id, tool_dataset_uuid::text FROM workflow_tool "
                              "WHERE workflow_dataset_uuid = %s", (wf_uuid,))) == sorted(
        (s, t["dataset_uuid"]) for s, t in steps.items())
    assert _db(client, "SELECT count(*) FROM subject") == [(0,)]

    # The workflow dataset is stored as uploaded; each tool gets only its own CWL and code.
    wf_keys = _keys(client, client.bucket)
    for rel in ("primary/workflow_convert.cwl", "primary/tool_to_nifti.cwl", "code/workflow_convert.py",
                "code/tool_to_nrrd.py", "dataset_description.xlsx"):
        assert f"{wf_uuid}/{rel}" in wf_keys
    nifti = steps["to_nifti"]["dataset_uuid"]
    assert [k for k in _keys(client, client.tool_bucket) if k.startswith(nifti)] == sorted(
        f"{nifti}/{rel}" for rel in ("README.md", "code/tool_to_nifti.py", "dataset_description.xlsx",
                                     "primary/tool_to_nifti.cwl"))

    seek = client.seek.workflows
    assert seek[wf_seek] == {"cwl": "workflow_convert.cwl", "workflow_type": "script",
                             "tools": ["tool_to_nifti.cwl", "tool_to_nrrd.cwl"], "project_id": 11, "token": "t"}
    assert seek[steps["to_nifti"]["seek_id"]] == {"cwl": "tool_to_nifti.cwl", "tool_type": "script",
                                                  "project_id": 11, "token": "t"}
    assert len(seek) == 3


@pytest.mark.integration
def test_gui_workflow_tool_gets_the_whole_code_folder(client):
    r = _post(client, _folder_parts(gui_files(), prefix="wf_viewer"), workflow_type="gui")

    assert r.status_code == 200, r.text
    [tool] = r.json()["tools"]
    keys = _keys(client, client.tool_bucket)
    assert f"{tool['dataset_uuid']}/code/package.json" in keys
    assert f"{tool['dataset_uuid']}/code/src/app.ts" in keys
    assert client.seek.workflows[tool["seek_id"]]["tool_type"] == "gui"
    assert client.seek.workflows[r.json()["seek_id"]]["workflow_type"] == "gui"


@pytest.mark.integration
def test_notebook_workflow_tool_uses_its_code_subfolder(client):
    r = _post(client, _folder_parts(notebook_files(), prefix="wf_select"), workflow_type="notebook")

    assert r.status_code == 200, r.text
    [tool] = r.json()["tools"]
    keys = [k for k in _keys(client, client.tool_bucket) if k.startswith(tool["dataset_uuid"])]
    assert f"{tool['dataset_uuid']}/code/select.ipynb" in keys
    assert not [k for k in keys if k.endswith("notes.txt")]


@pytest.mark.integration
def test_workflow_zip_upload(client):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, content in script_files().items():
            zf.writestr(f"wf_convert/{name}", content)

    r = _post(client, [("files", ("wf_convert.zip", buf.getvalue(), "application/zip"))])

    assert r.status_code == 200, r.text
    assert len(r.json()["tools"]) == 2


@pytest.mark.integration
@pytest.mark.parametrize("missing", ["workflow_type", "seek_project_id"])
def test_workflow_upload_needs_workflow_type_and_seek_project(client, missing):
    r = _post(client, _folder_parts(script_files()), **{missing: None})

    assert r.status_code == 400 and missing in r.json()["detail"]
    _nothing_stored(client)


@pytest.mark.integration
def test_unknown_workflow_type_is_rejected(client):
    assert _post(client, _folder_parts(script_files()), workflow_type="pipeline").status_code == 422


@pytest.mark.integration
def test_invalid_layout_is_rejected_before_anything_is_registered(client):
    r = _post(client, _folder_parts(script_files()), workflow_type="gui")

    assert r.status_code == 400 and "exactly one step" in r.json()["detail"]
    _nothing_stored(client)
    assert client.seek.workflows == {}


@pytest.mark.integration
def test_workflow_seek_failure_removes_the_tools_registered_before_it(client):
    client.seek.fail_register_workflow = True

    r = _post(client, _folder_parts(script_files()))

    assert r.status_code == 502 and "SEEK" in r.json()["detail"]
    _nothing_stored(client)
    assert client.seek.workflows == {} and sorted(client.seek.deleted) == [101, 102]


@pytest.mark.integration
def test_storage_failure_after_seek_rolls_everything_back(client, monkeypatch):
    real = Uploader.upload_dataset

    def fail_for_the_workflow(self, dataset_path, category, **kwargs):
        if category == client.bucket:
            raise RuntimeError("MinIO unreachable")
        return real(self, dataset_path, category, **kwargs)

    monkeypatch.setattr(Uploader, "upload_dataset", fail_for_the_workflow)

    r = _post(client, _folder_parts(script_files()))

    assert r.status_code == 500 and "MinIO unreachable" in r.json()["detail"]
    _nothing_stored(client)
    assert client.seek.workflows == {} and sorted(client.seek.deleted) == [101, 102, 103]



# ── FHIR ───────────────────────────────────────────────────────────────


def _fhir_status(client, dataset_uuid):
    return _db(client, "SELECT fhir_status FROM dataset WHERE dataset_uuid = %s", (dataset_uuid,))[0][0]


@pytest.mark.integration
def test_fhir_auto_pushes_tool_activity_definitions_then_the_plan_definition(client):
    r = _post(client, _folder_parts(script_files()), fhir="auto")

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["fhir_status"] == "pending"
    wf_uuid = body["dataset_uuid"]
    assert _fhir_status(client, wf_uuid) == "completed"  # TestClient ran the background push
    for tool in body["tools"]:
        assert _fhir_status(client, tool["dataset_uuid"]) == "completed"
    store = client.hapi.store
    assert client.hapi.types() == {"ActivityDefinition": 2, "PlanDefinition": 1}
    [plan] = [r for r in store.values() if r["resourceType"] == "PlanDefinition"]
    assert plan["identifier"][0]["value"] == wf_uuid
    by_uuid = {r["identifier"][0]["value"]: ref for ref, r in store.items() if r["resourceType"] == "ActivityDefinition"}
    assert [(a["title"], a["definition"]) for a in plan["action"]] == [
        (t["step_id"], {"reference": by_uuid[t["dataset_uuid"]]}) for t in body["tools"]]


@pytest.mark.integration
def test_fhir_descriptions_are_validated_before_anything_is_stored(client):
    bad = '{"workflow": {"action": [{"step": "to_nifti", "input": [{"id": "nope", "resource_type": "ImagingStudy"}]}]}}'
    r = _post(client, _folder_parts(script_files()), data={"fhir_descriptions": bad})

    assert r.status_code == 400 and "nope" in r.json()["detail"]
    _nothing_stored(client)
    assert client.seek.workflows == {}


@pytest.mark.integration
def test_fhir_descriptions_are_stored_and_pushed(client):
    descriptions = ('{"workflow": {"version": "1.0", "action": [{"step": "to_nifti", '
                    '"input": [{"id": "src", "resource_type": "ImagingStudy"}]}]}, '
                    '"workflow_tools": {"to_nrrd": {"version": "2.0"}}}')
    r = _post(client, _folder_parts(script_files()), data={"fhir_descriptions": descriptions})

    assert r.status_code == 200, r.text
    wf_uuid = r.json()["dataset_uuid"]
    stored = client.get(f"/datasets/{wf_uuid}/fhir/annotation").json()["descriptions"]["workflow"]
    assert stored["version"] == "1.0"
    assert stored["action"][0]["input"] == [{"display": "src", "resource_type": "ImagingStudy"}]
    nrrd = {t["step_id"]: t["dataset_uuid"] for t in r.json()["tools"]}["to_nrrd"]
    assert client.get(f"/datasets/{nrrd}/fhir/annotation").json()["descriptions"]["workflow_tool"]["version"] == "2.0"


@pytest.mark.integration
def test_failed_push_is_retried_as_a_whole(client):
    client.hapi.fail_push = True
    r = _post(client, _folder_parts(script_files()), fhir="auto")
    wf_uuid = r.json()["dataset_uuid"]
    assert _fhir_status(client, wf_uuid) == "failed"

    client.hapi.fail_push = False
    assert client.post(f"/datasets/{wf_uuid}/fhir/push").status_code == 202

    assert _fhir_status(client, wf_uuid) == "completed"
    assert client.hapi.types() == {"ActivityDefinition": 2, "PlanDefinition": 1}


@pytest.mark.integration
def test_tree_and_annotation_round_trip_and_repush_replaces_the_plan(client):
    r = _post(client, _folder_parts(script_files()), fhir="auto")
    wf_uuid = r.json()["dataset_uuid"]

    tree = client.get(f"/datasets/{wf_uuid}/fhir/tree").json()
    assert [s["step_id"] for s in tree["steps"]] == ["to_nifti", "to_nrrd"]
    assert tree["steps"][0]["ports"]["inputs"][0]["id"] == "src"
    descriptions = tree["descriptions"]
    descriptions["workflow"]["purpose"] = "Convert DICOM"
    descriptions["workflow_tools"]["to_nifti"]["version"] = "3.0"

    put = client.put(f"/datasets/{wf_uuid}/fhir/annotation", json={"descriptions": descriptions})
    assert put.status_code == 200, put.text
    assert client.post(f"/datasets/{wf_uuid}/fhir/push").status_code == 202

    assert client.hapi.types() == {"ActivityDefinition": 2, "PlanDefinition": 1}
    assert client.get(f"/datasets/{wf_uuid}/fhir/preview").json()["workflow"]["purpose"] == "Convert DICOM"
    nifti = {t["step_id"]: t["dataset_uuid"] for t in r.json()["tools"]}["to_nifti"]
    assert client.get(f"/datasets/{nifti}/fhir/annotation").json()["descriptions"]["workflow_tool"]["version"] == "3.0"


@pytest.mark.integration
def test_annotation_with_an_unknown_step_is_rejected(client):
    wf_uuid = _post(client, _folder_parts(script_files())).json()["dataset_uuid"]

    r = client.put(f"/datasets/{wf_uuid}/fhir/annotation",
                   json={"descriptions": {"workflow_tools": {"zzz": {}}}})

    assert r.status_code == 400 and "zzz" in r.json()["detail"]


# ── GET /datasets/{uuid}/workflow-tools ────────────────────────────────


@pytest.mark.integration
def test_workflow_tools_lists_each_tool_with_its_steps(client):
    body = _post(client, _folder_parts(script_files())).json()

    r = client.get(f"/datasets/{body['dataset_uuid']}/workflow-tools")

    assert r.status_code == 200, r.text
    assert r.json()["workflow_type"] == "script"
    assert r.json()["tools"] == [
        {"dataset_uuid": t["dataset_uuid"], "dataset_name": f"tool_{t['step_id']}", "seek_id": str(t["seek_id"]),
         "step_ids": [t["step_id"]]} for t in sorted(body["tools"], key=lambda t: t["step_id"])]


@pytest.mark.integration
def test_workflow_tools_of_a_non_workflow_is_empty(client):
    tool = _post(client, _folder_parts(script_files())).json()["tools"][0]

    r = client.get(f"/datasets/{tool['dataset_uuid']}/workflow-tools")

    assert r.status_code == 200 and r.json() == {"workflow_type": None, "tools": []}


@pytest.mark.integration
def test_workflow_tools_of_an_unknown_dataset_is_404(client):
    assert client.get("/datasets/00000000-0000-0000-0000-000000000000/workflow-tools").status_code == 404
