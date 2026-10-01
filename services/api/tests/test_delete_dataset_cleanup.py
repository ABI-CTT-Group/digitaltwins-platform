"""DELETE /datasets/{uuid} removes every trace: Postgres rows (incl. subject/sample), MinIO, HAPI, caches."""
import shutil
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app
from app.routers import auth
from digitaltwins.measurements import jobs, sessions
from digitaltwins.measurements.staging import dataset_dir, staging_root
from test_datasets_workflows_api import tool_bucket  # noqa: F401  (fixture)

FIXTURE = Path(__file__).parent / "data" / "example_sds_dataset"
UPLOADER = {"username": "alice", "token": "t", "claims": {"realm_access": {"roles": ["admin"]}}}
VIEWER = {"username": "bob", "token": "t", "claims": {"realm_access": {"roles": []}}}


@pytest.fixture
def env(platform_db, minio_bucket, hapi, tmp_path, monkeypatch):
    monkeypatch.setenv("DATASET_STAGING_DIR", str(tmp_path / "staging"))
    app = create_app()
    app.dependency_overrides[auth.validate_credentials] = lambda: UPLOADER
    return {"db": platform_db, "bucket": minio_bucket, "hapi": hapi, "client": TestClient(app)}


def _committed(env, fhir_mode):
    conn = env["db"]()
    upload_id = sessions.create_session(conn, category=env["bucket"], name="example", description=None,
                                        source_kind="folder", commit_mode="on_finalize", fhir_mode=fhir_mode)
    shutil.copytree(FIXTURE, dataset_dir(upload_id))
    sessions.update_session(conn, upload_id, status="processing")
    jobs.run_commit_job(upload_id)
    return upload_id, sessions.get_session(conn, upload_id)["dataset_uuid"]


def _count(env, table):
    conn = env["db"]()
    with conn.cursor() as cur:
        cur.execute(f"SELECT count(*) FROM {table}")
        return cur.fetchone()[0]


def _objects(s3, bucket, prefix):
    return s3.list_objects_v2(Bucket=bucket, Prefix=prefix).get("KeyCount", 0)


@pytest.mark.integration
def test_delete_removes_all_rows_objects_fhir_and_caches(env, s3):
    upload_id, dataset_uuid = _committed(env, fhir_mode="auto")
    jobs.run_fhir_push_job(dataset_uuid)
    downloaded = staging_root() / "downloads" / dataset_uuid
    downloaded.mkdir(parents=True)
    assert _objects(s3, env["bucket"], f"{dataset_uuid}/") > 0

    r = env["client"].delete(f"/datasets/{dataset_uuid}")

    assert r.status_code == 200, r.text
    assert r.json()["fhir_resources_deleted"] == {"Composition": 2, "Consent": 2, "Endpoint": 8, "ImagingStudy": 4, "Patient": 2, "ResearchSubject": 2}
    assert env["hapi"].store == {}
    for table in ("dataset", "dataset_mapping", "subject", "sample", "dataset_description",
                  "manifest", "dataset_fhir_annotation", "upload_session"):
        assert _count(env, table) == 0, table
    assert _objects(s3, env["bucket"], f"{dataset_uuid}/") == 0
    assert not dataset_dir(upload_id).exists() and not downloaded.exists()


@pytest.mark.integration
def test_delete_keeps_subjects_and_samples_of_other_datasets(env):
    _, first = _committed(env, fhir_mode="none")
    _, second = _committed(env, fhir_mode="none")

    assert env["client"].delete(f"/datasets/{first}").status_code == 200

    assert _count(env, "subject") == 2 and _count(env, "sample") == 4  # the second dataset's rows


@pytest.mark.integration
def test_delete_of_a_dataset_without_fhir_does_not_call_hapi(env):
    _, dataset_uuid = _committed(env, fhir_mode="none")

    r = env["client"].delete(f"/datasets/{dataset_uuid}")

    assert r.status_code == 200 and r.json()["fhir_resources_deleted"] == {}
    assert env["hapi"].calls == []


