"""A gui SDS workflow's tool in the Tool Hub: launcher metadata, the listing, its backend deploy.

Run from `backend/`:
    python -m unittest tests.test_workflow_gui_tools
"""
import unittest
import uuid
from datetime import datetime, timedelta

from tests.tool_app import bearer, make_hub_client  # noqa: I001  (sets DATABASE_PATH first)
from app.models.db_model import BuildStatus, PluginDeployment, SessionLocal, Workflow, WorkflowBuild
from app.router import workflow_router
from tests.test_tool_catalogue import FakeBucket


def add_workflow(workflow_type="gui", has_backend=False, **fields):
    with SessionLocal() as db:
        wf = Workflow(name="workflow_volview", version="1.0", repository_url="local://v", source_type="local",
                      workflow_type=workflow_type, is_sds=True, has_backend=has_backend,
                      backend_folder="backend" if has_backend else None, **fields)
        db.add(wf)
        db.commit()
        return wf.id


def add_build(wf_id, age_minutes=0, bundle=True, status=BuildStatus.COMPLETED.value, **fields):
    expose = f"workflowvolview_{uuid.uuid4().hex[:8]}"
    values = {"tool_name": "tool_volview" if bundle else None,
              "bundle_path": f"tool-builds/{expose}/primary" if bundle else None, **fields}
    with SessionLocal() as db:
        build = WorkflowBuild(workflow_id=wf_id, build_id=str(uuid.uuid4()), status=status, expose_name=expose,
                              dataset_path=f"/portal_workspace/workflows/{expose}",
                              created_at=datetime(2026, 10, 2, 12) - timedelta(minutes=age_minutes), **values)
        db.add(build)
        db.commit()
        return build.build_id, expose


def approve(wf_id, build_id, tool_uuid="tool-v"):
    with SessionLocal() as db:
        db.get(Workflow, wf_id).uuid = "wf-v"
        build = db.query(WorkflowBuild).filter(WorkflowBuild.build_id == build_id).one()
        build.dataset_uuid, build.tool_dataset_uuid = "wf-v", tool_uuid
        db.commit()


class LauncherMetadataTest(unittest.TestCase):
    def setUp(self):
        self.client = make_hub_client()

    def _components(self):
        r = self.client.get("/api/tools/metadata", headers=bearer("viewer"))
        self.assertEqual(r.status_code, 200, r.text)
        return [c for c in r.json()["components"] if c.get("kind") == "workflow"]

    def test_a_built_gui_workflow_loads_from_tool_builds(self):
        wf_id = add_workflow()
        _, expose = add_build(wf_id)
        [c] = self._components()
        self.assertEqual((c["id"], c["name"], c["expose"], c["label"]), (wf_id, "tool_volview", expose, "GUI"))
        self.assertTrue(c["path"].startswith(f"/tool-builds/{expose}/primary/my-app.umd.js?v="), c["path"])

    def test_an_approved_gui_workflow_loads_from_its_platform_tool_dataset(self):
        wf_id = add_workflow()
        build_id, _ = add_build(wf_id)
        approve(wf_id, build_id)
        [c] = self._components()
        self.assertEqual(c["uuid"], "tool-v")
        self.assertTrue(c["path"].startswith("/tools/tool-v/primary/my-app.umd.js?v="), c["path"])

    def test_the_approved_build_wins_over_a_newer_one(self):
        wf_id = add_workflow()
        build_id, approved_expose = add_build(wf_id, age_minutes=10)
        approve(wf_id, build_id)
        add_build(wf_id)
        [c] = self._components()
        self.assertEqual(c["expose"], approved_expose)

    def test_an_approved_build_without_its_tool_dataset_falls_back_to_tool_builds(self):
        wf_id = add_workflow()
        build_id, expose = add_build(wf_id)
        approve(wf_id, build_id, tool_uuid=None)
        [c] = self._components()
        self.assertTrue(c["path"].startswith(f"/tool-builds/{expose}/"), c["path"])

    def test_a_build_with_nowhere_to_load_from_is_skipped(self):
        wf_id = add_workflow()
        add_build(wf_id, bundle_path=None)
        self.assertEqual(self._components(), [])

    def test_builds_without_a_bundle_and_other_types_are_not_listed(self):
        add_build(add_workflow(), bundle=False)
        add_build(add_workflow(workflow_type="script"), bundle=False)
        self.assertEqual(self._components(), [])


