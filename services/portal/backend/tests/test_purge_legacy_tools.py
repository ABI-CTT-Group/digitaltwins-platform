"""One-off purge of portal tool data from before the platform handoff: legacy
``tools/<expose_name>/`` objects, ``sparc-tool-`` ActivityDefinitions and the
placeholder uuids on plugin rows (the rows stay; re-approving migrates them).

Run from `backend/`:
    python -m unittest tests.test_purge_legacy_tools
"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))
os.environ.setdefault("DATABASE_PATH", str(BACKEND_ROOT / "tmp" / "test_plugin_registry.db"))
(BACKEND_ROOT / "tmp").mkdir(parents=True, exist_ok=True)

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.cli.purge_legacy_tools import purge  # noqa: E402
from app.models.db_model import Base, Plugin  # noqa: E402

DATASET = "1f0c6a2e-8d4b-11f0-9a5e-0242ac120002"
LEGACY = "sparc-tool-$0b9c1e44-2f65-4a3e-9d3c-5e6f7a8b9c0d"


class FakeMinio:
    def __init__(self, objects):
        self.objects = set(objects)

    def list_objects(self, prefix=""):
        return [{"Key": k} for k in sorted(self.objects) if k.startswith(prefix)]

    def delete_object(self, object_name):
        self.objects.remove(object_name)


class FakeFhir:
    def __init__(self, identifiers):
        self.store = {f"ActivityDefinition/{n}": i for n, i in enumerate(identifiers)}

    def search(self, resource_type, identifier):
        return [{"resourceType": resource_type, "id": ref.split("/")[1]}
                for ref, i in self.store.items() if ref.startswith(resource_type) and i == identifier]

    def delete(self, reference):
        self.store.pop(reference)


class PurgeLegacyToolsTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(f"sqlite:///{tempfile.mkdtemp()}/p.db")
        Base.metadata.create_all(self.engine)
        with sessionmaker(bind=self.engine)() as db:
            for name, uuid in (("Old", LEGACY), ("New", DATASET), ("Draft", None)):
                db.add(Plugin(name=name, uuid=uuid, version="1", repository_url="r", label="Script",
                              has_backend=False, frontend_folder="", frontend_build_command=""))
            db.commit()
        self.minio = FakeMinio({"oldtool_ab12cd34/primary/tool.cwl", "oldtool_ab12cd34/code/x.py",
                                f"{DATASET}/primary/tool_new.cwl"})
        self.fhir = FakeFhir([LEGACY, DATASET])

    def _uuids(self):
        with self.engine.connect() as conn:
            return dict(conn.execute(text("SELECT name, uuid FROM plugins")).all())

    def test_legacy_objects_resources_and_placeholders_are_removed(self):
        report = purge(self.engine, self.minio, self.fhir)

        self.assertEqual(report, {"minio_objects": 2, "fhir_resources": 1, "placeholder_uuids": 1})
        self.assertEqual(self.minio.objects, {f"{DATASET}/primary/tool_new.cwl"})
        self.assertEqual(list(self.fhir.store.values()), [DATASET])
        self.assertEqual(self._uuids(), {"Old": None, "New": DATASET, "Draft": None})

    def test_dry_run_changes_nothing(self):
        report = purge(self.engine, self.minio, self.fhir, dry_run=True)

        self.assertEqual(report, {"minio_objects": 2, "fhir_resources": 1, "placeholder_uuids": 1})
        self.assertEqual(len(self.minio.objects), 3)
        self.assertEqual(len(self.fhir.store), 2)
        self.assertEqual(self._uuids()["Old"], LEGACY)

    def test_rerunning_finds_nothing(self):
        purge(self.engine, self.minio, self.fhir)
        self.assertEqual(purge(self.engine, self.minio, self.fhir),
                         {"minio_objects": 0, "fhir_resources": 0, "placeholder_uuids": 0})


if __name__ == "__main__":
    unittest.main()
