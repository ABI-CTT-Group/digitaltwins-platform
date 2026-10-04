"""An SDS workflow package is built as it is; a root-.cwl workflow as before.

Run from `backend/`:
    python -m unittest tests.test_workflow_build_dataset
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tests.tool_app import make_workflow_client  # noqa: I001  (sets DATABASE_PATH first)
from app.builder import build_workflow
from app.builder.build_tool import PluginBuilder
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
        self.assertTrue(result["is_sds"])

    def test_an_sds_package_needs_a_workflow_type(self):
        result = self._build(self.root, None)
        self.assertFalse(result["success"])
        self.assertIn("needs a workflow type", result["error_message"])

    def test_a_root_cwl_workflow_with_a_type_builds(self):
        src = Path(tempfile.mkdtemp())
        (src / "flow.cwl").write_text(WORKFLOW)
        result = self._build(src, "script")
        self.assertTrue(result["success"], result["error_message"])
        self.assertFalse(result["is_sds"])


class RecordingMinio:
    def __init__(self, buckets, fail=()):
        self.buckets, self.fail = buckets, fail

    def __call__(self, bucket):
        self.buckets.append(bucket)
        outer = self

        class Client:
            def upload_directory(self, path, name):
                if bucket in outer.fail:
                    raise RuntimeError("MinIO unreachable")
                return f"s3://{bucket}/{name}"
        return Client()


class GuiWorkflowBuildTest(unittest.TestCase):
    def setUp(self):
        make_workflow_client()  # fresh tables
        self.buckets, self.calls = [], []
        build_workflow.get_minio_client = RecordingMinio(self.buckets)
        self.builder = WorkflowBuilder(dataset_dir=tempfile.mkdtemp())
        self.root = make_sds_workflow(Path(tempfile.mkdtemp()) / "workflow_convert")
        (self.root / "code" / "package.json").write_text("{}")

    def _fake_build_frontend(self, _builder, frontend, expose, command, has_backend, sink=None):
        self.calls.append({"frontend": frontend, "expose": expose, "command": command, "has_backend": has_backend})
        (frontend / "dist").mkdir()
        (frontend / "dist" / "my-app.umd.js").write_text("//")
        return frontend / "dist"

    def _build(self, workflow_type="gui", side_effect=None, **gui):
        with mock.patch.object(PluginBuilder, "build_frontend", autospec=True,
                               side_effect=side_effect or self._fake_build_frontend):
            return self.builder.build({"id": "w1", "name": "convert", "source_type": "local",
                                       "local_archive_path": str(self.root), "workflow_type": workflow_type, **gui})

    def test_a_gui_workflow_gets_its_bundle_in_primary_tool_folder(self):
        result = self._build(frontend_build_command="yarn build:plugin")
        self.assertTrue(result["success"], result["error_message"])
        self.assertIn("primary/tool_convert/my-app.umd.js", _files(Path(result["dataset_path"])))
        self.assertEqual(result["tool_name"], "tool_convert")
        self.assertEqual(result["bundle_path"], f"tool-builds/{result['expose_name']}/primary")
        self.assertIn("tool-builds", self.buckets)
        [call] = self.calls
        self.assertEqual((call["expose"], call["command"], call["has_backend"]),
                         (result["expose_name"], "yarn build:plugin", False))

    def test_the_source_is_never_modified(self):
        before = _files(self.root)
        result = self._build()
        self.assertTrue(result["success"], result["error_message"])
        self.assertEqual(_files(self.root), before)
        self.assertNotIn(self.root, self.calls[0]["frontend"].parents)

    def test_a_workflow_registered_before_gui_fields_uses_the_defaults(self):
        self._build()  # no has_backend / folders / command keys at all
        [call] = self.calls
        self.assertEqual((call["frontend"].name, call["command"], call["has_backend"]),
                         ("code", "npm run build:plugin", False))

    def test_a_backend_builds_its_frontend_folder_and_keeps_its_backend(self):
        for layer in ("frontend", "backend"):
            (self.root / "code" / layer).mkdir()
        (self.root / "code" / "backend" / "docker-compose.yml").write_text("services: {}\n")
        result = self._build(has_backend=True, frontend_folder="frontend", backend_folder="backend")
        self.assertTrue(result["success"], result["error_message"])
        self.assertEqual((self.calls[0]["frontend"].name, self.calls[0]["has_backend"]), ("frontend", True))
        self.assertIn("code/backend/docker-compose.yml", _files(Path(result["dataset_path"])))

    def test_a_failed_frontend_build_fails_the_workflow_build(self):
        def failing(*args, **kwargs):
            raise RuntimeError("npm build failed: exited with code 1")
        result = self._build(side_effect=failing)
        self.assertFalse(result["success"])
        self.assertIn("npm build failed", result["error_message"])

    def test_a_failed_bundle_upload_does_not_fail_the_build(self):
        build_workflow.get_minio_client = RecordingMinio(self.buckets, fail=("tool-builds",))
        result = self._build()
        self.assertTrue(result["success"], result["error_message"])
        self.assertEqual((result["tool_name"], result["bundle_path"]), ("tool_convert", None))

    def test_script_workflows_are_not_npm_built(self):
        result = self._build(workflow_type="script")
        self.assertTrue(result["success"], result["error_message"])
        self.assertEqual((self.calls, result["tool_name"], result["bundle_path"]), ([], None, None))

    def test_a_root_cwl_gui_workflow_is_built_as_before(self):
        self.root = Path(tempfile.mkdtemp())
        (self.root / "flow.cwl").write_text(WORKFLOW)
        result = self._build()
        self.assertTrue(result["success"], result["error_message"])
        self.assertEqual((self.calls, result["tool_name"]), ([], None))


if __name__ == "__main__":
    unittest.main()
