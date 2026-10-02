"""Approval hands an SDS workflow build to digitaltwins-api as the user; delete removes it there.

Run from `backend/`:
    python -m unittest tests.test_workflow_handoff
"""
import json
import tempfile
import unittest
import uuid
from pathlib import Path

import httpx

from tests.tool_app import bearer, make_workflow_client  # noqa: I001  (sets DATABASE_PATH first)
from app.models.db_model import BuildStatus, SessionLocal, Workflow, WorkflowAnnotation, WorkflowBuild
from app.services import tool_handoff
from tests.test_tool_handoff import FakeApi
from tests.test_workflow_layout import make_sds_workflow

STEP = {"tool": "tool_convert.cwl", "inputs": [{"name": "src", "resource": "ImagingStudy"}],
        "outputs": [{"name": "nifti", "resource": "Observation", "code": "123", "system": "http://loinc.org",
                     "unit": ""}]}


class WorkflowHandoffTest(unittest.TestCase):
    def setUp(self):
        self.client = make_workflow_client()
        self.api = FakeApi()
        tool_handoff.POLL_INTERVAL = 0
        tool_handoff.make_http = lambda: httpx.Client(base_url="http://api.test",
                                                       transport=httpx.MockTransport(self.api))
        tool_handoff.relay.clear()
        with SessionLocal() as db:
            wf = Workflow(name="Convert", version="1.0.0", author="Ann", description="DICOM to NIfTI",
                          repository_url="local://x", source_type="local", workflow_type="script")
            db.add(wf)
            db.commit()
            self.wf_id = wf.id
        self.build_id = self._add_build()

    def _add_build(self):
        root = make_sds_workflow(Path(tempfile.mkdtemp()) / "convert_ab12cd34")
        with SessionLocal() as db:
            build = WorkflowBuild(workflow_id=self.wf_id, build_id=str(uuid.uuid4()),
                                  status=BuildStatus.COMPLETED.value, dataset_path=str(root))
            db.add(build)
            db.commit()
            return build.build_id

    def _annotate(self, steps):
        with SessionLocal() as db:
            db.add(WorkflowAnnotation(workflow_id=self.wf_id, annotation_id=str(uuid.uuid4()),
                                      fhir_note=json.dumps({"steps": steps}), sparc_note=""))
            db.commit()

    def _approve(self, token="researcher", **body):
        return self.client.post(f"/api/workflow/{self.wf_id}/approval",
                                json={"seek_project_id": 11, **body}, headers=bearer(token))

    def _status(self, token="researcher"):
        return self.client.get(f"/api/workflow/{self.wf_id}/approval/status", headers=bearer(token))

    def _workflow(self):
        with SessionLocal() as db:
            wf = db.get(Workflow, self.wf_id)
            db.expunge_all()
            return wf

    def test_approval_commits_the_package_as_a_workflow_dataset(self):
        r = self._approve()

        self.assertEqual(r.status_code, 202, r.text)
        status = self._status().json()
        self.assertEqual(status["handoff_status"], "completed", status)
        self.assertEqual((self._workflow().uuid, self._workflow().seek_project_id), (status["dataset_uuid"], 11))
        [session] = [s["body"] for s in self.api.sessions.values()]
        self.assertEqual((session["category"], session["workflow_type"], session["seek_project_id"],
                          session["commit_mode"], session["name"]), ("workflows", "script", 11, "on_finalize", "Convert"))
        self.assertIn("convert_ab12cd34/primary/workflow_convert.cwl", {e["rel_path"] for e in session["manifest"]})

    def test_the_step_annotations_become_workflow_and_tool_descriptions(self):
        self._annotate([{"step": "convert", **STEP}])

        self._approve()

        [session] = [s["body"] for s in self.api.sessions.values()]
        self.assertEqual(session["fhir_descriptions"], {
            "workflow": {"version": "1.0.0", "author": "Ann", "description": "DICOM to NIfTI", "action": [{
                "step": "convert",
                "input": [{"id": "src", "resource_type": "ImagingStudy"}],
                "output": [{"id": "nifti", "resource_type": "Observation", "code": "123",
                            "system": "http://loinc.org"}]}]},
            "workflow_tools": {"convert": {
                "version": "1.0.0",
                "input": [{"id": "src", "resourceType": "ImagingStudy"}],
                "output": [{"id": "nifti", "resourceType": "Observation", "code": "123",
                            "system": "http://loinc.org"}]}},
        })

    def test_steps_sharing_a_tool_annotate_it_once(self):
        self._annotate([{"step": "a", **STEP}, {"step": "b", **STEP, "inputs": []}])

        self._approve()

        [session] = [s["body"] for s in self.api.sessions.values()]
        self.assertEqual(list(session["fhir_descriptions"]["workflow_tools"]), ["a"])
        self.assertEqual([a["step"] for a in session["fhir_descriptions"]["workflow"]["action"]], ["a", "b"])

    def test_fhir_can_be_left_out(self):
        self._approve(fhir=False)
        [session] = [s["body"] for s in self.api.sessions.values()]
        self.assertNotIn("fhir_descriptions", session)

    def test_an_expired_token_pauses_and_a_fresh_one_resumes(self):
        self.api.expire_after = 2
        self._approve()
        self.assertEqual(self._status().json()["handoff_status"], "awaiting_reauth")

        self.api.valid.add("researcher#2")
        self._status(token="researcher#2")  # relays the fresh token and resumes
        self.assertEqual(self._status(token="researcher#2").json()["handoff_status"], "completed")

    def test_reapproval_replaces_the_previous_dataset_and_its_tools(self):
        self._approve()
        first = self._workflow().uuid
        self.build_id = self._add_build()

        self._approve()

        self.assertNotEqual(self._workflow().uuid, first)
        self.assertEqual(self.api.deleted, [first])
        self.assertEqual(self.api.delete_params, [{"delete_tools": "true"}])

    def test_a_root_cwl_workflow_is_not_approved_to_the_platform(self):
        with SessionLocal() as db:
            db.get(Workflow, self.wf_id).workflow_type = None
            db.commit()
        self.assertEqual(self._approve().status_code, 409)

    def test_the_legacy_approval_refuses_sds_workflows(self):
        r = self.client.get(f"/api/workflow/{self.wf_id}/approval", headers=bearer("researcher"))
        self.assertEqual(r.status_code, 409)

    def test_a_viewer_cannot_approve(self):
        self.assertEqual(self._approve(token="viewer").status_code, 403)

    def test_deleting_an_approved_workflow_deletes_its_dataset_and_tools(self):
        self._approve()
        uuid_ = self._workflow().uuid

        r = self.client.delete(f"/api/workflow/{self.wf_id}", headers=bearer("researcher"))

        self.assertTrue(r.json()["status"], r.json())
        self.assertEqual((self.api.deleted, self.api.delete_params), ([uuid_], [{"delete_tools": "true"}]))
        self.assertIsNone(self._workflow())

    def test_a_failed_platform_delete_keeps_the_workflow(self):
        self._approve()
        self.api.fail_delete = True

        r = self.client.delete(f"/api/workflow/{self.wf_id}", headers=bearer("researcher"))

        self.assertFalse(r.json()["status"])
        self.assertIsNotNone(self._workflow())

    def test_a_token_the_platform_rejects_says_to_sign_in_again(self):
        self._approve()

        r = self.client.delete(f"/api/workflow/{self.wf_id}", headers=bearer("researcher#2"))

        self.assertFalse(r.json()["status"])
        self.assertIn("sign in again", r.json()["message"])
        self.assertIsNotNone(self._workflow())


if __name__ == "__main__":
    unittest.main()
