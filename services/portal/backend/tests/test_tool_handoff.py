"""Approval hands the built tool to digitaltwins-api (chunked session) as the user, with token relay.

Run from `backend/`:
    python -m unittest tests.test_tool_handoff
"""
import json
import tempfile
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs

import httpx

from tests.tool_app import bearer, make_client  # noqa: I001  (sets DATABASE_PATH first)
from app.models.db_model import BuildStatus, Plugin, PluginAnnotation, PluginBuild, SessionLocal
from app.services import tool_handoff

CWL = "cwlVersion: v1.2\nclass: CommandLineTool\ninputs:\n  src: Directory\noutputs:\n  nifti: File\n"


class FakeApi:
    """digitaltwins-api's /datasets/uploads + /datasets surface, in memory.

    ``valid`` holds the tokens it accepts; ``expire_after`` invalidates every
    token once that many parts have been received (a 300 s token running out).
    """

    def __init__(self):
        self.valid = {"admin", "admin2", "researcher", "viewer"}
        self.expire_after = None
        self.fail_commit = None
        self.fail_delete = False
        self.sessions, self.puts, self.deleted, self.auth = {}, [], [], []
        self.delete_params = []
        self.datasets = {}
        self.workflow_tools = []          # what GET /datasets/{uuid}/workflow-tools lists
        self.fail_workflow_tools = False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        token = request.headers.get("authorization", "").removeprefix("Bearer ")
        self.auth.append(token)
        if token not in self.valid:
            return httpx.Response(401, json={"detail": "Invalid or expired token"})
        path, method = request.url.path, request.method
        if path == "/datasets/uploads/config":
            return httpx.Response(200, json={"max_part_size": 4})
        if path == "/datasets/uploads" and method == "POST":
            body = json.loads(request.content)
            upload_id = str(uuid.uuid4())
            self.sessions[upload_id] = {"body": body, "status": "receiving", "parts": set()}
            return httpx.Response(200, json={"upload_id": upload_id, "max_part_size": 4})
        parts = path.split("/")
        session = self.sessions.get(parts[3]) if path.startswith("/datasets/uploads/") else None
        if session is not None and "/parts/" in path:
            query = parse_qs(request.url.query.decode())
            rel = path.split("/parts/", 1)[1]
            session["parts"].add((rel, int(query["n"][0])))
            self.puts.append((rel, int(query["n"][0]), request.content))
            if self.expire_after is not None and len(self.puts) >= self.expire_after:
                self.valid.discard(token)
                self.expire_after = None
            return httpx.Response(200, json={})
        if session is not None and path.endswith("/finalize"):
            if self.fail_commit:
                session.update(status="failed", failure_message=self.fail_commit)
            else:
                dataset_uuid = str(uuid.uuid4())
                self.datasets[dataset_uuid] = {"dataset_uuid": dataset_uuid, "seek_id": "42"}
                session.update(status="completed", dataset_uuid=dataset_uuid)
            return httpx.Response(202, json={"status": "processing"})
        if session is not None and method == "GET":
            view = {k: session.get(k) for k in ("status", "dataset_uuid", "failure_message")}
            if session["status"] == "receiving":
                view["upload"] = {"files": [
                    {"rel_path": e["rel_path"], "parts": e["parts"],
                     "received_parts": sorted(n for r, n in session["parts"] if r == e["rel_path"])}
                    for e in session["body"]["manifest"]]}
            return httpx.Response(200, json=view)
        if session is not None and method == "DELETE":
            self.sessions.pop(parts[3])
            return httpx.Response(200, json={})
        if path == "/datasets" and method == "GET":
            categories = parse_qs(request.url.query.decode()).get("categories", [])
            return httpx.Response(200, json={"datasets": [
                d for d in self.datasets.values() if not categories or d.get("category", "tools") in categories]})
        if self.fail_delete and path.startswith("/datasets/") and method == "DELETE":
            return httpx.Response(500, json={"detail": "MinIO unreachable"})
        if path.startswith("/datasets/") and path.endswith("/fhir/annotation"):
            dataset = self.datasets.get(parts[2])
            if dataset is None or "annotation" not in dataset:
                return httpx.Response(404, json={"detail": "No FHIR annotation for this dataset"})
            return httpx.Response(200, json={"descriptions": dataset["annotation"]})
        if path.startswith("/datasets/") and path.endswith("/workflow-tools"):
            if self.fail_workflow_tools:
                return httpx.Response(500, json={"detail": "Postgres unreachable"})
            return httpx.Response(200, json={"workflow_type": "gui", "tools": self.workflow_tools})
        if path.startswith("/datasets/") and method == "GET":
            dataset = self.datasets.get(parts[2])
            return httpx.Response(200, json={"dataset": dataset}) if dataset else httpx.Response(404, json={})
        if path.startswith("/datasets/") and method == "DELETE":
            self.delete_params.append(dict(request.url.params))
            self.deleted.append(parts[2])
            return httpx.Response(200, json={}) if self.datasets.pop(parts[2], None) else httpx.Response(404, json={})
        return httpx.Response(404, json={"detail": f"no fake route {method} {path}"})


