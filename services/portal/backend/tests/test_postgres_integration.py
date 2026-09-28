"""
Postgres integration tests for the portal database layer.

Skipped unless PORTAL_TEST_DB_HOST is set. Each test class creates a throwaway
database on that server (so the role needs CREATEDB) and drops it afterwards.

Run from `backend/`, e.g. against the platform `database` service:
    PORTAL_TEST_DB_HOST=database PORTAL_TEST_DB_USER=admin PORTAL_TEST_DB_PASSWORD=<REDACTED> \
        python -m unittest tests.test_postgres_integration
"""
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_PATH", str(BACKEND_ROOT / "tmp" / "test_plugin_registry.db"))
(BACKEND_ROOT / "tmp").mkdir(parents=True, exist_ok=True)

from sqlalchemy import create_engine, inspect, text  # noqa: E402
from sqlalchemy.engine import URL  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database.database import init_db, migrate_add_missing_columns  # noqa: E402
from app.models.db_model import Base, PORTAL_DB_SCHEMA, Plugin, PluginBuild, PluginDeployment  # noqa: E402
from tests.test_db_constraints import add_plugin_with_deployment  # noqa: E402

PORTAL_TABLES = set(Base.metadata.tables)


def _server_url(database: str) -> URL:
    return URL.create(
        "postgresql+psycopg2",
        host=os.environ["PORTAL_TEST_DB_HOST"],
        port=int(os.getenv("PORTAL_TEST_DB_PORT", "5432")),
        database=database,
        username=os.getenv("PORTAL_TEST_DB_USER", "postgres"),
        password=os.getenv("PORTAL_TEST_DB_PASSWORD"),
    )


@unittest.skipUnless(os.getenv("PORTAL_TEST_DB_HOST"), "PORTAL_TEST_DB_HOST not set")
class PostgresTestCase(unittest.TestCase):
    """Gives each test a fresh database and an engine configured like the app's."""

    def setUp(self):
        self.db_name = f"portal_test_{uuid.uuid4().hex[:8]}"
        self.admin = create_engine(_server_url("postgres"), isolation_level="AUTOCOMMIT")
        with self.admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{self.db_name}"'))
        with mock.patch.dict(os.environ, {
            "PORTAL_DB_HOST": os.environ["PORTAL_TEST_DB_HOST"],
            "PORTAL_DB_PORT": os.getenv("PORTAL_TEST_DB_PORT", "5432"),
            "PORTAL_DB_NAME": self.db_name,
            "PORTAL_DB_USER": os.getenv("PORTAL_TEST_DB_USER", "postgres"),
            "PORTAL_DB_PASSWORD": os.getenv("PORTAL_TEST_DB_PASSWORD", ""),
        }):
            from app.models.db_model import _build_engine
            self.engine = _build_engine()

    def tearDown(self):
        self.engine.dispose()
        with self.admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{self.db_name}" WITH (FORCE)'))
        self.admin.dispose()


class InitDbTest(PostgresTestCase):
    def test_tables_and_enum_created_in_portal_schema_only(self):
        init_db(bind=self.engine)
        insp = inspect(self.engine)
        self.assertEqual(set(insp.get_table_names(schema=PORTAL_DB_SCHEMA)), PORTAL_TABLES)
        self.assertEqual(insp.get_table_names(schema="public"), [])
        with self.engine.connect() as conn:
            enum_schema = conn.execute(text(
                "SELECT n.nspname FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace "
                "WHERE t.typname = 'plugin_label'"
            )).scalar_one()
        self.assertEqual(enum_schema, PORTAL_DB_SCHEMA)

    def test_init_db_is_idempotent(self):
        init_db(bind=self.engine)
        init_db(bind=self.engine)

    def test_init_db_as_schema_owner_without_database_create_privilege(self):
        # The platform's `portal` role owns the schema but cannot CREATE in the database,
        # and Postgres checks that privilege even for CREATE SCHEMA IF NOT EXISTS.
        role, password = f"portal_role_{uuid.uuid4().hex[:8]}", uuid.uuid4().hex
        with self.admin.connect() as conn:
            conn.execute(text(f"CREATE ROLE {role} LOGIN PASSWORD '{password}'"))
        try:
            with self.engine.begin() as conn:
                conn.execute(text(f"CREATE SCHEMA {PORTAL_DB_SCHEMA} AUTHORIZATION {role}"))
            with mock.patch.dict(os.environ, {"PORTAL_DB_USER": role, "PORTAL_DB_PASSWORD": password,
                                              "PORTAL_DB_HOST": os.environ["PORTAL_TEST_DB_HOST"],
                                              "PORTAL_DB_PORT": os.getenv("PORTAL_TEST_DB_PORT", "5432"),
                                              "PORTAL_DB_NAME": self.db_name}):
                from app.models.db_model import _build_engine
                role_engine = _build_engine()
            init_db(bind=role_engine)
            self.assertEqual(set(inspect(role_engine).get_table_names(schema=PORTAL_DB_SCHEMA)), PORTAL_TABLES)
            role_engine.dispose()
        finally:
            self.engine.dispose()
            with self.admin.connect() as conn:
                conn.execute(text(f'DROP DATABASE IF EXISTS "{self.db_name}" WITH (FORCE)'))
                conn.execute(text(f"DROP ROLE {role}"))

    def test_missing_columns_are_added_back(self):
        init_db(bind=self.engine)
        with self.engine.begin() as conn:
            conn.execute(text("ALTER TABLE plugins DROP COLUMN local_archive_path"))
            conn.execute(text("ALTER TABLE plugin_deployments DROP COLUMN up"))
        migrate_add_missing_columns(bind=self.engine)
        insp = inspect(self.engine)
        self.assertIn("local_archive_path", {c["name"] for c in insp.get_columns("plugins")})
        self.assertIn("up", {c["name"] for c in insp.get_columns("plugin_deployments")})


class ForeignKeyTest(PostgresTestCase):
    def test_deploy_and_cascade_delete(self):
        init_db(bind=self.engine)
        session = sessionmaker(bind=self.engine)()
        plugin = add_plugin_with_deployment(session)
        session.delete(plugin)
        session.commit()
        self.assertEqual(session.query(Plugin).count(), 0)
        self.assertEqual(session.query(PluginBuild).count(), 0)
        self.assertEqual(session.query(PluginDeployment).count(), 0)
        session.close()


class MigrateToPostgresTest(PostgresTestCase):
    def test_sqlite_to_postgres_end_to_end(self):
        import tempfile
        from app.cli.migrate_sqlite_to_postgres import migrate
        from tests.test_migrate_sqlite_to_postgres import make_source, rows

        with tempfile.TemporaryDirectory() as tmp:
            source = make_source(Path(tmp) / "plugin_registry.db")
            counts, _ = migrate(source, self.engine)
            for table in Base.metadata.sorted_tables:
                self.assertEqual(rows(self.engine, table), rows(source, table), table.name)
            self.assertEqual(sum(counts.values()), sum(len(rows(source, t)) for t in Base.metadata.sorted_tables))
            source.dispose()
        with self.engine.connect() as conn:
            self.assertTrue(conn.execute(text("SELECT plugin_metadata IS NULL FROM plugins WHERE id = 'p2'")).scalar_one())
            self.assertEqual(conn.execute(text("SELECT plugin_metadata->'k'->>1 FROM plugins WHERE id = 'p1'")).scalar_one(), "two")


if __name__ == "__main__":
    unittest.main()
