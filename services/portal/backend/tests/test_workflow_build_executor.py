"""A successful workflow build records whether the source is an SDS package; a failed one leaves it alone.

Run from `backend/`:
    python -m unittest tests.test_workflow_build_executor
"""
import unittest
import uuid

from fastapi import BackgroundTasks

from tests.tool_app import make_workflow_client  # noqa: I001  (sets DATABASE_PATH first)
from app.models.db_model import BuildStatus, SessionLocal, Workflow, WorkflowBuild
from app.utils.builder_utils import execute_build_in_background


class FakeBuilder:
    def __init__(self, result):
        self.result = result

    def build(self, data):
        return self.result


class WorkflowBuildExecutorTest(unittest.TestCase):
    def setUp(self):
        make_workflow_client()  # fresh tables
        self.build_id = str(uuid.uuid4())
        with SessionLocal() as db:
            wf = Workflow(name="convert", version="1.0.0", repository_url="local://x", source_type="local",
                          workflow_type="script")
            db.add(wf)
            db.commit()
            self.wf_id = wf.id
            db.add(WorkflowBuild(workflow_id=wf.id, build_id=self.build_id, status=BuildStatus.PENDING.value))
            db.commit()

    def _run(self, result):
        tasks = BackgroundTasks()
        execute_build_in_background(self.build_id, {}, FakeBuilder(result), WorkflowBuild, tasks)
        for task in tasks.tasks:
            task.func(*task.args, **task.kwargs)
        with SessionLocal() as db:
            return db.get(Workflow, self.wf_id).is_sds

    def test_a_successful_build_records_the_layout(self):
        ok = {"success": True, "s3_path": None, "dataset_path": "/d", "expose_name": "convert_ab12", "is_sds": True}
        self.assertTrue(self._run(ok))

    def test_a_failed_build_leaves_it_alone(self):
        self.assertIsNone(self._run({"success": False, "error_message": "boom"}))

    def test_a_gui_build_records_its_tool_and_bundle(self):
        self._run({"success": True, "s3_path": None, "dataset_path": "/d", "expose_name": "convert_ab12",
                   "is_sds": True, "tool_name": "tool_convert", "bundle_path": "tool-builds/convert_ab12/primary"})
        with SessionLocal() as db:
            build = db.query(WorkflowBuild).filter(WorkflowBuild.build_id == self.build_id).one()
            self.assertEqual((build.tool_name, build.bundle_path),
                             ("tool_convert", "tool-builds/convert_ab12/primary"))


if __name__ == "__main__":
    unittest.main()
