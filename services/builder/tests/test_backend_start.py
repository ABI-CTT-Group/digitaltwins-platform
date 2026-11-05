"""Launch starts a GUI tool's backend: POST/GET /api/builder/tools/backend/{expose_name}.

Run from `services/builder/`:
    python -m pytest tests/test_backend_start.py
"""
import unittest
import uuid

from tests.tool_app import bearer, make_hub_client  # noqa: I001  (sets DATABASE_PATH first)
from app.models.db_model import BuildStatus, DeployStatus, Plugin, PluginBuild, PluginDeployment, SessionLocal
from app.router import workflow_tool_plugin
from app.utils import workflow_tool_utils
from tests.test_workflow_gui_tools import add_build, add_workflow


class FakeDeployer:
    def __init__(self):
        self.running, self.up_ok, self.calls = set(), True, []

    def is_project_running(self, expose_name):
        return "running" if expose_name in self.running else "gone"

    def compose_up(self, plugin):
        self.calls.append(("up", plugin))
        if self.up_ok:
            self.running.add(plugin["expose_name"])
            return {"success": True, "message": "ok"}
        return {"success": False, "message": "compose up failed"}

    def generate_nginx_conf(self, **kwargs):
        self.calls.append(("nginx", kwargs["expose_name"]))

    def reload_nginx(self):
        return True


def add_deployment(build_id, expose, status=DeployStatus.COMPLETED.value, up=False, **fields):
    with SessionLocal() as db:
        row = PluginDeployment(workflow_build_id=build_id, deploy_id=str(uuid.uuid4()), status=status, up=up,
                               source_path=f"/portal_workspace/workflows/{expose}/code/backend",
                               route_prefix=f"/plugin/{expose}", internal_host=f"{expose}-app-1",
                               internal_port="8000", **fields)
        db.add(row)
        db.commit()
        return row.deploy_id


def deployment_rows():
    with SessionLocal() as db:
        return [(d.deploy_id, d.status, d.up, d.error) for d in db.query(PluginDeployment).all()]


