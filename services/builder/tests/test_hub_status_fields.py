"""Fields the catalogue cards' status line reads: whether a tool or workflow has a FHIR annotation, and why its
build or backend failed (docs/decisions/2026-11-06-card-status-sentence.md).

Run from `services/builder/`:
    python -m pytest tests/test_hub_status_fields.py
"""
import unittest
import uuid

from tests.tool_app import bearer, make_hub_client  # noqa: I001  (sets DATABASE_PATH first)
from app.models.db_model import (BuildStatus, Plugin, PluginAnnotation, PluginBuild, PluginDeployment, SessionLocal,
                                 WorkflowAnnotation)
from tests.test_workflow_gui_tools import add_build, add_workflow


def add_plugin():
    with SessionLocal() as db:
        plugin = Plugin(name="tool_volview", version="1.0", repository_url="local://v", source_type="local",
                        label="GUI", has_backend=True, frontend_folder="frontend", frontend_build_command="npm run build")
        db.add(plugin)
        db.commit()
        return plugin.id


class HasAnnotationTest(unittest.TestCase):
    def setUp(self):
        self.client = make_hub_client()

    def _row(self, url):
        r = self.client.get(url, headers=bearer("viewer"))
        self.assertEqual(r.status_code, 200, r.text)
        [row] = r.json()
        return row

    def test_a_tool_row_says_whether_it_has_an_annotation(self):
        plugin_id = add_plugin()
        self.assertIs(self._row("/api/builder/tools/")["has_annotation"], False)
        with SessionLocal() as db:
            db.add(PluginAnnotation(plugin_id=plugin_id, annotation_id=str(uuid.uuid4()), fhir_note="{}", sparc_note="{}"))
            db.commit()
        self.assertIs(self._row("/api/builder/tools/")["has_annotation"], True)

    def test_a_workflow_row_says_whether_it_has_an_annotation(self):
        wf_id = add_workflow()
        self.assertIs(self._row("/api/builder/workflow/")["has_annotation"], False)
        with SessionLocal() as db:
            db.add(WorkflowAnnotation(workflow_id=wf_id, annotation_id=str(uuid.uuid4()), fhir_note="{}", sparc_note="{}"))
            db.commit()
        self.assertIs(self._row("/api/builder/workflow/")["has_annotation"], True)


class FailureReasonTest(unittest.TestCase):
    def setUp(self):
        self.client = make_hub_client()

    def test_a_tool_deploy_carries_why_it_failed(self):
        plugin_id = add_plugin()
        with SessionLocal() as db:
            db.add(PluginBuild(plugin_id=plugin_id, build_id="b1", status=BuildStatus.COMPLETED.value))
            db.add(PluginDeployment(plugin_id=plugin_id, build_id="b1", deploy_id="d1", status="failed",
                                    error="port 8000 is already allocated"))
            db.commit()
        r = self.client.get("/api/builder/tools/plugin/build/b1/deploys", headers=bearer("viewer"))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()[0]["error"], "port 8000 is already allocated")

    def test_a_gui_workflow_tool_row_carries_its_build_and_deploy_errors(self):
        wf_id = add_workflow(has_backend=True)
        served_id, _ = add_build(wf_id, age_minutes=10)
        add_build(wf_id, bundle=False, status=BuildStatus.FAILED.value, error_messages="npm ERR! missing script")
        with SessionLocal() as db:
            db.add(PluginDeployment(workflow_build_id=served_id, deploy_id="d1", status="failed", error="no such image"))
            db.commit()
        r = self.client.get("/api/builder/workflow/gui-tools", headers=bearer("viewer"))
        [row] = r.json()
        self.assertEqual((row["build_error"], row["deploy_error"]), ("npm ERR! missing script", "no such image"))

    def test_a_healthy_gui_workflow_tool_row_has_no_errors(self):
        add_build(add_workflow())
        [row] = self.client.get("/api/builder/workflow/gui-tools", headers=bearer("viewer")).json()
        self.assertEqual((row["build_error"], row["deploy_error"]), (None, None))


if __name__ == "__main__":
    unittest.main()