@pytest.mark.integration
def test_delete_requires_an_upload_role(env):
    _, dataset_uuid = _committed(env, fhir_mode="none")
    env["client"].app.dependency_overrides[auth.validate_credentials] = lambda: VIEWER

    assert env["client"].delete(f"/datasets/{dataset_uuid}").status_code == 403
    assert _count(env, "dataset") == 1


@pytest.mark.integration
def test_delete_of_an_unknown_dataset_is_404(env):
    assert env["client"].delete("/datasets/00000000-0000-0000-0000-000000000000").status_code == 404


# ── Tool datasets: their SEEK workflow goes too ─────────────────────────


@pytest.fixture
def tool_env(env, seek, tmp_path, monkeypatch):
    from digitaltwins import tools

    monkeypatch.setattr(tools, "CATEGORY", env["bucket"])
    return {**env, "seek": seek, "tmp": tmp_path}


def _committed_tool(env):
    from digitaltwins.tools.pipeline import commit_tool

    root = env["tmp"] / "sds_tool_convert"
    (root / "primary").mkdir(parents=True)
    (root / "code").mkdir()
    (root / "primary" / "tool_convert.cwl").write_text("cwlVersion: v1.2\nclass: CommandLineTool\n")
    (root / "code" / "tool_convert.py").write_text("print('hi')\n")
    shutil.copy(FIXTURE / "dataset_description.xlsx", root)
    return commit_tool(root, "script", 11, "t")


@pytest.mark.integration
def test_delete_of_a_tool_also_deletes_its_seek_workflow(tool_env, s3):
    tool = _committed_tool(tool_env)

    r = tool_env["client"].delete(f"/datasets/{tool['dataset_uuid']}")

    assert r.status_code == 200, r.text
    assert r.json()["seek_workflow_deleted"] is True
    assert tool_env["seek"].deleted == [tool["seek_id"]]
    assert _count(tool_env, "dataset") == 0
    assert _objects(s3, tool_env["bucket"], f"{tool['dataset_uuid']}/") == 0


@pytest.mark.integration
def test_seek_failure_does_not_fail_the_tool_delete(tool_env):
    tool = _committed_tool(tool_env)
    tool_env["seek"].fail_delete = True

    r = tool_env["client"].delete(f"/datasets/{tool['dataset_uuid']}")

    assert r.status_code == 200, r.text
    assert r.json()["seek_workflow_deleted"] is False
    assert _count(tool_env, "dataset") == 0


@pytest.mark.integration
def test_delete_of_a_non_tool_dataset_does_not_call_seek(env, seek):
    _, dataset_uuid = _committed(env, fhir_mode="none")

    r = env["client"].delete(f"/datasets/{dataset_uuid}")

    assert r.status_code == 200 and r.json()["seek_workflow_deleted"] is False
    assert seek.deleted == []


# ── Workflow datasets: confirm whether their tools go too ─────────────────


@pytest.fixture
def workflow_env(env, seek, tool_bucket, tmp_path, monkeypatch):
    from digitaltwins import tools, workflows

    monkeypatch.setattr(workflows, "CATEGORY", env["bucket"])
    monkeypatch.setattr(tools, "CATEGORY", tool_bucket)
    return {**env, "seek": seek, "tmp": tmp_path, "tool_bucket": tool_bucket}


def _committed_workflow(env):
    """A script workflow with two tools, committed and pushed to (fake) FHIR."""
    from digitaltwins.workflows.pipeline import annotate_workflow, commit_workflow
    from test_datasets_workflows_api import script_files

    root = env["tmp"] / "wf_convert"
    for rel, data in script_files().items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    result = commit_workflow(root, "script", 11, "t")
    conn = env["db"]()
    annotate_workflow(conn, root, "script", result["dataset_uuid"])
    jobs.set_fhir_status(conn, result["dataset_uuid"], "pending")
    jobs.run_fhir_push_job(result["dataset_uuid"])
    assert env["hapi"].types() == {"ActivityDefinition": 2, "PlanDefinition": 1}
    return result


