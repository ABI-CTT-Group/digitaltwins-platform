"""An SDS workflow package is built as it is; a root-.cwl workflow as before.

Run from `backend/`:
    python -m unittest tests.test_workflow_build_dataset
"""
import tempfile
import unittest
from pathlib import Path

from tests.tool_app import make_workflow_client  # noqa: I001  (sets DATABASE_PATH first)
from app.builder import build_workflow
from app.builder.build_workflow import WorkflowBuilder
from tests.test_workflow_layout import WORKFLOW, make_sds_workflow


class FakeMinio:
    def upload_directory(self, path, name):
        return f"s3://workflows/{name}"


def _files(root: Path):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file())


class WorkflowBuildDatasetTest(unittest.TestCase):
    def setUp(self):
        make_workflow_client()  # fresh tables
        build_workflow.get_minio_client = lambda bucket: FakeMinio()
        self.builder = WorkflowBuilder(dataset_dir=tempfile.mkdtemp())
        self.root = make_sds_workflow(Path(tempfile.mkdtemp()) / "workflow_convert")

    def _build(self, source, workflow_type):
        return self.builder.build({"id": "w1", "name": "convert", "source_type": "local",
                                   "local_archive_path": str(source), "workflow_type": workflow_type})

    def test_an_sds_package_is_copied_as_it_is(self):
        (self.root / ".git").mkdir()
        (self.root / ".git" / "HEAD").write_text("ref")
        out = self.builder.create_sparc_dataset(self.root, None, "convert_ab12")
        self.assertEqual(_files(out), [p for p in _files(self.root) if not p.startswith(".git/")])

    def test_a_root_cwl_source_is_built_as_before(self):
        src = Path(tempfile.mkdtemp())
        (src / "flow.cwl").write_text(WORKFLOW)
        out = self.builder.create_sparc_dataset(src, None, "flow_ab12")
        self.assertIn("primary/flow.cwl", _files(out))
        self.assertIn("code/flow.cwl", _files(out))

    def test_an_sds_build_succeeds_with_a_workflow_type(self):
        result = self._build(self.root, "script")
        self.assertTrue(result["success"], result["error_message"])
        self.assertIn("primary/workflow_convert.cwl", _files(Path(result["dataset_path"])))

    def test_an_sds_package_needs_a_workflow_type(self):
        result = self._build(self.root, None)
        self.assertFalse(result["success"])
        self.assertIn("needs a workflow type", result["error_message"])

    def test_a_workflow_type_needs_an_sds_package(self):
        src = Path(tempfile.mkdtemp())
        (src / "flow.cwl").write_text(WORKFLOW)
        result = self._build(src, "script")
        self.assertFalse(result["success"])
        self.assertIn("not an SDS workflow package", result["error_message"])


if __name__ == "__main__":
    unittest.main()
