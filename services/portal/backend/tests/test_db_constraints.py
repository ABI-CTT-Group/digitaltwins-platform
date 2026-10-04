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
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.models.db_model import Base, Plugin, PluginBuild, PluginDeployment, Workflow, WorkflowBuild  # noqa: E402


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


def add_workflow_build(session):
    workflow = Workflow(name="w", version="1", repository_url="local://w", workflow_type="gui")
    session.add(workflow)
    session.flush()
    build = WorkflowBuild(workflow_id=workflow.id, build_id="wf-build-key")
    session.add(build)
    session.flush()
    return workflow, build


class WorkflowDeploymentTest(unittest.TestCase):
    def test_a_deployment_can_belong_to_a_workflow_build(self):
        session = make_fk_session()
        _, build = add_workflow_build(session)
        session.add(PluginDeployment(workflow_build_id=build.build_id, deploy_id="d1"))
        session.commit()
        self.assertEqual(session.query(PluginDeployment).one().workflow_build.build_id, "wf-build-key")

    def test_a_deployment_needs_a_build(self):
        session = make_fk_session()
        session.add(PluginDeployment(deploy_id="d2"))
        with self.assertRaises(IntegrityError):
            session.commit()

    def test_a_deployment_belongs_to_only_one_build(self):
        session = make_fk_session()
        add_plugin_with_deployment(session)
        _, build = add_workflow_build(session)
        session.add(PluginDeployment(build_id="build-business-key", workflow_build_id=build.build_id, deploy_id="d3"))
        with self.assertRaises(IntegrityError):
            session.commit()

    def test_delete_workflow_cascades_its_deployments(self):
        session = make_fk_session()
        workflow, build = add_workflow_build(session)
        session.add(PluginDeployment(workflow_build_id=build.build_id, deploy_id="d4"))
        session.commit()
        session.delete(workflow)
        session.commit()
        self.assertEqual(session.query(PluginDeployment).count(), 0)

    def test_the_postgres_migration_leaves_sqlite_alone(self):
        from app.database.database import migrate_plugin_deployments_for_workflows
        engine = create_engine("sqlite://")
        Base.metadata.create_all(engine)
        migrate_plugin_deployments_for_workflows(engine)  # must not raise


if __name__ == "__main__":
    unittest.main()
