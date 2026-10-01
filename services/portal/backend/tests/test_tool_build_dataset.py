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
from app.builder.build_tool import PluginBuilder  # noqa: E402
from app.builder.tool_layout import root_cwl  # noqa: E402

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


def make_sds(root: Path) -> Path:
    """An SDS-packaged Script tool, as in tests/data/tool_dicom_to_nifti."""
    (root / "dataset_description.xlsx").write_bytes(b"curated metadata")
    (root / "README.md").write_text("# convert\n")
    (root / "primary").mkdir()
    (root / "primary" / "tool_convert.cwl").write_text(CWL)
    (root / "code").mkdir()
    (root / "code" / "convert.py").write_text("print('hi')\n")
    return root


def tree(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


class CreateSparcDatasetFromSdsTest(unittest.TestCase):
    def setUp(self):
        self.builder = PluginBuilder(dataset_dir=tempfile.mkdtemp())
        self.sds = make_sds(Path(tempfile.mkdtemp()))

    def test_a_script_sds_is_passed_through_untouched(self):
        out = self.builder.create_sparc_dataset(self.sds, "Script", False, None, "convert_ab12cd34")
        self.assertEqual(tree(out), tree(self.sds))

    def test_a_notebook_sds_is_passed_through_untouched(self):
        (self.sds / "code" / "convert.py").rename(self.sds / "code" / "convert.ipynb")
        out = self.builder.create_sparc_dataset(self.sds, "Notebook", False, None, "convert_ab12cd34")
        self.assertEqual(tree(out), tree(self.sds))

    def test_a_gui_sds_gets_its_bundle_next_to_the_cwl(self):
        dist = Path(tempfile.mkdtemp())
        (dist / "my-app.umd.js").write_text("//")
        out = self.builder.create_sparc_dataset(self.sds, "GUI", False, dist, "convert_ab12cd34")
        self.assertEqual(sorted(p.name for p in (out / "primary").iterdir()), ["my-app.umd.js", "tool_convert.cwl"])
        self.assertEqual((out / "dataset_description.xlsx").read_bytes(), b"curated metadata")

    def test_build_leftovers_in_code_are_not_copied(self):
        (self.sds / "code" / "node_modules").mkdir()
        (self.sds / "code" / "node_modules" / "dep.js").write_text("//")
        out = self.builder.create_sparc_dataset(self.sds, "GUI", False, None, "convert_ab12cd34")
        self.assertFalse((out / "code" / "node_modules").exists())
        self.assertTrue((out / "code" / "convert.py").is_file())

    def test_a_gui_sds_with_a_backend_keeps_its_layers_under_code(self):
        for layer in ("frontend", "backend"):
            (self.sds / "code" / layer).mkdir()
            (self.sds / "code" / layer / "node_modules").mkdir()
            (self.sds / "code" / layer / "main.txt").write_text(layer)
        out = self.builder.create_sparc_dataset(self.sds, "GUI", True, None, "convert_ab12cd34")
        self.assertTrue((out / "code" / "backend" / "main.txt").is_file())
        self.assertFalse((out / "code" / "frontend" / "node_modules").exists())


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

    def test_a_local_sds_builds_and_keeps_its_metadata(self):
        sds = make_sds(Path(tempfile.mkdtemp()))

        class FakeMinio:
            def upload_directory(self, local, prefix):
                return f"s3://tool-builds/{prefix}"

        with mock.patch.object(build_tool, "get_minio_client", lambda bucket=None: FakeMinio()):
            result = PluginBuilder(dataset_dir=tempfile.mkdtemp()).build({
                "id": "p1", "name": "Convert", "label": "Script", "source_type": "local",
                "local_archive_path": str(sds), "metadata": {},
            })

        self.assertTrue(result["success"], result["error_message"])
        self.assertEqual(tree(Path(result["dataset_path"])), tree(sds))

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