class BackendStartTest(unittest.TestCase):
    def setUp(self):
        self.client = make_hub_client()
        self.deployer = FakeDeployer()
        self.deployed, self.spawned = [], []
        self._orig = (workflow_tool_plugin.deployer, workflow_tool_utils.run_deployment, workflow_tool_utils.spawn)
        workflow_tool_plugin.deployer = self.deployer
        workflow_tool_utils.run_deployment = lambda deployer, deploy_id, d: self.deployed.append((deploy_id, d))
        workflow_tool_utils.spawn = lambda fn, *args: self.spawned.append((fn, args))
        workflow_tool_utils.backend_jobs.clear()

    def tearDown(self):
        workflow_tool_plugin.deployer, workflow_tool_utils.run_deployment, workflow_tool_utils.spawn = self._orig
        workflow_tool_utils.backend_jobs.clear()

    def _start(self, expose, token="viewer"):
        return self.client.post(f"/api/builder/tools/backend/{expose}/start", headers=bearer(token))

    def _state(self, expose):
        r = self.client.get(f"/api/builder/tools/backend/{expose}", headers=bearer("viewer"))
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def _run_spawned(self):
        while self.spawned:
            fn, args = self.spawned.pop(0)
            fn(*args)

    def test_a_tool_without_a_backend_needs_nothing(self):
        _, expose = add_build(add_workflow())
        r = self._start(expose)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["state"], "none")
        self.assertEqual((self.spawned, self.deployed), ([], []))

    def test_an_unknown_tool_is_404(self):
        self.assertEqual(self._start("nope").status_code, 404)

    def test_a_token_is_needed(self):
        self.assertEqual(self._start("nope", token="expired").status_code, 401)

    def test_a_running_backend_is_left_alone(self):
        build_id, expose = add_build(add_workflow(has_backend=True))
        add_deployment(build_id, expose, up=True)
        self.deployer.running.add(expose)
        self.assertEqual(self._start(expose).json()["state"], "running")
        self.assertEqual((self.spawned, self.deployer.calls), ([], []))

    def test_a_stopped_deployment_is_started_by_any_user(self):
        build_id, expose = add_build(add_workflow(has_backend=True))
        add_deployment(build_id, expose)
        self.assertEqual(self._start(expose).json()["state"], "starting")
        self.assertEqual(self._state(expose)["state"], "starting")
        self._run_spawned()
        self.assertEqual(self.deployer.calls, [
            ("up", {"backend_dir": f"/portal_workspace/workflows/{expose}/code/backend", "expose_name": expose}),
            ("nginx", expose)])
        self.assertEqual(self._state(expose)["state"], "running")
        self.assertEqual(self.deployed, [])

    def test_a_marked_up_deployment_whose_containers_are_gone_is_started(self):
        build_id, expose = add_build(add_workflow(has_backend=True))
        add_deployment(build_id, expose, up=True)
        self.assertEqual(self._start(expose).json()["state"], "starting")

    def test_a_build_never_deployed_is_deployed(self):
        build_id, expose = add_build(add_workflow(has_backend=True))
        self.assertEqual(self._start(expose).json()["state"], "deploying")
        self._run_spawned()
        [(deploy_id, d)] = self.deployed
        self.assertEqual(d, {"expose_name": expose, "dataset_path": f"/portal_workspace/workflows/{expose}",
                             "backend_folder": "backend"})
        with SessionLocal() as db:
            row = db.query(PluginDeployment).one()
            self.assertEqual((row.deploy_id, row.workflow_build_id, row.build_id), (deploy_id, build_id, None))

    def test_a_failed_deployment_is_redeployed_in_its_own_row(self):
        build_id, expose = add_build(add_workflow(has_backend=True))
        deploy_id = add_deployment(build_id, expose, status=DeployStatus.FAILED.value, error="image build failed")
        self.assertEqual(self._state(expose), {"state": "failed", "error": "image build failed", "deploy_id": deploy_id})
        self.assertEqual(self._start(expose).json()["state"], "deploying")
        self._run_spawned()
        self.assertEqual(self.deployed[0][0], deploy_id)
        self.assertEqual(deployment_rows(), [(deploy_id, DeployStatus.PENDING.value, False, None)])

    def test_a_failed_start_is_reported_and_redeploys_next_time(self):
        build_id, expose = add_build(add_workflow(has_backend=True))
        add_deployment(build_id, expose)
        self.deployer.up_ok = False
        self._start(expose)
        self._run_spawned()
        state = self._state(expose)
        self.assertEqual((state["state"], state["error"]), ("failed", "compose up failed"))
        self.assertEqual(self._start(expose).json()["state"], "deploying")

    def test_a_second_launch_joins_the_start_under_way(self):
        build_id, expose = add_build(add_workflow(has_backend=True))
        add_deployment(build_id, expose)
        self._start(expose)
        self.assertEqual(self._start(expose).json()["state"], "starting")
        self.assertEqual(len(self.spawned), 1)

    def test_a_tool_backend_is_deployed_from_its_build(self):
        with SessionLocal() as db:
            plugin = Plugin(name="annotator", version="1", repository_url="local://a", source_type="local",
                            label="GUI", has_backend=True, frontend_folder="fe", frontend_build_command="npm run build",
                            backend_folder="be")
            db.add(plugin)
            db.flush()
            db.add(PluginBuild(plugin_id=plugin.id, build_id="pb1", status=BuildStatus.COMPLETED.value,
                               expose_name="annotator_1", dataset_path="/portal_workspace/tools/annotator_1"))
            db.commit()
            plugin_id = plugin.id
        self.assertEqual(self._start("annotator_1").json()["state"], "deploying")
        self._run_spawned()
        self.assertEqual(self.deployed[0][1], {"expose_name": "annotator_1",
                                               "dataset_path": "/portal_workspace/tools/annotator_1",
                                               "backend_folder": "be"})
        with SessionLocal() as db:
            row = db.query(PluginDeployment).one()
            self.assertEqual((row.plugin_id, row.build_id, row.workflow_build_id), (plugin_id, "pb1", None))


if __name__ == "__main__":
    unittest.main()
