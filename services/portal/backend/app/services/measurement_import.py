"""CLI dataset-import helpers (plan 11).

Three concerns, deliberately free of heavy deps (boto3 / fhir_cda) at module
scope so validation + id-reset are unit-testable without the Docker stack:

- ``validate_fhir_matches_dataset`` — reject a fhir.json that doesn't structurally
  match the dataset on disk (e.g. someone dropped an unrelated file).
- ``reset_placeholder_ids`` — stamp folder-name placeholder uuids and clear url
  fields, so the approval pipeline recomputes the real URLs.
- ``build_descriptions_from_dataset`` — auto pre-annotation when no fhir.json is
  present. This one needs the fhir-cda-backed builders, so it imports them
  lazily (Docker-only) to keep the module importable for the unit tests.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, List

from app.services.measurement_classifier import classify_sample
from app.utils.measurement_mocks import (
    folder_dataset_uuid,
    folder_endpoint_uuid,
    folder_patient_uuid,
    folder_resource_uuid,
)

# fhir-cda kind -> descriptions tree key
_KIND_TO_KEY = {
    "Observation": "observations",
    "ImagingStudy": "imagingStudy",
    "DocumentReference": "documentReference",
}


class DatasetMismatchError(ValueError):
    """The provided fhir.json doesn't structurally match the dataset on disk."""


def classify_dataset_structure(dataset_path: Path) -> Dict[str, Dict[str, str]]:
    """Walk ``primary/<sub>/<sam>`` and return ``{patient: {sample: kind}}`` using
    the same ``classify_sample`` the pipeline uses. Unclassifiable (empty) samples
    are omitted."""
    primary = dataset_path / "primary"
    out: Dict[str, Dict[str, str]] = {}
    if not primary.is_dir():
        return out
    for patient_dir in sorted(p for p in primary.iterdir() if p.is_dir()):
        samples: Dict[str, str] = {}
        for sample_dir in sorted(s for s in patient_dir.iterdir() if s.is_dir()):
            result = classify_sample(sample_dir)
            if result is not None:
                samples[sample_dir.name] = result.kind
        out[patient_dir.name] = samples
    return out


def _samples_by_kind(samples: Dict[str, str]) -> Dict[str, List[str]]:
    """Group ``{sample: kind}`` into ``{kind: [sample, ...]}`` (samples sorted)."""
    grouped: Dict[str, List[str]] = {"Observation": [], "ImagingStudy": [], "DocumentReference": []}
    for sample, kind in sorted(samples.items()):
        if kind in grouped:
            grouped[kind].append(sample)
    return grouped


def validate_fhir_matches_dataset(descriptions: Dict[str, Any], dataset_path: Path) -> None:
    """Assert the provided descriptions structurally match the dataset, rejecting
    an unrelated fhir.json. Raises :class:`DatasetMismatchError` on any mismatch.

    Checks:
      1. every ``patient.name`` is a real ``sub`` folder, and every classified
         ``sub`` appears in the fhir.json (empty-annotation patients allowed);
      2. per patient, the fhir.json count of each resource type equals the
         classify count of that kind;
      3. every ``imagingStudy.series[].name`` is a real imaging sample folder.
    """
    structure = classify_dataset_structure(dataset_path)
    fhir_patients = {p.get("name"): p for p in descriptions.get("patients", []) or []}

    for name in fhir_patients:
        if name not in structure:
            raise DatasetMismatchError(
                f"fhir.json references patient '{name}' that is not in the dataset's primary/."
            )
    for sub in structure:
        if sub not in fhir_patients:
            raise DatasetMismatchError(
                f"dataset patient folder '{sub}' is missing from the fhir.json."
            )

    for name, patient in fhir_patients.items():
        grouped = _samples_by_kind(structure[name])
        fhir_counts = {
            "Observation": len(patient.get("observations", []) or []),
            "ImagingStudy": len(patient.get("imagingStudy", []) or []),
            "DocumentReference": len(patient.get("documentReference", []) or []),
        }
        for kind in _KIND_TO_KEY:
            if fhir_counts[kind] != len(grouped[kind]):
                raise DatasetMismatchError(
                    f"patient '{name}': fhir.json has {fhir_counts[kind]} {kind} but the dataset "
                    f"has {len(grouped[kind])} {kind} sample(s)."
                )
        imaging_samples = set(grouped["ImagingStudy"])
        for img in patient.get("imagingStudy", []) or []:
            for series in img.get("series", []) or []:
                sname = series.get("name")
                if sname not in imaging_samples:
                    raise DatasetMismatchError(
                        f"patient '{name}': imagingStudy series '{sname}' is not an imaging "
                        f"sample folder in the dataset."
                    )