class BuildLogsTest(unittest.TestCase):
    def test_a_workflow_build_log_is_served_after_it_left_memory(self):
        client = make_hub_client()
        build_id, _ = add_build(add_workflow(), build_logs="npm run build:plugin\nok")
        r = client.get(f"/api/tools/builds/{build_id}/logs", headers=bearer("viewer"))
        self.assertEqual((r.status_code, r.text), (200, "npm run build:plugin\nok"))


class GuiToolListingTest(unittest.TestCase):
    def setUp(self):
        self.client = make_hub_client()

    def _rows(self):
        r = self.client.get("/api/workflow/gui-tools", headers=bearer("viewer"))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def test_a_built_gui_workflow_is_a_tool_row(self):
        wf_id = add_workflow()
        build_id, _ = add_build(wf_id)
        [row] = self._rows()
        self.assertEqual({k: row[k] for k in ("id", "kind", "workflow_name", "name", "label", "status",
                                              "latest_build_id", "has_backend", "uuid")},
                         {"id": wf_id, "kind": "workflow", "workflow_name": "workflow_volview", "name": "tool_volview",
                          "label": "GUI", "status": "completed", "latest_build_id": build_id,
                          "has_backend": False, "uuid": None})

    def test_an_approved_row_carries_its_platform_tool_dataset(self):
        wf_id = add_workflow()
        build_id, _ = add_build(wf_id)
        approve(wf_id, build_id)
        self.assertEqual(self._rows()[0]["uuid"], "tool-v")

    def test_status_is_the_served_builds_while_logs_follow_the_latest(self):
        wf_id = add_workflow()
        served_id, _ = add_build(wf_id, age_minutes=10)
        approve(wf_id, served_id)
        newer_id, _ = add_build(wf_id, bundle=False, status=BuildStatus.FAILED.value)
        [row] = self._rows()
        self.assertEqual((row["status"], row["latest_build_id"], row["uuid"]), ("completed", newer_id, "tool-v"))

    def test_a_completed_build_with_nowhere_to_load_from_is_not_listed(self):
        add_build(add_workflow(), bundle_path=None)
        self.assertEqual(self._rows(), [])

    def test_a_building_workflow_is_listed_while_it_builds(self):
        add_build(add_workflow(), bundle=False, status=BuildStatus.BUILDING.value)
        self.assertEqual([r["status"] for r in self._rows()], ["building"])

    def test_workflows_never_built_or_built_without_a_bundle_are_not_listed(self):
        add_workflow()
        add_build(add_workflow(), bundle=False)
        add_build(add_workflow(workflow_type="script"))
        self.assertEqual(self._rows(), [])

    def test_a_row_shows_the_latest_deploy_of_the_served_build(self):
        wf_id = add_workflow(has_backend=True)
        build_id, _ = add_build(wf_id)
        with SessionLocal() as db:
            db.add(PluginDeployment(workflow_build_id=build_id, deploy_id="d1", status="completed", up=True))
            db.commit()
        [row] = self._rows()
        self.assertEqual((row["latest_deploy_id"], row["deploy_status"], row["has_backend"]), ("d1", "completed", True))


