"""Submit / retry pipeline helpers for the measurements upload flow.

Why this module exists
----------------------
``measurement_router.submit`` orchestrates a 6-stage pipeline (staging →
fhir_build → upload → finalize → fhir_push). Keeping every stage as a
top-level callable here makes each one unit-testable in isolation against
a mock MinIO / fhir client, and lets ``/retry-fhir`` reuse stages 4-6
without duplicating the code.

Key/casing contract
-------------------
The frontend ships descriptions through axios' deepSnakeize interceptor
(``frontend/src/bootstrap/http.ts``), so by the time POST /annotation
hits this backend, the descriptions dict has snake_case keys
(``resource_type``, ``code_system``, ``value_type``, ``imaging_study`` …).
fhir-cda expects camelCase (``resourceType``, ``codeSystem``,
``imagingStudy`` …). We canonicalise via :func:`deep_camelize_keys` on
inbound so DB storage and downstream fhir-cda / digitaltwins-on-fhir calls
all see one shape.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError

from fhir_cda.ehr import (
    DocumentReferenceMeasurement,
)
from fhir_cda.ehr.elements import (
    DocumentAttachment,
    ObservationValue,
    Quantity,
)

from app.builder.logger import get_logger
from app.client.minio import MinioClient
from app.models.db_model import Measurement
from app.services.measurements_fhir_adapter import (
    MeasurementsFhirAnnotator,
    NiiCompatibleImagingStudy,
    SafeObservationMeasurement,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Case conversion (snake_case → camelCase) to undo frontend interceptor
# ---------------------------------------------------------------------------


def _to_camel(s: str) -> str:
    """Mirror of the frontend's ``toCamel`` (http.ts). Leaves leading
    underscores alone where it doesn't matter for our descriptions tree —
    we never put converter-sensitive markers at the top of a key here."""
    if not s or "_" not in s:
        return s
    parts = s.split("_")
    head, *tail = parts
    # If the key starts with an underscore (e.g. "_auto"), keep it. Then
    # camelize the rest as normal.
    if not head and tail:
        # ['', 'auto'] -> '_auto'   ['', 'auto', 'meta'] -> '_autoMeta'
        first, *rest = tail
        return "_" + first + "".join(p[:1].upper() + p[1:] for p in rest)
    return head + "".join(p[:1].upper() + p[1:] for p in tail)


def deep_camelize_keys(obj: Any) -> Any:
    """Recursively rewrite dict keys snake_case → camelCase. Values pass through.
    Mirrors the frontend interceptor's outbound behaviour in reverse, so the
    payload stored in DB and consumed by fhir-cda has consistent casing.
    """
    if isinstance(obj, list):
        return [deep_camelize_keys(x) for x in obj]
    if isinstance(obj, dict):
        return {_to_camel(k): deep_camelize_keys(v) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------
# apply_descriptions: feed the user-edited tree back into the fhir-cda annotator
# ---------------------------------------------------------------------------


def _build_observation_value(desc: Dict[str, Any]) -> Optional[ObservationValue]:
    """Map the frontend's flat ``value`` + ``valueType`` into fhir-cda's nested
    ObservationValue shape. Returns None if neither is set."""
    value_type = desc.get("valueType") or ""
    value = desc.get("value")
    if value in (None, ""):
        return None

    if value_type == "Quantity":
        try:
            numeric = float(value) if not isinstance(value, (int, float)) else value
        except (TypeError, ValueError):
            # Soft-degrade: treat unparseable numerics as String values so the
            # submit doesn't blow up on a single bad row.
            return ObservationValue(value_string=str(value))
        unit = desc.get("unit") or None
        return ObservationValue(
            value_quantity=Quantity(value=numeric, unit=unit if isinstance(unit, str) else None)
        )

    # Default / "String"
    return ObservationValue(value_string=str(value))


def _build_observation_measurement(desc: Dict[str, Any]) -> SafeObservationMeasurement:
    return SafeObservationMeasurement(
        value=_build_observation_value(desc),
        code=desc.get("code") or "",
        code_system=desc.get("codeSystem") or "http://loinc.org",
        unit=desc.get("unit") or None,
        display=desc.get("display") or None,
        uuid=desc.get("uuid") or "",
    )


def _build_imaging_study_measurement(
    desc: Dict[str, Any], dataset_path: Path, patient_name: str
) -> Optional[NiiCompatibleImagingStudy]:
    """Construct a NiiCompatibleImagingStudy from a description entry.

    The samples it points at MUST exist on disk under
    ``<dataset>/primary/<patient>/<series.name>/`` — the ImagingStudyMeasurement
    constructor walks them to populate series metadata. If the descriptions
    were hand-crafted with no series we return None and the caller skips.
    """
    series = desc.get("series") or []
    if not series:
        return None

    sample_details: List[Dict[str, Any]] = []
    for s in series:
        sample_name = s.get("name") or ""
        sample_path = dataset_path / "primary" / patient_name / sample_name
        if not sample_path.exists() or not sample_path.is_dir():
            logger.warning(
                f"ImagingStudy sample path missing on disk: {sample_path}; skipping series."
            )
            continue
        sample_details.append(
            {
                "uuid": s.get("endpointUuid") or "",
                "path": sample_path,
            }
        )

    if not sample_details:
        return None

    return NiiCompatibleImagingStudy(
        uuid=desc.get("uuid") or "",
        sample_details=sample_details,
        endpoint_url=desc.get("endpointUrl") or "",
        description=desc.get("description") or "",
    )


def _build_document_reference_measurement(desc: Dict[str, Any]) -> DocumentReferenceMeasurement:
    attachments: List[DocumentAttachment] = []
    for a in desc.get("attachments", []) or []:
        attachments.append(
            DocumentAttachment(
                title=a.get("title") or "",
                url=a.get("url") or "",
                content_type=a.get("contentType") or "",
            )
        )
    return DocumentReferenceMeasurement(
        attachments=attachments,
        uuid=desc.get("uuid") or "",
        description=desc.get("description") or None,
    )


def apply_descriptions(
    annotator: MeasurementsFhirAnnotator,
    descriptions: Dict[str, Any],
    dataset_path: Path,
) -> None:
    """Replay the user's edited descriptions tree onto a fresh annotator.

    Mutates the annotator in place — caller is expected to call
    ``annotator.save()`` afterwards. ``descriptions`` must already be in
    canonical (camelCase) shape — pass through :func:`deep_camelize_keys`
    first if you got it straight off the wire.
    """
    dataset = descriptions.get("dataset") or {}
    if dataset.get("uuid"):
        annotator.update_dataset("uuid", dataset["uuid"])
    if dataset.get("name"):
        annotator.update_dataset("name", dataset["name"])

    for patient in descriptions.get("patients", []) or []:
        patient_name = patient.get("name") or ""
        if not patient_name:
            continue
        try:
            if patient.get("uuid"):
                annotator.update_patient(patient_name, "uuid", patient["uuid"])
        except ValueError as e:
            # update_patient raises if the patient isn't in the annotator's
            # auto-analysed tree (e.g. a stray entry in descriptions for a
            # folder that was deleted). Skip gracefully.
            logger.warning(f"Skipping unknown patient {patient_name}: {e}")
            continue

        for ob_desc in patient.get("observations", []) or []:
            ob = _build_observation_measurement(ob_desc)
            try:
                annotator.add_measurements([patient_name], [ob])
            except ValueError as e:
                logger.warning(f"Skipping observation for {patient_name}: {e}")

        for img_desc in patient.get("imagingStudy", []) or []:
            img = _build_imaging_study_measurement(img_desc, dataset_path, patient_name)
            if img is None:
                continue
            try:
                annotator.add_measurements([patient_name], [img])
            except ValueError as e:
                logger.warning(f"Skipping imaging study for {patient_name}: {e}")

        for doc_desc in patient.get("documentReference", []) or []:
            doc = _build_document_reference_measurement(doc_desc)
            try:
                annotator.add_measurements([patient_name], [doc])
            except ValueError as e:
                logger.warning(f"Skipping document reference for {patient_name}: {e}")


# ---------------------------------------------------------------------------
# Endpoint URL computation (finalize stage)
# ---------------------------------------------------------------------------


def _portal_base() -> str:
    use_ssl = os.getenv("SSL", "false").lower() == "true"
    host = os.getenv("PORTAL_BACKEND_HOST", "localhost")
    proto = "https" if use_ssl else "http"
    return f"{proto}://{host}"


def compute_endpoint_urls(measurement: Measurement, descriptions: Dict[str, Any]) -> Dict[str, Any]:
    """Walk the descriptions tree and rewrite every ImagingStudy + series
    ``endpointUrl`` to the real portal stream-proxy URL. Returns the mutated
    descriptions dict (also mutated in place — both for caller convenience).
    """
    base = f"{_portal_base()}/api/measurement/{measurement.expose_name}/primary"

    for patient in descriptions.get("patients", []) or []:
        patient_name = patient.get("name") or ""
        for img in patient.get("imagingStudy", []) or []:
            # Top-level endpointUrl points at the patient dir — series-level
            # points at the sample folder. ImagingStudy resources can have a
            # study-level endpoint and per-series endpoints; both must agree
            # with what the FHIR adapter does in _generate_imaging_study.
            img["endpointUrl"] = f"{base}/{patient_name}"
            for series in img.get("series", []) or []:
                sample_name = series.get("name") or ""
                series["endpointUrl"] = f"{base}/{patient_name}/{sample_name}"
        for doc in patient.get("documentReference", []) or []:
            for attach in doc.get("attachments", []) or []:
                fname = attach.get("title") or ""
                # DocumentReference attachment URLs aren't strictly required
                # by the adapter but emit a sensible one anyway so consumers
                # can fetch each file individually.
                if fname:
                    attach["url"] = f"{base}/{patient_name}/{fname}"

    return descriptions


# ---------------------------------------------------------------------------
# MinIO transport
# ---------------------------------------------------------------------------


def upload_full_dataset(dataset_path: Path, expose_name: str, minio: MinioClient) -> str:
    """Upload the whole staged dataset to ``measurements/<expose_name>``.
    Returns the s3:// URI."""
    return minio.upload_directory(str(dataset_path), expose_name)


