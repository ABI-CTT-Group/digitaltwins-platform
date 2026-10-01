"""A tool upload is either source code (one root .cwl) or an SDS package (primary/tool_*.cwl).

Run from `backend/`:
    python -m unittest tests.test_tool_layout
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DATABASE_PATH", str(BACKEND_ROOT / "tmp" / "test_plugin_registry.db"))
(BACKEND_ROOT / "tmp").mkdir(parents=True, exist_ok=True)

from app.builder.tool_layout import detect_tool_layout  # noqa: E402

CWL = "cwlVersion: v1.2\nclass: CommandLineTool\ninputs: []\noutputs: []\n"


def make_sds(root: Path, cwls=("tool_convert.cwl",)) -> Path:
    (root / "dataset_description.xlsx").write_bytes(b"xlsx")
    (root / "primary").mkdir()
    (root / "code").mkdir()
    (root / "code" / "convert.py").write_text("print('hi')\n")
    for name in cwls:
        (root / "primary" / name).write_text(CWL)
    return root


class SourceLayoutTest(unittest.TestCase):
    def setUp(self):
        self.src = Path(tempfile.mkdtemp())

    def test_a_root_cwl_makes_a_source_layout(self):
        (self.src / "convert.cwl").write_text(CWL)
        layout = detect_tool_layout(self.src)
        self.assertFalse(layout.is_sds)
        self.assertEqual(layout.root, self.src)
        self.assertEqual(layout.source_dir, self.src)
        self.assertEqual(layout.cwl, self.src / "convert.cwl")

    def test_a_source_without_a_root_cwl_names_both_layouts(self):
        with self.assertRaisesRegex(RuntimeError, "exactly one .cwl.*primary/tool_\\*.cwl"):
            detect_tool_layout(self.src)


class SdsLayoutTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())

    def test_dataset_description_makes_an_sds_layout(self):
        make_sds(self.root)
        layout = detect_tool_layout(self.root)
        self.assertTrue(layout.is_sds)
        self.assertEqual(layout.source_dir, self.root / "code")
        self.assertEqual(layout.cwl, self.root / "primary" / "tool_convert.cwl")

    def test_a_root_cwl_is_ignored_in_an_sds(self):
        make_sds(self.root)
        (self.root / "stray.cwl").write_text(CWL)
        self.assertEqual(detect_tool_layout(self.root).cwl.name, "tool_convert.cwl")

    def test_an_sds_needs_exactly_one_tool_cwl(self):
        for cwls in [(), ("tool_a.cwl", "tool_b.cwl"), ("convert.cwl",)]:
            with self.subTest(cwls=cwls):
                root = make_sds(Path(tempfile.mkdtemp()), cwls)
                with self.assertRaisesRegex(RuntimeError, "exactly one primary/tool_\\*.cwl"):
                    detect_tool_layout(root)

    def test_an_sds_without_primary_is_rejected(self):
        (self.root / "dataset_description.xlsx").write_bytes(b"xlsx")
        with self.assertRaisesRegex(RuntimeError, "exactly one primary/tool_\\*.cwl"):
            detect_tool_layout(self.root)

    def test_single_wrapper_folders_are_peeled(self):
        (self.root / "tool_convert").mkdir()
        make_sds(self.root / "tool_convert")
        layout = detect_tool_layout(self.root)
        self.assertTrue(layout.is_sds)
        self.assertEqual(layout.root, self.root / "tool_convert")


if __name__ == "__main__":
    unittest.main()
