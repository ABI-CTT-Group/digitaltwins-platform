"""
Tests for the one-off purge of legacy portal measurements (their MinIO prefixes,
HAPI FHIR resources, staged dataset dirs and the two portal tables). Measurement
ingest moved to digitaltwins-api; these rows are discarded, not migrated.

Run from `backend/`:
    python -m unittest tests.test_purge_legacy_measurements
"""
import json
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

from sqlalchemy import create_engine, inspect, text  # noqa: E402

from app.cli.purge_legacy_measurements import purge  # noqa: E402


class FakeMinio:
    """Same surface as app.client.minio.MinioClient. Bulk delete_objects is
    deliberately absent: MinIO rejects multi-object delete without Content-MD5,
    which boto3 >= 1.36 no longer sends, so the purge must delete one by one."""

    def __init__(self, objects):
        self.objects = set(objects)

    def list_objects(self, prefix=""):
        return [{"Key": k} for k in sorted(self.objects) if k.startswith(prefix)]

    def delete_object(self, object_name):
        self.objects.remove(object_name)


class FakeFhir:
    """FHIR REST surface (search / read / delete) over an in-memory graph shaped
    like digitaltwins-on-fhir's: only Compositions carry the dataset identifier;
    Patients carry the patient uuid and point-at-Patient resources hang off them.
    Delete refuses a resource that is still referenced (referential integrity)."""

    def __init__(self):
        self.store = {}

    def add(self, ref, identifier, **fields):
        t, i = ref.split("/")
        self.store[ref] = {"resourceType": t, "id": i, "identifier": [{"value": identifier}], **fields}

    def search(self, resource_type, **params):
        (param, value), = params.items()
        return [r for ref, r in self.store.items() if ref.startswith(resource_type + "/") and (
            r["identifier"][0]["value"] == value if param == "identifier"
            else (r.get(param) or {}).get("reference") == value)]

    def read(self, reference):
        return self.store.get(reference)

    def delete(self, reference):
        if any(reference in json.dumps(r) for ref, r in self.store.items() if ref != reference):
            raise RuntimeError(f"{reference} is still referenced")
        self.store.pop(reference, None)


def legacy_graph(fhir, dataset, patient, n):
    """One legacy patient graph: Patient, Consent, ResearchSubject, ImagingStudy + Endpoint, Composition."""
    fhir.add(f"Patient/{n}", patient)
    fhir.add(f"Consent/{n}", f"{dataset}_{patient}_ResearchSubject_Consent", patient={"reference": f"Patient/{n}"})
    fhir.add(f"ResearchSubject/{n}", f"{dataset}_{patient}_ResearchSubject",
             individual={"reference": f"Patient/{n}"}, consent={"reference": f"Consent/{n}"})
    fhir.add(f"Endpoint/{n}", f"{dataset}_{patient}_Endpoint")
    fhir.add(f"ImagingStudy/{n}", f"{patient}/sam-1", subject={"reference": f"Patient/{n}"},
             endpoint=[{"reference": f"Endpoint/{n}"}])
    fhir.add(f"Composition/{n}", dataset, subject={"reference": f"ResearchSubject/{n}"},
             section=[{"entry": [{"reference": f"ImagingStudy/{n}"}]}])


class PurgeLegacyMeasurementsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)
        self.staged = tmp / "datasets_measurement" / "ds-a-1234abcd"
        self.staged.mkdir(parents=True)
        self.engine = create_engine(f"sqlite:///{tmp / 'portal.db'}")
        with self.engine.begin() as c:
            c.execute(text("CREATE TABLE measurements (id TEXT PRIMARY KEY, uuid TEXT, name TEXT, "
                           "expose_name TEXT, dataset_path TEXT)"))
            c.execute(text("CREATE TABLE measurement_annotations (id TEXT PRIMARY KEY, measurement_id TEXT, "
                           "descriptions TEXT)"))
            c.execute(text("INSERT INTO measurements VALUES "
                           "('m1', 'ds-a', 'a', 'ds-a-1234abcd', :path), ('m2', NULL, 'b', NULL, NULL)"),
                      {"path": str(self.staged)})
            c.execute(text("INSERT INTO measurement_annotations VALUES ('a1', 'm1', :d)"),
                      {"d": json.dumps({"dataset": {"uuid": "ds-a"}, "patients": [{"uuid": "sub-1"}, {"uuid": "sub-2"}]})})
        self.minio = FakeMinio(["ds-a-1234abcd/primary/sub-1/x.dcm", "ds-a-1234abcd/fhir.json", "other/keep.txt"])
        self.fhir = FakeFhir()
        legacy_graph(self.fhir, "ds-a", "sub-1", 1)
        legacy_graph(self.fhir, "ds-a", "sub-2", 2)
        self.fhir.store.pop("Composition/2")  # a graph whose Composition is already gone
        self.fhir.add("Patient/9", "unrelated")

    def tearDown(self):
        self.engine.dispose()
        self._tmp.cleanup()

    def _purge(self, dry_run):
        return purge(self.engine, self.minio, self.fhir, dry_run=dry_run)

    def test_dry_run_reports_without_changing_anything(self):
        report = self._purge(dry_run=True)

        self.assertEqual(report, {"measurements": 2, "minio_objects": 2, "fhir_resources": 11,
                                  "staged_dirs": 1, "dropped_tables": []})
        self.assertEqual(len(self.minio.objects), 3)
        self.assertEqual(len(self.fhir.store), 12)
        self.assertTrue(self.staged.exists())
        self.assertIn("measurements", inspect(self.engine).get_table_names())

    def test_purge_removes_objects_resources_dirs_and_tables(self):
        report = self._purge(dry_run=False)

        self.assertEqual(report["dropped_tables"], ["measurement_annotations", "measurements"])
        self.assertEqual(self.minio.objects, {"other/keep.txt"})
        self.assertEqual(list(self.fhir.store), ["Patient/9"])  # the whole legacy graph, nothing else
        self.assertFalse(self.staged.exists())
        self.assertEqual(
            [t for t in inspect(self.engine).get_table_names() if t.startswith("measurement")], [])

    def test_rerun_after_purge_is_a_noop(self):
        self._purge(dry_run=False)

        self.assertEqual(self._purge(dry_run=False), {"measurements": 0, "minio_objects": 0,
                                                      "fhir_resources": 0, "staged_dirs": 0,
                                                      "dropped_tables": []})


if __name__ == "__main__":
    unittest.main()
