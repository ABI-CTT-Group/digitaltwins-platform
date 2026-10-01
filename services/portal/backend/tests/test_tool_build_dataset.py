"""The built SPARC folder is what digitaltwins-api ingests: exactly one CWL, as primary/tool_<stem>.cwl.

Run from `backend/`:
    python -m unittest tests.test_tool_build_dataset
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DATABASE_PATH", str(BACKEND_ROOT / "tmp" / "test_plugin_registry.db"))
(BACKEND_ROOT / "tmp").mkdir(parents=True, exist_ok=True)

from app.builder import build_tool  # noqa: E402
from app.builder.build_tool import PluginBuilder, root_cwl  # noqa: E402

CWL = "cwlVersion: v1.2\nclass: CommandLineTool\ninputs: []\noutputs: []\n"


class RootCwlTest(unittest.TestCase):
    def setUp(self):
        self.src = Path(tempfile.mkdtemp())

    def test_exactly_one_root_cwl_is_required(self):
        with self.assertRaisesRegex(RuntimeError, "exactly one .cwl"):
            root_cwl(self.src)
        (self.src / "a.cwl").write_text(CWL)
        self.assertEqual(root_cwl(self.src), self.src / "a.cwl")
        (self.src / "b.cwl").write_text(CWL)
        with self.assertRaisesRegex(RuntimeError, "a.cwl, b.cwl"):
            root_cwl(self.src)

    def test_nested_cwl_files_do_not_count(self):
        (self.src / "code").mkdir()
        (self.src / "code" / "inner.cwl").write_text(CWL)
        with self.assertRaises(RuntimeError):
            root_cwl(self.src)


class CreateSparcDatasetTest(unittest.TestCase):
    def setUp(self):
        self.builder = PluginBuilder(dataset_dir=tempfile.mkdtemp())
        self.src = Path(tempfile.mkdtemp())
        (self.src / "convert.py").write_text("print('hi')\n")

    def _primary(self, label, cwl_name="convert.cwl", build_output=None):
        (self.src / cwl_name).write_text(CWL)
        out = self.builder.create_sparc_dataset(self.src, label, False, build_output, "convert_ab12cd34")
        return sorted(p.name for p in (out / "primary").iterdir()), out

    def test_script_cwl_is_renamed_to_tool_stem(self):
        primary, out = self._primary("Script")
        self.assertEqual(primary, ["tool_convert.cwl"])
        self.assertTrue((out / "code" / "convert.py").is_file())

    def test_a_tool_prefixed_cwl_keeps_its_name(self):
        self.assertEqual(self._primary("Script", cwl_name="tool_convert.cwl")[0], ["tool_convert.cwl"])

    def test_notebook_is_packaged_like_a_script(self):
        self.assertEqual(self._primary("Notebook")[0], ["tool_convert.cwl"])

    def test_gui_gets_its_bundle_and_the_cwl(self):
        dist = Path(tempfile.mkdtemp())
        (dist / "my-app.umd.js").write_text("//")
        self.assertEqual(self._primary("GUI", build_output=dist)[0], ["my-app.umd.js", "tool_convert.cwl"])


class BuildUploadTest(unittest.TestCase):
    def test_test_builds_go_to_the_tool_builds_bucket_not_tools(self):
        src = Path(tempfile.mkdtemp())
        (src / "convert.cwl").write_text(CWL)
        (src / "convert.py").write_text("print('hi')\n")
        buckets = []

        class FakeMinio:
            def upload_directory(self, local, prefix):
                return f"s3://{buckets[-1]}/{prefix}"

        def fake_client(bucket=None):
            buckets.append(bucket)
            return FakeMinio()

        with mock.patch.object(build_tool, "get_minio_client", fake_client):
            result = PluginBuilder(dataset_dir=tempfile.mkdtemp()).build({
                "id": "p1", "name": "Convert", "label": "Script", "source_type": "local",
                "local_archive_path": str(src), "metadata": {},
            })

        self.assertTrue(result["success"], result["error_message"])
        self.assertEqual(buckets, ["tool-builds"])
        self.assertTrue(result["s3_path"].startswith("s3://tool-builds/"))

    def test_a_source_without_a_root_cwl_fails_the_build(self):
        src = Path(tempfile.mkdtemp())
        (src / "convert.py").write_text("print('hi')\n")
        result = PluginBuilder(dataset_dir=tempfile.mkdtemp()).build({
            "id": "p1", "name": "Convert", "label": "Script", "source_type": "local",
            "local_archive_path": str(src), "metadata": {},
        })
        self.assertFalse(result["success"])
        self.assertIn("exactly one .cwl", result["error_message"])


if __name__ == "__main__":
    unittest.main()
