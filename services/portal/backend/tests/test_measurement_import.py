"""Unit tests for the CLI dataset-import helpers (validation C + id reset).

These cover the dep-light functions only; ``build_descriptions_from_dataset``
needs the fhir-cda-backed builders and is exercised by the Docker E2E.
"""
from __future__ import annotations

import copy
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

from app.services.measurement_import import (  # noqa: E402
    DatasetMismatchError,
    classify_dataset_structure,
    reset_placeholder_ids,
    validate_fhir_matches_dataset,
)


def _make_dataset(root: Path) -> None:
    """primary/sub-001/{sam-001:.txt obs, sam-002:.dcm imaging, sam-003:.obj doc};
    plus an empty patient sub-002."""
    primary = root / "primary"
    (primary / "sub-001" / "sam-001").mkdir(parents=True)
    (primary / "sub-001" / "sam-001" / "a.txt").write_text("28.5")
    (primary / "sub-001" / "sam-002").mkdir(parents=True)
    (primary / "sub-001" / "sam-002" / "a.dcm").write_bytes(b"\x00")
    (primary / "sub-001" / "sam-003").mkdir(parents=True)
    (primary / "sub-001" / "sam-003" / "a.obj").write_text("o")
    (primary / "sub-002").mkdir(parents=True)


def _matching_descriptions() -> dict:
    return {
        "dataset": {"uuid": "old-ds", "name": "ds"},
        "patients": [
            {
                "uuid": "old-p",
                "name": "sub-001",
                "observations": [
                    {"resourceType": "Observation", "uuid": "old", "value": "28.5",
                     "code": "30525-0", "codeSystem": "http://loinc.org", "display": ""},
                ],
                "imagingStudy": [
                    {"resourceType": "ImagingStudy", "uuid": "old", "endpointUrl": "http://old",
                     "series": [{"uid": "1.2.3", "name": "sam-002", "endpointUuid": "old",
                                 "endpointUrl": "http://old",
                                 "bodySite": {"system": "snomed", "code": "76752008"}}]},
                ],
                "documentReference": [
                    {"resourceType": "DocumentReference", "uuid": "old",
                     "attachments": [{"url": "http://old", "contentType": "model/obj", "title": "a.obj"}]},
                ],
            },
            {"uuid": "old", "name": "sub-002", "observations": [], "imagingStudy": [], "documentReference": []},
        ],
    }


class ClassifyStructureTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _make_dataset(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_structure(self):
        s = classify_dataset_structure(self.root)
        self.assertEqual(s["sub-001"], {"sam-001": "Observation", "sam-002": "ImagingStudy", "sam-003": "DocumentReference"})
        self.assertEqual(s["sub-002"], {})


class ValidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _make_dataset(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_matching_passes(self):
        validate_fhir_matches_dataset(_matching_descriptions(), self.root)  # no raise

    def test_unknown_patient_rejected(self):
        d = _matching_descriptions()
        d["patients"][0]["name"] = "sub-099"
        with self.assertRaises(DatasetMismatchError):
            validate_fhir_matches_dataset(d, self.root)

    def test_missing_dataset_patient_rejected(self):
        d = _matching_descriptions()
        d["patients"] = [d["patients"][0]]  # drop sub-002
        with self.assertRaises(DatasetMismatchError):
            validate_fhir_matches_dataset(d, self.root)

    def test_count_mismatch_rejected(self):
        d = _matching_descriptions()
        d["patients"][0]["observations"].append(
            {"resourceType": "Observation", "uuid": "x", "value": "1"}
        )  # 2 obs vs 1 sample
        with self.assertRaises(DatasetMismatchError):
            validate_fhir_matches_dataset(d, self.root)

    def test_bad_series_name_rejected(self):
        d = _matching_descriptions()
        d["patients"][0]["imagingStudy"][0]["series"][0]["name"] = "sam-999"
        with self.assertRaises(DatasetMismatchError):
            validate_fhir_matches_dataset(d, self.root)


class ResetTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        _make_dataset(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_reset_stamps_folder_uuids_and_clears_urls(self):
        src = _matching_descriptions()
        original = copy.deepcopy(src)
        out = reset_placeholder_ids(src, self.root)

        self.assertEqual(out["dataset"]["uuid"], "ds")
        p = out["patients"][0]
        self.assertEqual(p["uuid"], "sub-001")
        self.assertEqual(p["observations"][0]["uuid"], "sub-001/sam-001")
        self.assertEqual(p["imagingStudy"][0]["uuid"], "sub-001/sam-002")
        self.assertEqual(p["imagingStudy"][0]["endpointUrl"], "")
        series = p["imagingStudy"][0]["series"][0]
        self.assertEqual(series["endpointUuid"], "sub-001/sam-002:endpoint")
        self.assertEqual(series["endpointUrl"], "")
        self.assertEqual(p["documentReference"][0]["uuid"], "sub-001/sam-003")
        self.assertEqual(p["documentReference"][0]["attachments"][0]["url"], "")

        # annotated values are preserved
        self.assertEqual(p["observations"][0]["code"], "30525-0")
        self.assertEqual(series["uid"], "1.2.3")
        self.assertEqual(series["bodySite"]["code"], "76752008")
        self.assertEqual(p["documentReference"][0]["attachments"][0]["title"], "a.obj")
        # input not mutated
        self.assertEqual(src, original)


if __name__ == "__main__":
    unittest.main()
