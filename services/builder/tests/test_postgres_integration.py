"""
Postgres integration tests for the portal database layer.

Skipped unless BUILDER_TEST_DB_HOST is set. Each test class creates a throwaway
database on that server (so the role needs CREATEDB) and drops it afterwards.

Run from `services/builder/`, e.g. against the platform `database` service:
    BUILDER_TEST_DB_HOST=database BUILDER_TEST_DB_USER=admin BUILDER_TEST_DB_PASSWORD=<REDACTED> \
        python -m pytest tests/test_postgres_integration.py
"""
import os
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_PATH", str(BACKEND_ROOT / "tmp" / "test_plugin_registry.db"))
(BACKEND_ROOT / "tmp").mkdir(parents=True, exist_ok=True)

from sqlalchemy import create_engine, inspect, text  # noqa: E402
from sqlalchemy.engine import URL  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.database.database import init_db  # noqa: E402
from app.models.db_model import Base, PORTAL_DB_SCHEMA, Plugin, PluginBuild, PluginDeployment  # noqa: E402
from tests.test_db_constraints import add_plugin_with_deployment  # noqa: E402

PORTAL_TABLES = set(Base.metadata.tables) | {"schema_migrations"}
SCHEMA_2026_09_28 = Path(__file__).resolve().parent / "fixtures" / "portal_2026_09_28.sql"


def schema_snapshot(engine):
    """The parts of the portal schema the models describe: what create_all and the migrations must agree on.

    Columns are keyed by name, since a column added to an existing table goes last.
    """
    insp = inspect(engine)
    tables = {}
    for name in Base.metadata.tables:
        tables[name] = {
            "columns": {c["name"]: (str(c["type"]), c["nullable"], c["default"]) for c in insp.get_columns(name)},
            "primary_key": insp.get_pk_constraint(name)["constrained_columns"],
            "foreign_keys": sorted((fk["name"], tuple(fk["constrained_columns"]), fk["referred_table"],
                                    tuple(fk["referred_columns"]), fk["options"].get("ondelete"))
                                   for fk in insp.get_foreign_keys(name)),
            "unique": sorted((u["name"], tuple(u["column_names"])) for u in insp.get_unique_constraints(name)),
            "checks": sorted((c["name"], c["sqltext"]) for c in insp.get_check_constraints(name)),
            "indexes": sorted((i["name"], tuple(i["column_names"]), i["unique"]) for i in insp.get_indexes(name)),
        }
    enums = {}
    with engine.connect() as conn:
        for type_name, label in conn.execute(text(
                "SELECT t.typname, e.enumlabel FROM pg_enum e JOIN pg_type t ON t.oid = e.enumtypid "
                "JOIN pg_namespace n ON n.oid = t.typnamespace WHERE n.nspname = :schema "
                "ORDER BY t.typname, e.enumsortorder"), {"schema": PORTAL_DB_SCHEMA}):
            enums.setdefault(type_name, []).append(label)
    return {"tables": tables, "enums": enums}


def _server_url(database: str) -> URL:
    return URL.create(
        "postgresql+psycopg2",
        host=os.environ["BUILDER_TEST_DB_HOST"],
        port=int(os.getenv("BUILDER_TEST_DB_PORT", "5432")),
        database=database,
        username=os.getenv("BUILDER_TEST_DB_USER", "postgres"),
        password=os.getenv("BUILDER_TEST_DB_PASSWORD"),
    )