def upload_fhir_json(dataset_path: Path, expose_name: str, minio: MinioClient) -> str:
    """Overwrite just the fhir.json object on MinIO (called after finalize
    rewrites endpointUrl values)."""
    local = dataset_path / "fhir.json"
    if not local.exists():
        raise FileNotFoundError(f"fhir.json not found at {local}")
    return minio.upload_file(str(local), f"{expose_name}/primary/fhir.json")


def rollback_minio(expose_name: str, minio: MinioClient) -> int:
    """Best-effort cleanup: delete every object under the ``<expose>/`` prefix.
    Returns the number of objects deleted (0 if there was nothing or if the
    delete failed)."""
    try:
        keys = minio.list_objects(prefix=f"{expose_name}/")
        if not keys:
            return 0
        minio.delete_objects(delete_keys=keys)
        return len(keys)
    except Exception as e:
        logger.error(f"rollback_minio failed for {expose_name}: {e}")
        return 0


# ---------------------------------------------------------------------------
# HAPI FHIR push
# ---------------------------------------------------------------------------


async def push_to_hapi_fhir(fhir_json_dict: Dict[str, Any], adapter) -> None:
    """Feed the saved fhir.json into the digitaltwins-on-fhir adapter chain.
    Mirrors workflow_router's approval pattern; v1 skips add_practitioner."""
    client = adapter.digital_twin().measurements()
    client.add_measurements_description(fhir_json_dict)
    await client.generate_resources()