class WorkflowToolDeployTest(unittest.TestCase):
    def setUp(self):
        self.client = make_hub_client()
        self.deployed, self.shut_down = [], []
        self._orig = (workflow_router.run_deployment, workflow_router.shut_down_workflow_backends,
                      workflow_router.execute_build_in_background, workflow_router.minio,
                      workflow_router.get_minio_client)
        workflow_router.run_deployment = lambda deployer, deploy_id, d: self.deployed.append((deploy_id, d))
        workflow_router.shut_down_workflow_backends = lambda wf_id, deployer: self.shut_down.append(wf_id)
        workflow_router.execute_build_in_background = lambda **kwargs: None

    def tearDown(self):
        (workflow_router.run_deployment, workflow_router.shut_down_workflow_backends,
         workflow_router.execute_build_in_background, workflow_router.minio,
         workflow_router.get_minio_client) = self._orig

    def _deploy(self, wf_id, token="admin"):
        return self.client.get(f"/api/workflow/{wf_id}/deploy", headers=bearer(token))

    def test_only_admins_deploy(self):
        wf_id = add_workflow(has_backend=True)
        add_build(wf_id)
        self.assertEqual(self._deploy(wf_id, token="researcher").status_code, 403)

    def test_deploy_runs_the_served_build_backend(self):
        wf_id = add_workflow(has_backend=True)
        build_id, expose = add_build(wf_id)
        r = self._deploy(wf_id)
        self.assertEqual(r.status_code, 200, r.text)
        [(deploy_id, d)] = self.deployed
        self.assertEqual((r.json()["deploy_id"], r.json()["build_id"]), (deploy_id, build_id))
        self.assertEqual(d, {"expose_name": expose, "dataset_path": f"/portal_workspace/workflows/{expose}",
                             "backend_folder": "backend"})
        with SessionLocal() as db:
            row = db.query(PluginDeployment).filter(PluginDeployment.deploy_id == deploy_id).one()
            self.assertEqual((row.workflow_build_id, row.build_id, row.plugin_id), (build_id, None, None))

    def test_deploy_uses_the_approved_build(self):
        wf_id = add_workflow(has_backend=True)
        build_id, approved_expose = add_build(wf_id, age_minutes=10)
        approve(wf_id, build_id)
        add_build(wf_id)
        self._deploy(wf_id)
        self.assertEqual(self.deployed[0][1]["expose_name"], approved_expose)

    def test_a_workflow_without_a_backend_or_a_bundle_is_not_deployed(self):
        no_backend = add_workflow()
        add_build(no_backend)
        unbuilt = add_workflow(has_backend=True)
        self.assertEqual(self._deploy(no_backend).status_code, 400)
        self.assertEqual(self._deploy(unbuilt).status_code, 400)
        self.assertEqual(self.deployed, [])

    def test_a_rebuild_shuts_down_the_backend_first(self):
        with_backend, without = add_workflow(has_backend=True), add_workflow()
        for wf_id in (with_backend, without):
            r = self.client.post(f"/api/workflow/{wf_id}/build", json={}, headers=bearer("researcher"))
            self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.shut_down, [with_backend])

    def test_delete_shuts_down_the_backend_and_removes_the_bundle(self):
        wf_id = add_workflow(has_backend=True)
        build_id, expose = add_build(wf_id)
        with SessionLocal() as db:
            db.add(PluginDeployment(workflow_build_id=build_id, deploy_id="d1", status="completed"))
            db.commit()
        tool_builds = FakeBucket([f"{expose}/primary/my-app.umd.js", "other_ab12/primary/my-app.umd.js"])
        workflow_router.minio = FakeBucket()
        workflow_router.get_minio_client = lambda bucket=None: tool_builds

        r = self.client.delete(f"/api/workflow/{wf_id}", headers=bearer("researcher"))

        self.assertTrue(r.json()["status"], r.text)
        self.assertEqual(self.shut_down, [wf_id])
        self.assertEqual(tool_builds.deleted, [f"{expose}/primary/my-app.umd.js"])
        with SessionLocal() as db:
            self.assertEqual(db.query(PluginDeployment).count(), 0)


if __name__ == "__main__":
    unittest.main()
