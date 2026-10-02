"""workflows.is_sds is added once and backfilled from workflow_type (until 2026-10-02 a set type meant SDS).

Run from `backend/`:
    python -m unittest tests.test_workflow_is_sds_migration
"""
import tempfile
import unittest
from pathlib import Path

import tests.tool_app  # noqa: F401,I001  (sets DATABASE_PATH first)
from sqlalchemy import create_engine, text

from app.database.database import migrate_workflow_is_sds
from app.models.db_model import Base


def _engine():
    return create_engine(f"sqlite:///{Path(tempfile.mkdtemp()) / 'portal.db'}")


def _is_sds(engine):
    with engine.connect() as conn:
        return dict(conn.execute(text("SELECT id, is_sds FROM workflows ORDER BY id")).all())


class WorkflowIsSdsMigrationTest(unittest.TestCase):
    def setUp(self):
        self.engine = _engine()
        with self.engine.begin() as conn:  # the workflows table as it was before is_sds
            conn.execute(text("CREATE TABLE workflows (id VARCHAR PRIMARY KEY, workflow_type VARCHAR)"))
            conn.execute(text("INSERT INTO workflows VALUES ('sds', 'script'), ('root', NULL)"))

    def test_the_first_run_marks_typed_workflows_as_sds(self):
        migrate_workflow_is_sds(self.engine)
        self.assertEqual(_is_sds(self.engine), {"root": False, "sds": True})

    def test_a_later_run_leaves_rows_alone(self):
        migrate_workflow_is_sds(self.engine)
        with self.engine.begin() as conn:  # a root-.cwl workflow registered after the change has a type
            conn.execute(text("UPDATE workflows SET workflow_type = 'gui' WHERE id = 'root'"))
        migrate_workflow_is_sds(self.engine)
        self.assertEqual(_is_sds(self.engine), {"root": False, "sds": True})

    def test_a_fresh_database_already_has_the_column(self):
        engine = _engine()
        Base.metadata.create_all(engine)
        migrate_workflow_is_sds(engine)  # nothing to do
        with engine.connect() as conn:
            self.assertEqual(conn.execute(text("SELECT COUNT(is_sds) FROM workflows")).scalar(), 0)


if __name__ == "__main__":
    unittest.main()