async def delete_hapi_fhir_resources(measurement_uuid: str, fhir_async_client) -> Dict[str, int]:
    """Delete every FHIR resource carrying ``identifier=<measurement_uuid>``.

    Mirrors the workflow delete + approval idempotency pattern. Returns a
    per-type count of resources removed. Best-effort: if hapi-fhir is down
    we log and proceed so the SQL row + MinIO blob can still be reclaimed."""
    removed: Dict[str, int] = {}
    if not measurement_uuid:
        return removed
    types = ("Patient", "Observation", "ImagingStudy", "DocumentReference",
             "Consent", "ResearchSubject", "Composition", "Endpoint")
    for t in types:
        try:
            resources = await fhir_async_client.resources(t).search(
                identifier=measurement_uuid
            ).fetch_all()
        except Exception as e:
            logger.warning(f"delete_hapi_fhir_resources: search {t} failed: {e}")
            continue
        n = 0
        for r in resources:
            try:
                await r.delete()
                n += 1
            except Exception as e:
                logger.warning(f"delete_hapi_fhir_resources: delete {t}/{r.id} failed: {e}")
        if n:
            removed[t] = n
    return removed


# ---------------------------------------------------------------------------
# fhir.json round-trip helpers
# ---------------------------------------------------------------------------


def read_fhir_json(dataset_path: Path) -> Dict[str, Any]:
    """Load the saved fhir.json from a dataset_path. Raises FileNotFoundError
    if the file isn't there (caller should treat as a stage failure)."""
    local = dataset_path / "fhir.json"
    if not local.exists():
        raise FileNotFoundError(f"fhir.json not found at {local}")
    with open(local, "r", encoding="utf-8") as f:
        return json.load(f)


def read_fhir_json_from_minio(expose_name: str, minio) -> Dict[str, Any]:
    """Load the finalized fhir.json straight from the ``measurements`` bucket.

    Lets completed-measurement reads (Preview / Export) work without the local
    dataset on disk — the canonical copy lives in MinIO after the submit
    pipeline's ``upload_fhir_json``. Raises FileNotFoundError when the object is
    absent so callers can fall back to the on-disk copy."""
    key = f"{expose_name}/primary/fhir.json"
    try:
        obj = minio.get_object(key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("404", "NoSuchKey"):
            raise FileNotFoundError(f"fhir.json not found in MinIO at {key}")
        raise
    return json.load(obj["Body"])
