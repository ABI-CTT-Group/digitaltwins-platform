"""
Plugin build and deploy commands are third-party code, so the portal's own
database credentials (PORTAL_DB_*) must not reach their environment.

Run from `backend/`:
    python -m unittest tests.test_subprocess_env_scrub
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

from app.builder.build_tool import PluginBuilder  # noqa: E402
from app.builder.deploy_tool import PluginDeployer  # noqa: E402

PORTAL_DB_ENV = {"PORTAL_DB_HOST": "database", "PORTAL_DB_USER": "portal", "PORTAL_DB_PASSWORD": "secret"}


class PluginSubprocessEnvTest(unittest.TestCase):
    def assert_scrubbed(self, env):
        self.assertIsNotNone(env)
        for key in PORTAL_DB_ENV:
            self.assertNotIn(key, env)
        self.assertEqual(env.get("PROJECT_NAME"), "keep-me")

    def test_compose_execute_env_excludes_portal_db(self):
        with mock.patch.dict(os.environ, {**PORTAL_DB_ENV, "PROJECT_NAME": "keep-me"}), \
                mock.patch("app.builder.deploy_tool.stream_process", return_value=0) as sp:
            PluginDeployer._compose_execute(Path("."), "docker compose up -d", extra_env={"PLUGIN_ROUTE_PREFIX": "/plugin/x"})
        env = sp.call_args.kwargs["env"]
        self.assert_scrubbed(env)
        self.assertEqual(env["PLUGIN_ROUTE_PREFIX"], "/plugin/x")

    def test_frontend_build_env_excludes_portal_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            builder = PluginBuilder(dataset_dir=str(Path(tmp) / "datasets"))
            with mock.patch.dict(os.environ, {**PORTAL_DB_ENV, "PROJECT_NAME": "keep-me"}), \
                    mock.patch("app.builder.build_tool.stream_process", return_value=0) as sp:
                builder._run_streaming(["yarn", "build"], cwd=tmp)
        self.assert_scrubbed(sp.call_args.kwargs.get("env"))


if __name__ == "__main__":
    unittest.main()
