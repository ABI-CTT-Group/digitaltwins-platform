"""PluginBuilder.build_frontend: the GUI tool build shared by tool builds and gui workflow builds.

Run from `backend/`:
    python -m unittest tests.test_gui_frontend_build
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

CWL = "cwlVersion: v1.2\nclass: CommandLineTool\ninputs: []\noutputs: []\n"
# `name` before `fileName`: the lib-block rewrite stops at the first `}` (here, inside `${format}`).
VITE_CONFIG = """import { defineConfig } from 'vite'
export default defineConfig({
  plugins: [],
  build: {
    lib: { entry: './src/index.ts', name: 'placeholder', formats: ['es'], fileName: (format) => `x.${format}.js` },
    rollupOptions: { external: ['vue', 'vuetify', 'pinia', 'vue-toastification'] },
  },
})
"""


def make_frontend(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "package.json").write_text('{"name": "viewer", "version": "2.1.0"}')
    (root / "vite.config.ts").write_text(VITE_CONFIG)
    return root


def fake_npm(project_dir, *args, **kwargs):
    """Stands in for frontend_install / frontend_build: 'builds' dist/my-app.umd.js."""
    (project_dir / "dist").mkdir(exist_ok=True)
    (project_dir / "dist" / "my-app.umd.js").write_text("//")
    return {"success": True, "stdout": "", "stderr": ""}


class FakeMinio:
    def upload_directory(self, local, prefix):
        return f"s3://tool-builds/{prefix}"


class BuildFrontendTest(unittest.TestCase):
    def setUp(self):
        self.builder = PluginBuilder(dataset_dir=tempfile.mkdtemp())
        self.frontend = make_frontend(Path(tempfile.mkdtemp()) / "frontend")

    def _build(self, has_backend=False, build=fake_npm):
        with mock.patch.object(self.builder, "frontend_install", side_effect=fake_npm), \
             mock.patch.object(self.builder, "frontend_build", side_effect=build) as npm_build:
            out = self.builder.build_frontend(self.frontend, "viewer_ab12cd34", "yarn build", has_backend)
        return out, npm_build

    def test_builds_the_umd_bundle_under_the_expose_name(self):
        out, npm_build = self._build()
        self.assertEqual(out, self.frontend / "dist")
        config = (self.frontend / "vite.config.ts").read_text()
        self.assertIn("name: 'viewer_ab12cd34'", config)
        self.assertIn("formats: ['umd']", config)
        self.assertIn("my-app.${format}.js", config)
        self.assertEqual(npm_build.call_args.args[:2], (self.frontend, "yarn build"))
        self.assertFalse((self.frontend / ".env").exists())

    def test_a_backend_gets_its_route_prefix(self):
        self._build(has_backend=True)
        self.assertIn("VITE_PLUGIN_ROUTE_PREFIX=/plugin/viewer_ab12cd34", (self.frontend / ".env").read_text())

    def test_a_folder_without_package_json_is_refused(self):
        (self.frontend / "package.json").unlink()
        with self.assertRaisesRegex(RuntimeError, "No package.json"):
            self._build()

    def test_a_failed_npm_build_fails(self):
        def failed(*args, **kwargs):
            return {"success": False, "error": "exited with code 1"}
        with self.assertRaisesRegex(RuntimeError, "npm build failed: exited with code 1"):
            self._build(build=failed)


class PluginGuiBuildTest(unittest.TestCase):
    """Characterisation: a GUI tool build still puts the bundle next to the CWL."""

    def test_a_gui_tool_build_puts_the_bundle_in_primary(self):
        src = make_frontend(Path(tempfile.mkdtemp()))
        (src / "viewer.cwl").write_text(CWL)
        builder = PluginBuilder(dataset_dir=tempfile.mkdtemp())
        with mock.patch.object(build_tool, "get_minio_client", lambda bucket=None: FakeMinio()), \
             mock.patch.object(builder, "frontend_install", side_effect=fake_npm), \
             mock.patch.object(builder, "frontend_build", side_effect=fake_npm), \
             mock.patch.object(PluginBuilder, "_update_plugin_version", return_value="2.1.0"):
            result = builder.build({"id": "p1", "name": "Viewer", "label": "GUI", "has_backend": False,
                                    "source_type": "local", "local_archive_path": str(src),
                                    "frontend_build_command": "npm run build:plugin", "metadata": {}})
        self.assertTrue(result["success"], result["error_message"])
        self.assertEqual(sorted(p.name for p in (Path(result["dataset_path"]) / "primary").iterdir()),
                         ["my-app.umd.js", "tool_viewer.cwl"])


if __name__ == "__main__":
    unittest.main()