@pytest.mark.integration
def test_workflow_delete_needs_delete_tools_and_lists_the_tools(workflow_env):
    wf = _committed_workflow(workflow_env)

    r = workflow_env["client"].delete(f"/datasets/{wf['dataset_uuid']}")

    assert r.status_code == 409, r.text
    detail = r.json()["detail"]
    assert "delete_tools" in detail["message"]
    assert sorted((t["dataset_uuid"], t["dataset_name"], t["step_ids"]) for t in detail["tools"]) == sorted(
        (t["dataset_uuid"], f"tool_{t['step_id']}", [t["step_id"]]) for t in wf["tools"])
    assert _count(workflow_env, "dataset") == 3
    assert workflow_env["seek"].deleted == []


@pytest.mark.integration
def test_workflow_delete_keeping_its_tools(workflow_env, s3):
    wf = _committed_workflow(workflow_env)

    r = workflow_env["client"].delete(f"/datasets/{wf['dataset_uuid']}", params={"delete_tools": "false"})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["seek_workflow_deleted"] is True and body["tools_deleted"] == []
    assert body["fhir_resources_deleted"] == {"PlanDefinition": 1}
    assert workflow_env["seek"].deleted == [wf["seek_id"]]
    assert _count(workflow_env, "dataset") == 2 and _count(workflow_env, "workflow_tool") == 0
    assert _objects(s3, workflow_env["bucket"], f"{wf['dataset_uuid']}/") == 0
    assert workflow_env["hapi"].types() == {"ActivityDefinition": 2}
    # The kept tools are now standalone and can be deleted on their own.
    tool = wf["tools"][0]["dataset_uuid"]
    assert workflow_env["client"].delete(f"/datasets/{tool}").status_code == 200


@pytest.mark.integration
def test_workflow_delete_with_its_tools(workflow_env, s3):
    wf = _committed_workflow(workflow_env)

    r = workflow_env["client"].delete(f"/datasets/{wf['dataset_uuid']}", params={"delete_tools": "true"})

    assert r.status_code == 200, r.text
    assert sorted(r.json()["tools_deleted"]) == sorted(t["dataset_uuid"] for t in wf["tools"])
    assert _count(workflow_env, "dataset") == 0
    assert sorted(workflow_env["seek"].deleted) == sorted([wf["seek_id"], *(t["seek_id"] for t in wf["tools"])])
    assert workflow_env["hapi"].types() == {}
    for tool in wf["tools"]:
        assert _objects(s3, workflow_env["tool_bucket"], f"{tool['dataset_uuid']}/") == 0


@pytest.mark.integration
def test_a_tool_used_by_a_workflow_cannot_be_deleted_on_its_own(workflow_env):
    wf = _committed_workflow(workflow_env)
    tool = wf["tools"][0]["dataset_uuid"]

    r = workflow_env["client"].delete(f"/datasets/{tool}")

    assert r.status_code == 409, r.text
    assert [w["dataset_uuid"] for w in r.json()["detail"]["workflows"]] == [wf["dataset_uuid"]]
    assert _count(workflow_env, "dataset") == 3 and workflow_env["seek"].deleted == []


@pytest.mark.integration
def test_a_workflows_category_dataset_without_a_workflow_type_deletes_as_before(workflow_env):
    # e.g. an assay workspace output, which shares the category and is stored with the plain Uploader.
    from digitaltwins.core.uploader import Uploader

    dataset_uuid = Uploader().upload_dataset(str(FIXTURE), category=workflow_env["bucket"])

    r = workflow_env["client"].delete(f"/datasets/{dataset_uuid}")

    assert r.status_code == 200, r.text
    assert r.json()["seek_workflow_deleted"] is False and r.json()["tools_deleted"] == []
    assert workflow_env["seek"].deleted == []