def reset_placeholder_ids(descriptions: Dict[str, Any], dataset_path: Path) -> Dict[str, Any]:
    """Return a deep copy with every uuid stamped to the folder-name placeholder
    scheme and every url cleared, so the approval pipeline's finalize stage
    recomputes the real endpoint/attachment URLs.

    Sample resolution per resource:
      - imagingStudy -> ``series[0].name``;
      - observation / documentReference -> matched to the classified sample
        folders of that kind by sorted order within the patient.
    """
    out = copy.deepcopy(descriptions)
    structure = classify_dataset_structure(dataset_path)

    dataset = out.setdefault("dataset", {})
    dataset["uuid"] = folder_dataset_uuid(dataset.get("name") or "")

    for patient in out.get("patients", []) or []:
        pname = patient.get("name") or ""
        patient["uuid"] = folder_patient_uuid(pname)
        grouped = _samples_by_kind(structure.get(pname, {}))

        for i, obs in enumerate(patient.get("observations", []) or []):
            if i < len(grouped["Observation"]):
                obs["uuid"] = folder_resource_uuid(pname, grouped["Observation"][i])

        for i, doc in enumerate(patient.get("documentReference", []) or []):
            if i < len(grouped["DocumentReference"]):
                doc["uuid"] = folder_resource_uuid(pname, grouped["DocumentReference"][i])
            for attach in doc.get("attachments", []) or []:
                attach["url"] = ""

        for img in patient.get("imagingStudy", []) or []:
            series_list = img.get("series", []) or []
            sample = series_list[0].get("name") if series_list else None
            if sample:
                img["uuid"] = folder_resource_uuid(pname, sample)
            img["endpointUrl"] = ""
            for series in series_list:
                sname = series.get("name")
                if sname:
                    series["endpointUuid"] = folder_endpoint_uuid(pname, sname)
                series["endpointUrl"] = ""

    return out


def build_descriptions_from_dataset(dataset_path: Path, dataset_name: str) -> Dict[str, Any]:
    """Auto pre-annotation: classify every sample folder and build the prefilled
    descriptions tree (same output as the GUI ``/tree``), for the no-fhir.json
    import path.

    Imports the fhir-cda-backed builders lazily so this module stays importable
    (for unit tests) without the Docker-only deps.
    """
    from app.router.measurement_router import (  # lazy: pulls fhir-cda / minio at import
        _document_reference_description_from_classify,
        _imaging_study_description_from_classify,
        _observation_description_from_classify,
    )

    primary = dataset_path / "primary"
    descriptions: Dict[str, Any] = {
        "dataset": {"uuid": folder_dataset_uuid(dataset_name), "name": dataset_name},
        "patients": [],
    }
    if not primary.is_dir():
        return descriptions

    for patient_dir in sorted(p for p in primary.iterdir() if p.is_dir()):
        pname = patient_dir.name
        entry: Dict[str, Any] = {
            "uuid": folder_patient_uuid(pname),
            "name": pname,
            "observations": [],
            "imagingStudy": [],
            "documentReference": [],
        }
        for sample_dir in sorted(s for s in patient_dir.iterdir() if s.is_dir()):
            sname = sample_dir.name
            classify = classify_sample(sample_dir)
            if classify is None:
                continue
            if classify.kind == "Observation":
                entry["observations"].append(
                    _observation_description_from_classify(classify, pname, sname)
                )
            elif classify.kind == "ImagingStudy":
                entry["imagingStudy"].append(
                    _imaging_study_description_from_classify(classify, pname, sname, sample_dir)
                )
            else:
                entry["documentReference"].append(
                    _document_reference_description_from_classify(classify, pname, sname, sample_dir)
                )
        descriptions["patients"].append(entry)

    return descriptions
