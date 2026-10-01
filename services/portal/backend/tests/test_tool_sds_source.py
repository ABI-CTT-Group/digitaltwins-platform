"""The wizard sees an SDS package's code/ folders and its primary/tool_*.cwl; workflows don't.

Run from `backend/`:
    python -m unittest tests.test_tool_sds_source
"""
import io
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path

from tests.tool_app import bearer, make_client  # noqa: I001  (sets DATABASE_PATH first)
from app.builder.source_acquirer import _inspect_with_cwl_content
from app.builder.tool_layout import inspect_tool_source, read_tool_cwl
from app.models.db_model import Plugin, SessionLocal
from app.utils.builder_utils import inspect_uploaded_source

CWL = "cwlVersion: v1.2\nclass: CommandLineTool\ninputs: []\noutputs: []\n"


def make_sds(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "dataset_description.xlsx").write_bytes(b"xlsx")
    (root / "primary").mkdir()
    (root / "primary" / "tool_viewer.cwl").write_text(CWL)
    for layer in ("frontend", "backend"):
        (root / "code" / layer).mkdir(parents=True)
        (root / "code" / layer / "README.md").write_text(layer)
    (root / "code" / "frontend" / "package.json").write_text('{"version": "2.3.4"}')
    return root


class InspectToolSourceTest(unittest.TestCase):
    def setUp(self):
        self.root = make_sds(Path(tempfile.mkdtemp()))

    def test_an_sds_reports_its_code_folders_and_its_cwl(self):
        meta = inspect_tool_source(self.root, want_cwl=False)
        self.assertTrue(meta["is_sds"])
        self.assertTrue(meta["has_cwl"])
        self.assertEqual(sorted(meta["folders_in_root"]), ["backend", "frontend"])
        self.assertEqual(meta["package_version"], "2.3.4")

    def test_an_sds_without_a_tool_cwl_has_no_cwl(self):
        (self.root / "primary" / "tool_viewer.cwl").unlink()
        meta = inspect_tool_source(self.root, want_cwl=False)
        self.assertTrue(meta["is_sds"])
        self.assertFalse(meta["has_cwl"])

    def test_a_source_tree_is_reported_as_before(self):
        src = Path(tempfile.mkdtemp())
        (src / "viewer.cwl").write_text(CWL)
        (src / "frontend").mkdir()
        meta = inspect_tool_source(src, want_cwl=False)
        self.assertFalse(meta["is_sds"])
        self.assertEqual(meta, {**inspect_uploaded_source(src, want_npm=True, want_cwl=False), "is_sds": False})

    def test_workflow_inspection_ignores_sds_packages(self):
        self.assertFalse(inspect_uploaded_source(self.root, want_npm=False, want_cwl=True)["has_cwl"])

    def test_the_sds_cwl_is_read_from_primary(self):
        self.assertEqual(read_tool_cwl(self.root), {"cwl_file": "tool_viewer.cwl", "content": CWL})

    def test_a_tool_probe_inlines_the_sds_cwl(self):
        meta = _inspect_with_cwl_content(self.root, tool_layout=True)
        self.assertTrue(meta["is_sds"])
        self.assertEqual(meta["cwl_file"], "tool_viewer.cwl")
        self.assertEqual(meta["cwl_content"], CWL)

    def test_a_workflow_probe_keeps_the_root_rule(self):
        self.assertNotIn("cwl_content", _inspect_with_cwl_content(self.root))


class ToolSourceEndpointsTest(unittest.TestCase):
    def setUp(self):
        self.client = make_client()
        self.root = make_sds(Path(tempfile.mkdtemp()) / "tool_viewer")

    def test_upload_source_detects_an_sds_zip(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            for p in self.root.rglob("*"):
                z.write(p, p.relative_to(self.root.parent).as_posix())
        r = self.client.post("/api/tools/upload-source", headers=bearer("researcher"),
                             files={"file": ("source.zip", buf.getvalue(), "application/zip")})
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.addCleanup(shutil.rmtree, Path("tmp") / body["upload_id"], True)
        self.assertTrue(body["is_sds"])
        self.assertTrue(body["has_cwl"])
        self.assertEqual(sorted(body["folders_in_root"]), ["backend", "frontend"])

    def test_the_cwl_endpoint_serves_the_sds_cwl(self):
        with SessionLocal() as db:
            plugin = Plugin(name="Viewer", version="1.0.0", repository_url="local://x", label="GUI",
                            has_backend=True, frontend_folder="frontend", frontend_build_command="npm run build",
                            source_type="local", local_archive_path=str(self.root))
            db.add(plugin)
            db.commit()
            plugin_id = plugin.id
        r = self.client.get(f"/api/tools/plugin/{plugin_id}/cwl", headers=bearer("viewer"))
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json(), {"cwl_file": "tool_viewer.cwl", "content": CWL})


if __name__ == "__main__":
    unittest.main()
