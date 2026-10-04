"""An SDS workflow package: dataset_description.xlsx, one primary/workflow_*.cwl and its tool CWLs.

Run from `backend/`:
    python -m unittest tests.test_workflow_layout
"""
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.builder.workflow_layout import (  # noqa: E402
    detect_workflow_layout, inspect_workflow_source, read_workflow_cwl,
)

WORKFLOW = ("cwlVersion: v1.2\nclass: Workflow\ninputs: {src: Directory}\noutputs: {}\n"
            "steps:\n  convert:\n    run: tool_convert.cwl\n    in: {src: src}\n    out: [nifti]\n")
TOOL = "cwlVersion: v1.2\nclass: CommandLineTool\ninputs: {src: Directory}\noutputs: {nifti: File}\n"


def make_sds_workflow(root: Path) -> Path:
    (root / "primary").mkdir(parents=True)
    (root / "code").mkdir()
    (root / "dataset_description.xlsx").write_bytes(b"xlsx")
    (root / "primary" / "workflow_convert.cwl").write_text(WORKFLOW)
    (root / "primary" / "tool_convert.cwl").write_text(TOOL)
    (root / "code" / "tool_convert.py").write_text("print('x')\n")
    return root


class WorkflowLayoutTest(unittest.TestCase):
    def setUp(self):
        self.root = make_sds_workflow(Path(tempfile.mkdtemp()) / "workflow_convert")

    def test_an_sds_package_is_detected_through_a_wrapper_folder(self):
        layout = detect_workflow_layout(self.root.parent)
        self.assertTrue(layout.is_sds)
        self.assertEqual(layout.root, self.root)

    def test_an_sds_package_needs_exactly_one_workflow_cwl(self):
        (self.root / "primary" / "workflow_other.cwl").write_text(WORKFLOW)
        with self.assertRaisesRegex(RuntimeError, "exactly one primary/workflow_\\*.cwl"):
            detect_workflow_layout(self.root)

    def test_a_root_cwl_source_is_not_sds(self):
        src = Path(tempfile.mkdtemp())
        (src / "flow.cwl").write_text(WORKFLOW)
        self.assertFalse(detect_workflow_layout(src).is_sds)

    def test_inspection_reports_the_package_and_its_cwl(self):
        meta = inspect_workflow_source(self.root, want_cwl=True)
        self.assertTrue(meta["is_sds"])
        self.assertTrue(meta["has_cwl"])

    def test_inspection_without_a_workflow_cwl_has_no_cwl(self):
        (self.root / "primary" / "workflow_convert.cwl").unlink()
        meta = inspect_workflow_source(self.root, want_cwl=True)
        self.assertTrue(meta["is_sds"])
        self.assertFalse(meta["has_cwl"])

    def test_reading_returns_the_workflow_and_its_tool_cwls_as_a_list(self):
        cwl = read_workflow_cwl(self.root)
        self.assertEqual(cwl["cwl_file"], "workflow_convert.cwl")
        self.assertEqual(cwl["content"], WORKFLOW)
        # A list, not a dict keyed by filename: the frontend interceptor camelCases object keys.
        self.assertEqual(cwl["tool_cwls"], [{"cwl_file": "tool_convert.cwl", "content": TOOL}])

    def test_reading_a_root_cwl_source_is_unchanged(self):
        src = Path(tempfile.mkdtemp())
        (src / "flow.cwl").write_text(WORKFLOW)
        self.assertEqual(read_workflow_cwl(src), {"cwl_file": "flow.cwl", "content": WORKFLOW})

    def test_inspection_of_sds_workflow_lists_code_subfolders_excluding_blacklist(self):
        # SDS workflows should report code/ subfolders (like tools do), not root folders.
        (self.root / "code").mkdir(exist_ok=True)
        (self.root / "code" / "frontend").mkdir()
        (self.root / "code" / "backend").mkdir()
        (self.root / "code" / "node_modules").mkdir()  # Blacklisted
        meta = inspect_workflow_source(self.root, want_cwl=True)
        self.assertTrue(meta["is_sds"])
        self.assertEqual(sorted(meta.get("folders_in_root", [])), ["backend", "frontend"])

    def test_inspection_of_root_cwl_source_lists_root_folders(self):
        # Root-.cwl workflows should still report root folders as before.
        src = Path(tempfile.mkdtemp())
        (src / "flow.cwl").write_text(WORKFLOW)
        (src / "config").mkdir()
        meta = inspect_workflow_source(src, want_cwl=True)
        self.assertFalse(meta["is_sds"])
        # folders_in_root should list root folders for non-SDS sources
        self.assertIn("config", meta.get("folders_in_root", []))


if __name__ == "__main__":
    unittest.main()
