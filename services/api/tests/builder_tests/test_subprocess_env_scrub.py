"""
Plugin build and deploy commands are third-party code, so the portal's own
database credentials (BUILDER_DB_*) must not reach their environment.

Run from `services/api/`:
    python -m pytest tests/builder_tests/test_subprocess_env_scrub.py
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_PATH", str(BACKEND_ROOT / "tmp" / "test_plugin_registry.db"))
(BACKEND_ROOT / "tmp").mkdir(parents=True, exist_ok=True)

from builder.engine.build_tool import PluginBuilder  # noqa: E402
from builder.engine.deploy_tool import PluginDeployer  # noqa: E402

BUILDER_DB_ENV = {"BUILDER_DB_HOST": "database", "BUILDER_DB_USER": "portal", "BUILDER_DB_PASSWORD": "secret"}


class PluginSubprocessEnvTest(unittest.TestCase):
    def assert_scrubbed(self, env):
        self.assertIsNotNone(env)
        for key in BUILDER_DB_ENV:
            self.assertNotIn(key, env)
        self.assertEqual(env.get("PROJECT_NAME"), "keep-me")

    def test_compose_execute_env_excludes_portal_db(self):
        with mock.patch.dict(os.environ, {**BUILDER_DB_ENV, "PROJECT_NAME": "keep-me"}), \
                mock.patch("builder.engine.deploy_tool.stream_process", return_value=0) as sp:
            PluginDeployer._compose_execute(Path("."), "docker compose up -d", extra_env={"PLUGIN_ROUTE_PREFIX": "/plugin/x"})
        env = sp.call_args.kwargs["env"]
        self.assert_scrubbed(env)
        self.assertEqual(env["PLUGIN_ROUTE_PREFIX"], "/plugin/x")

    def test_frontend_build_env_excludes_portal_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = PluginBuilder(dataset_dir=str(Path(tmp) / "datasets"))
            with mock.patch.dict(os.environ, {**BUILDER_DB_ENV, "PROJECT_NAME": "keep-me"}), \
                    mock.patch("builder.engine.build_tool.stream_process", return_value=0) as sp:
                builder._run_streaming(["yarn", "build"], cwd=tmp)
        self.assert_scrubbed(sp.call_args.kwargs.get("env"))


if __name__ == "__main__":
    unittest.main()