def _sparc_folder():
    root = Path(tempfile.mkdtemp()) / "convert_ab12cd34"
    (root / "primary").mkdir(parents=True)
    (root / "code").mkdir()
    (root / "primary" / "tool_convert.cwl").write_text(CWL)
    (root / "code" / "convert.py").write_text("print('hello')\n")  # 15 bytes: 4 parts of 4
    (root / "dataset_description.xlsx").write_bytes(b"xlsx")
    return root


class HandoffTest(unittest.TestCase):
    def setUp(self):
        self.client = make_client()
        self.api = FakeApi()
        tool_handoff.POLL_INTERVAL = 0
        tool_handoff.make_http = lambda: httpx.Client(base_url="http://api.test", transport=httpx.MockTransport(self.api))
        tool_handoff.relay.clear()
        with SessionLocal() as db:
            plugin = Plugin(name="Convert", version="1.2.0", repository_url="local://x", label="Script",
                            has_backend=False, frontend_folder="", frontend_build_command="")
            db.add(plugin)
            db.commit()
            self.plugin_id = plugin.id
        self.build_id = self._add_build()

    def _add_build(self, status=BuildStatus.COMPLETED.value, age=0):
        with SessionLocal() as db:
            build = PluginBuild(plugin_id=self.plugin_id, build_id=str(uuid.uuid4()), status=status,
                                dataset_path=str(_sparc_folder()), expose_name="convert_ab12cd34",
                                created_at=datetime.utcnow() - timedelta(minutes=age))
            db.add(build)
            db.commit()
            return build.build_id

    def _approve(self, token="researcher", **body):
        return self.client.post(f"/api/tools/plugin/{self.plugin_id}/approval",
                                json={"seek_project_id": 11, **body}, headers=bearer(token))

    def _status(self, token="researcher"):
        return self.client.get(f"/api/tools/plugin/{self.plugin_id}/approval/status", headers=bearer(token))

    def _rows(self, build_id=None):
        with SessionLocal() as db:
            build = db.query(PluginBuild).filter_by(build_id=build_id or self.build_id).one()
            plugin = db.get(Plugin, self.plugin_id)
            db.expunge_all()
            return plugin, build

    def test_approval_commits_the_build_in_the_platform_as_the_user(self):
        r = self._approve()

        self.assertEqual(r.status_code, 202, r.text)
        status = self._status().json()
        self.assertEqual(status["handoff_status"], "completed", status)
        plugin, build = self._rows()
        self.assertEqual((build.dataset_uuid, build.seek_id, plugin.uuid),
                         (status["dataset_uuid"], "42", status["dataset_uuid"]))
        self.assertEqual(plugin.seek_project_id, 11)
        [session] = [s["body"] for s in self.api.sessions.values()]
        self.assertEqual((session["category"], session["tool_type"], session["seek_project_id"],
                          session["commit_mode"], session["name"]), ("tools", "script", 11, "on_finalize", "Convert"))
        self.assertEqual({e["rel_path"] for e in session["manifest"]}, {
            "convert_ab12cd34/primary/tool_convert.cwl", "convert_ab12cd34/code/convert.py",
            "convert_ab12cd34/dataset_description.xlsx"})
        sent = b"".join(c for rel, n, c in sorted(self.api.puts) if rel.endswith("convert.py"))
        self.assertEqual(sent, b"print('hello')\n")
        self.assertEqual(set(self.api.auth), {"researcher"})

    def test_the_annotation_draft_becomes_the_tools_fhir_descriptions(self):
        draft = {"name": "Convert", "inputs": [{"name": "src", "resource": "ImagingStudy"}],
                 "outputs": [{"name": "nifti", "resource": "Observation", "code": "123", "system": "http://loinc.org",
                              "unit": ""}]}
        with SessionLocal() as db:
            db.add(PluginAnnotation(plugin_id=self.plugin_id, annotation_id="a1", fhir_note=json.dumps(draft)))
            db.commit()

        self._approve()

        [session] = [s["body"] for s in self.api.sessions.values()]
        self.assertEqual(session["fhir_descriptions"], {"workflow_tool": {
            "version": "1.2.0",
            "input": [{"id": "src", "resourceType": "ImagingStudy"}],
            "output": [{"id": "nifti", "resourceType": "Observation", "code": "123", "system": "http://loinc.org"}],
        }})

    def test_fhir_can_be_left_out(self):
        self._approve(fhir=False)

        [session] = [s["body"] for s in self.api.sessions.values()]
        self.assertNotIn("fhir_descriptions", session)

    def test_an_expired_token_pauses_and_a_fresh_one_resumes_without_resending(self):
        self.api.expire_after = 2

        self._approve()
        self.assertEqual(self._rows()[1].handoff_status, "awaiting_reauth")

        self.api.valid.add("researcher#2")
        self._status(token="researcher#2")  # the page's next poll brings a fresh token and resumes the job
        status = self._status(token="researcher#2").json()

        self.assertEqual(status["handoff_status"], "completed", status)
        self.assertEqual(len(self.api.puts), len({(rel, n) for rel, n, _ in self.api.puts}))
        self.assertEqual(status["parts_sent"], status["parts_total"])

    def test_only_the_approving_users_token_is_relayed(self):
        self.api.expire_after = 2
        self._approve(token="researcher")

        self._status(token="admin2")  # another uploader's poll must not continue the handoff as them
        self.assertEqual(self._rows()[1].handoff_status, "awaiting_reauth")
        self.assertNotIn("admin2", self.api.auth)

        self.api.valid.add("researcher#2")  # the approver's page brings a fresh token
        self._status(token="researcher#2")
        self.assertEqual(self._status(token="researcher#2").json()["handoff_status"], "completed")

    def test_a_failed_commit_is_recorded(self):
        self.api.fail_commit = "SEEK registration failed; nothing was stored: not a member"

        self._approve()

        plugin, build = self._rows()
        self.assertEqual(build.handoff_status, "failed")
        self.assertIn("not a member", build.handoff_error)
        self.assertIsNone(plugin.uuid)

    def test_a_failed_handoff_can_be_approved_again(self):
        self.api.fail_commit = "boom"
        self._approve()
        self.api.fail_commit = None

        self.assertEqual(self._approve().status_code, 202)
        self.assertEqual(self._rows()[1].handoff_status, "completed")
        self.assertEqual(len(self.api.sessions), 1)  # the failed session was cancelled

    def test_the_same_build_cannot_be_approved_twice(self):
        self._approve()
        self.assertEqual(self._approve().status_code, 409)

    def test_an_unfinished_build_cannot_be_approved(self):
        self._add_build(status=BuildStatus.BUILDING.value, age=-1)
        self.assertEqual(self._approve().status_code, 409)

    def test_a_seek_project_is_required(self):
        r = self.client.post(f"/api/tools/plugin/{self.plugin_id}/approval", json={}, headers=bearer("researcher"))
        self.assertEqual(r.status_code, 400)
        self.assertIn("seek_project_id", r.json()["detail"])

    def test_reapproval_replaces_the_previous_dataset_once_the_new_one_is_committed(self):
        self._approve()
        old = self._rows()[0].uuid
        new_build = self._add_build(age=-1)

        self.assertEqual(self._approve().status_code, 202)

        plugin, build = self._rows(new_build)
        self.assertEqual(plugin.uuid, build.dataset_uuid)
        self.assertNotEqual(plugin.uuid, old)
        self.assertEqual(self.api.deleted, [old])
        self.assertIsNone(self._rows()[1].dataset_uuid)

    def test_a_failed_reapproval_keeps_the_previous_dataset(self):
        self._approve()
        old = self._rows()[0].uuid
        self._add_build(age=-1)
        self.api.fail_commit = "boom"

        self._approve()

        self.assertEqual(self._rows()[0].uuid, old)
        self.assertEqual(self.api.deleted, [])

    def test_an_approved_tools_annotation_is_read_from_the_platform(self):
        self._approve()
        dataset_uuid = self._rows()[0].uuid
        self.api.datasets[dataset_uuid]["annotation"] = {"workflow_tool": {
            "uuid": dataset_uuid, "input": [{"id": "src", "resourceType": "ImagingStudy"}],
            "output": [{"id": "nifti", "resourceType": "Observation", "code": "1", "system": "s"}]}}

        r = self.client.get(f"/api/tools/plugin/{self.plugin_id}/annotation", headers=bearer("viewer"))

        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(json.loads(r.json()["fhir_note"]), {
            "name": "Convert",
            "inputs": [{"name": "src", "resource": "ImagingStudy"}],
            "outputs": [{"name": "nifti", "resource": "Observation", "code": "1", "system": "s", "unit": ""}],
        })


if __name__ == "__main__":
    unittest.main()
