"""The workflow wizard accepts an SDS workflow package and reads its workflow and tool CWLs.

Run from `backend/`:
    python -m unittest tests.test_workflow_sds_source
"""
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests.tool_app import bearer, make_workflow_client  # noqa: I001  (sets DATABASE_PATH first)
from app.builder.source_acquirer import _inspect_with_cwl_content
from app.models.db_model import SessionLocal, Workflow
from tests.test_workflow_layout import TOOL, WORKFLOW, make_sds_workflow


def _zip(root: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for p in root.rglob("*"):
            if p.is_file():
                zf.write(p, f"{root.name}/{p.relative_to(root).as_posix()}")  # with a wrapper folder
    return buf.getvalue()


class WorkflowSdsSourceTest(unittest.TestCase):
    def setUp(self):
        self.client = make_workflow_client()
        self.root = make_sds_workflow(Path(tempfile.mkdtemp()) / "workflow_convert")

    def test_upload_source_accepts_an_sds_workflow_zip(self):
        r = self.client.post("/api/workflow/upload-source", headers=bearer("researcher"),
                             files={"file": ("w.zip", _zip(self.root), "application/zip")})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertTrue(r.json()["has_cwl"])
        self.assertTrue(r.json()["is_sds"])

    def test_upload_source_rejects_an_sds_package_without_a_workflow_cwl(self):
        (self.root / "primary" / "workflow_convert.cwl").unlink()
        r = self.client.post("/api/workflow/upload-source", headers=bearer("researcher"),
                             files={"file": ("w.zip", _zip(self.root), "application/zip")})
        self.assertEqual(r.status_code, 400)
        self.assertIn("primary/workflow_*.cwl", r.json()["detail"])

    def test_cwl_returns_the_workflow_and_its_tool_cwls(self):
        with SessionLocal() as db:
            wf = Workflow(name="convert", version="1.0.0", repository_url="local://x", source_type="local",
                          local_archive_path=str(self.root), workflow_type="script")
            db.add(wf)
            db.commit()
            wf_id = wf.id
        r = self.client.get(f"/api/workflow/{wf_id}/cwl", headers=bearer("viewer"))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["cwl_file"], "workflow_convert.cwl")
        self.assertEqual(r.json()["tool_cwls"], [{"cwl_file": "tool_convert.cwl", "content": TOOL}])
        self.assertTrue(r.json()["is_sds"])

    def test_cwl_reports_a_root_cwl_source_as_not_sds(self):
        src = Path(tempfile.mkdtemp())
        (src / "flow.cwl").write_text(WORKFLOW)
        with SessionLocal() as db:
            wf = Workflow(name="flow", version="1.0.0", repository_url="local://y", source_type="local",
                          local_archive_path=str(src), workflow_type="script")
            db.add(wf)
            db.commit()
            wf_id = wf.id
        r = self.client.get(f"/api/workflow/{wf_id}/cwl", headers=bearer("viewer"))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertFalse(r.json()["is_sds"])

    def test_a_git_probe_inlines_the_tool_cwls(self):
        data = _inspect_with_cwl_content(self.root, workflow_layout=True)
        self.assertTrue(data["is_sds"])
        self.assertEqual((data["cwl_file"], data["cwl_content"]), ("workflow_convert.cwl", WORKFLOW))
        self.assertEqual(data["tool_cwls"], [{"cwl_file": "tool_convert.cwl", "content": TOOL}])

    def test_a_root_cwl_probe_is_unchanged(self):
        src = Path(tempfile.mkdtemp())
        (src / "flow.cwl").write_text(WORKFLOW)
        data = _inspect_with_cwl_content(src, workflow_layout=True)
        self.assertFalse(data["is_sds"])
        self.assertNotIn("tool_cwls", data)

    def test_a_root_cwl_git_probe_reports_the_package_version_and_author(self):
        src = Path(tempfile.mkdtemp())
        (src / "flow.cwl").write_text(WORKFLOW)
        (src / "package.json").write_text('{"version": "2.3.4", "author": "Ann"}')
        data = _inspect_with_cwl_content(src, workflow_layout=True)
        self.assertEqual((data["package_version"], data["package_author"]), ("2.3.4", "Ann"))


if __name__ == "__main__":
    unittest.main()