@unittest.skipUnless(os.getenv("BUILDER_TEST_DB_HOST"), "BUILDER_TEST_DB_HOST not set")
class PostgresTestCase(unittest.TestCase):
    """Gives each test a fresh database and an engine configured like the app's."""

    def setUp(self):
        self.db_name = f"portal_test_{uuid.uuid4().hex[:8]}"
        self.admin = create_engine(_server_url("postgres"), isolation_level="AUTOCOMMIT")
        with self.admin.connect() as conn:
            conn.execute(text(f'CREATE DATABASE "{self.db_name}"'))
        with mock.patch.dict(os.environ, {
            "BUILDER_DB_HOST": os.environ["BUILDER_TEST_DB_HOST"],
            "BUILDER_DB_PORT": os.getenv("BUILDER_TEST_DB_PORT", "5432"),
            "BUILDER_DB_NAME": self.db_name,
            "BUILDER_DB_USER": os.getenv("BUILDER_TEST_DB_USER", "postgres"),
            "BUILDER_DB_PASSWORD": os.getenv("BUILDER_TEST_DB_PASSWORD", ""),
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
            with mock.patch.dict(os.environ, {"BUILDER_DB_USER": role, "BUILDER_DB_PASSWORD": password,
                                              "BUILDER_DB_HOST": os.environ["BUILDER_TEST_DB_HOST"],
                                              "BUILDER_DB_PORT": os.getenv("BUILDER_TEST_DB_PORT", "5432"),
                                              "BUILDER_DB_NAME": self.db_name}):
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

    def test_an_existing_label_enum_gains_new_values(self):
        # Databases created before the Notebook label have plugin_label = ('GUI', 'Script').
        with self.engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {PORTAL_DB_SCHEMA}"))
            conn.execute(text(f"CREATE TYPE {PORTAL_DB_SCHEMA}.plugin_label AS ENUM ('GUI', 'Script')"))
        init_db(bind=self.engine)
        with self.engine.connect() as conn:
            labels = conn.execute(text("SELECT unnest(enum_range(NULL::plugin_label))::text")).scalars().all()
        self.assertEqual(labels, ["GUI", "Script", "Notebook"])


class MigrationsTest(PostgresTestCase):
    """init_db applies app/database/migrations/ on Postgres; 0001 also catches up schemas built since 2026-09-28."""

    def _execute(self, sql, params=None):
        with self.engine.begin() as conn:
            return conn.execute(text(sql), params or {})

    def _applied(self):
        return self._execute("SELECT version FROM portal.schema_migrations ORDER BY version").scalars().all()

    def _fresh_snapshot(self):
        """The schema init_db builds from nothing; leaves the database empty again."""
        init_db(bind=self.engine)
        snapshot = schema_snapshot(self.engine)
        self._execute(f"DROP SCHEMA {PORTAL_DB_SCHEMA} CASCADE")
        return snapshot

    def _load_2026_09_28(self):
        with self.engine.begin() as conn:
            conn.exec_driver_sql(SCHEMA_2026_09_28.read_text())

    def test_the_migrations_build_the_schema_the_models_describe(self):
        with self.engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {PORTAL_DB_SCHEMA}"))
        Base.metadata.create_all(self.engine)
        from_models = schema_snapshot(self.engine)
        self._execute(f"DROP SCHEMA {PORTAL_DB_SCHEMA} CASCADE")

        init_db(bind=self.engine)

        self.assertEqual(schema_snapshot(self.engine), from_models)
        self.assertEqual(self._applied(), ["0001"])

    def test_a_second_start_changes_nothing(self):
        init_db(bind=self.engine)
        before = schema_snapshot(self.engine)
        init_db(bind=self.engine)
        self.assertEqual(schema_snapshot(self.engine), before)
        self.assertEqual(self._applied(), ["0001"])

    def test_a_schema_the_old_startup_code_built_is_only_recorded(self):
        # Before numbered migrations, init_db ran create_all (plus catch-up code) on every start.
        with self.engine.begin() as conn:
            conn.execute(text(f"CREATE SCHEMA {PORTAL_DB_SCHEMA}"))
        Base.metadata.create_all(self.engine)
        before = schema_snapshot(self.engine)
        init_db(bind=self.engine)
        self.assertEqual(schema_snapshot(self.engine), before)
        self.assertEqual(self._applied(), ["0001"])

    def test_the_2026_09_28_schema_catches_up_and_keeps_its_rows(self):
        fresh = self._fresh_snapshot()
        self._load_2026_09_28()
        self._execute("INSERT INTO plugins (id, name, version, repository_url, source_type, label, has_backend, "
                      "frontend_folder, frontend_build_command) "
                      "VALUES ('p1', 'n', '1', 'r', 'github', 'GUI', true, 'f', 'npm run build')")
        self._execute("INSERT INTO plugin_builds (id, plugin_id, build_id, status) VALUES ('b1', 'p1', 'bk1', 'ok')")
        self._execute("INSERT INTO plugin_deployments (id, plugin_id, build_id, deploy_id, status) "
                      "VALUES ('d1', 'p1', 'bk1', 'dep1', 'up')")
        self._execute("INSERT INTO workflows (id, name, version, repository_url, source_type) "
                      "VALUES ('w1', 'n', '1', 'r', 'github')")
        self._execute("INSERT INTO measurements (id, name, status) VALUES ('m1', 'n', 'completed')")

        init_db(bind=self.engine)

        self.assertEqual(schema_snapshot(self.engine), fresh)
        self.assertEqual(self._applied(), ["0001"])
        self.assertEqual(self._execute("SELECT deploy_id FROM plugin_deployments").scalars().all(), ["dep1"])
        # Untyped rows predate the SDS marker: not SDS.
        self.assertEqual(self._execute("SELECT is_sds FROM workflows").scalars().all(), [False])
        # Tables the models no longer define are left alone.
        self.assertEqual(self._execute("SELECT id FROM measurements").scalars().all(), ["m1"])

    def test_workflows_typed_before_is_sds_are_marked_sds_once(self):
        # From 2026-10-02 until is_sds existed, a set workflow_type marked an SDS package.
        self._load_2026_09_28()
        self._execute("ALTER TABLE workflows ADD COLUMN workflow_type VARCHAR")
        self._execute("INSERT INTO workflows (id, name, version, repository_url, source_type, workflow_type) "
                      "VALUES ('sds', 'n', '1', 'r', 'github', 'script'), ('root', 'n', '1', 'r', 'github', NULL)")

        init_db(bind=self.engine)
        self._execute("UPDATE workflows SET workflow_type = 'gui' WHERE id = 'root'")
        init_db(bind=self.engine)

        self.assertEqual(dict(self._execute("SELECT id, is_sds FROM workflows").all()), {"sds": True, "root": False})


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
