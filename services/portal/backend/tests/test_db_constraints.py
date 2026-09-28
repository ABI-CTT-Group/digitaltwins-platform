"""
Foreign-key tests for the portal ORM models, run on SQLite with FK enforcement
switched on so they behave like Postgres (plain SQLite ignores foreign keys).

Run from `backend/`:
    python -m unittest tests.test_db_constraints
"""
import os
import sys
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_PATH", str(BACKEND_ROOT / "tmp" / "test_plugin_registry.db"))
(BACKEND_ROOT / "tmp").mkdir(parents=True, exist_ok=True)

from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.models.db_model import Base, Plugin, PluginBuild, PluginDeployment  # noqa: E402


def make_fk_session():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def add_plugin_with_deployment(session):
    plugin = Plugin(
        name="p", version="1", repository_url="https://example.invalid/p.git",
        label="GUI", has_backend=True, frontend_folder="fe", frontend_build_command="yarn build",
    )
    session.add(plugin)
    session.flush()
    build = PluginBuild(plugin_id=plugin.id, build_id="build-business-key")
    session.add(build)
    session.flush()
    # Same as the deploy endpoint: build_id holds the build's business key.
    deployment = PluginDeployment(plugin_id=plugin.id, build_id=build.build_id, deploy_id="d1")
    session.add(deployment)
    session.commit()
    return plugin


class PluginDeploymentForeignKeyTest(unittest.TestCase):
    def test_deployment_references_build_business_key(self):
        session = make_fk_session()
        add_plugin_with_deployment(session)
        self.assertEqual(session.query(PluginDeployment).one().build.build_id, "build-business-key")

    def test_delete_plugin_cascades_builds_and_deployments(self):
        session = make_fk_session()
        plugin = add_plugin_with_deployment(session)
        session.delete(plugin)
        session.commit()
        self.assertEqual(session.query(PluginBuild).count(), 0)
        self.assertEqual(session.query(PluginDeployment).count(), 0)


if __name__ == "__main__":
    unittest.main()
