"""
Tests for the SQLite -> Postgres data-migration CLI. The copy logic is plain
SQLAlchemy Core, so these run SQLite -> SQLite (target with FK enforcement on);
the Postgres run lives in tests.test_postgres_integration.

Run from `backend/`:
    python -m unittest tests.test_migrate_sqlite_to_postgres
"""
import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_PATH", str(BACKEND_ROOT / "tmp" / "test_plugin_registry.db"))
(BACKEND_ROOT / "tmp").mkdir(parents=True, exist_ok=True)

from sqlalchemy import create_engine, event, select, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.cli.migrate_sqlite_to_postgres import MigrationError, migrate  # noqa: E402
from app.models.db_model import (  # noqa: E402
    Base, Measurement, MeasurementAnnotation, Plugin, PluginAnnotation, PluginBuild,
    PluginDeployment, Workflow, WorkflowAnnotation, WorkflowBuild,
)

T0 = datetime(2025, 1, 2, 3, 4, 5, 678901)


def make_source(path: Path):
    """A SQLite file shaped like production: no FK enforcement, one row in every table."""
    engine = create_engine(f"sqlite:///{path}")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    common = dict(created_at=T0, updated_at=T0)
    with_meta = Plugin(id="p1", uuid="u-p1", name="p1", version="1", repository_url="r", label="GUI",
                       has_backend=True, frontend_folder="fe", frontend_build_command="b",
                       plugin_metadata={"k": [1, "two"]}, **common)
    no_meta = Plugin(id="p2", name="p2", version="1", repository_url="r", label="Script",
                     has_backend=False, frontend_folder="fe", frontend_build_command="b", **common)
    wf = Workflow(id="w1", name="w1", version="1", repository_url="r", plugins=[with_meta], **common)
    s.add_all([
        with_meta, no_meta, wf,
        PluginBuild(id="pb1", plugin_id="p1", build_id="bk1", status="completed", **common),
        PluginDeployment(id="pd1", plugin_id="p1", build_id="bk1", deploy_id="d1", up=True, **common),
        PluginAnnotation(id="pa1", plugin_id="p1", annotation_id="a1", fhir_note="f", **common),
        WorkflowBuild(id="wb1", workflow_id="w1", build_id="wbk1", **common),
        WorkflowAnnotation(id="wa1", workflow_id="w1", annotation_id="a2", **common),
        Measurement(id="m1", name="m1", status="completed", expose_name="e1", **common),
        MeasurementAnnotation(id="ma1", measurement_id="m1", annotation_id="a3",
                              descriptions={"dataset": {"name": "x"}, "patients": []}, **common),
    ])
    s.commit()
    s.close()
    return engine


def make_fk_target():
    engine = create_engine("sqlite://")

    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


def rows(engine, table):
    with engine.connect() as conn:
        return sorted(tuple(r) for r in conn.execute(select(table)))


def total_rows(engine):
    return sum(len(rows(engine, t)) for t in Base.metadata.sorted_tables)


class MigrateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.source = make_source(Path(self.tmp.name) / "plugin_registry.db")
        self.target = make_fk_target()

    def tearDown(self):
        self.source.dispose()
        self.target.dispose()
        self.tmp.cleanup()

    def test_copies_every_table_unchanged(self):
        counts, stripped = migrate(self.source, self.target)
        self.assertEqual(stripped, {})
        self.assertEqual(set(counts), set(Base.metadata.tables))
        for table in Base.metadata.sorted_tables:
            self.assertEqual(rows(self.target, table), rows(self.source, table), table.name)
            self.assertEqual(counts[table.name], len(rows(self.source, table)))
            self.assertGreater(counts[table.name], 0, f"fixture should cover {table.name}")

    def test_sql_null_json_stays_sql_null(self):
        migrate(self.source, self.target)
        with self.target.connect() as conn:
            is_null = conn.execute(text("SELECT plugin_metadata IS NULL FROM plugins WHERE id = 'p2'")).scalar_one()
        self.assertTrue(is_null)

    def test_refuses_non_empty_target(self):
        migrate(self.source, self.target)
        before = total_rows(self.target)
        with self.assertRaisesRegex(MigrationError, "not empty"):
            migrate(self.source, self.target)
        self.assertEqual(total_rows(self.target), before)

    def test_orphan_row_aborts_and_rolls_back(self):
        with self.source.begin() as conn:
            conn.execute(text("INSERT INTO plugin_builds (id, plugin_id, build_id, status) "
                              "VALUES ('orphan', 'no-such-plugin', 'bk-orphan', 'pending')"))
        with self.assertRaises(MigrationError):
            migrate(self.source, self.target)
        self.assertEqual(total_rows(self.target), 0)

    def test_dry_run_writes_nothing(self):
        counts, _ = migrate(self.source, self.target, dry_run=True)
        self.assertEqual(counts["plugins"], 2)
        self.assertEqual(total_rows(self.target), 0)

    def test_source_missing_newer_column(self):
        with self.source.begin() as conn:
            conn.execute(text("ALTER TABLE plugins DROP COLUMN local_archive_path"))
        counts, _ = migrate(self.source, self.target)
        self.assertEqual(counts["plugins"], 2)

    def test_nul_characters_are_stripped_and_reported(self):
        # Postgres text cannot hold NUL; old build logs captured from vite output can contain it.
        with self.source.begin() as conn:
            conn.execute(text("UPDATE plugin_builds SET build_logs = 'a' || char(0) || 'b' || char(0) WHERE id = 'pb1'"))
        _, stripped = migrate(self.source, self.target)
        self.assertEqual(stripped, {"plugin_builds.build_logs": 1})
        with self.target.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT build_logs FROM plugin_builds WHERE id = 'pb1'")).scalar_one(), "ab")


if __name__ == "__main__":
    unittest.main()
