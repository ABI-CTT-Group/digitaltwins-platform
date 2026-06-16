"""Shared measurement approval pipeline (submit stages 2–6).

Used by both the GUI ``/submit`` / ``/retry-fhir`` endpoints and the CLI dataset
import. Service-layer: on a stage failure it records the failure on the row
(stage / message / terminal status) and raises :class:`ApprovalError` — callers
map that to their own surface (HTTP 500 for the GUI, a non-zero exit for the CLI).

The caller is responsible for stage 1 (staging existence checks), for setting
``status = UPLOADING`` and ``measurement.uuid`` before calling, and for any
post-success cleanup (e.g. CLI local-dataset deletion).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.builder.logger import get_logger
from app.models.db_model import Measurement, MeasurementAnnotation, MeasurementStatus
from app.services.measurement_service import (
    apply_descriptions,
    compute_endpoint_urls,
    delete_hapi_fhir_resources,
    push_to_hapi_fhir,
    read_fhir_json,
    rollback_minio,
    upload_fhir_json,
    upload_full_dataset,
)
from app.services.measurements_fhir_adapter import MeasurementsFhirAnnotator

logger = get_logger(__name__)


class ApprovalError(Exception):
    """A stage in the approval pipeline failed. The measurement row has already
    been marked (failure_stage / failure_message / terminal status) before this
    is raised, so callers only need to surface ``stage`` / ``message``."""

    def __init__(self, stage: str, message: str):
        self.stage = stage
        self.message = message
        super().__init__(f"{stage}: {message}")


def set_stage_failure(
    measurement: Measurement,
    stage: str,
    err: Exception,
    *,
    db,
    terminal_status: MeasurementStatus,
) -> None:
    """Record a stage failure on the measurement row + commit so polling sees it.

    ``terminal_status``:
      - SUBMIT_FAILED for stages 1-3 (staging / fhir_build / upload), MinIO rolled back
      - FHIR_FAILED for stages 4-6 (finalize / fhir_push), MinIO retained
    """
    measurement.failure_stage = stage
    measurement.failure_message = str(err) or err.__class__.__name__
    measurement.status = terminal_status.value
    measurement.updated_at = datetime.utcnow()
    db.commit()
    logger.error(
        f"Measurement {measurement.id} stage '{stage}' failed "
        f"({terminal_status.value}): {measurement.failure_message}"
    )


async def run_measurement_approval(
    measurement: Measurement,
    annotation: MeasurementAnnotation,
    *,
    db,
    minio,
    adapter,
    fhir_async_client,
    update_mode: bool = False,
) -> None:
    """Run approval stages 2–6 on ``measurement`` (dataset must be on disk;
    ``annotation.descriptions`` must be final-shaped camelCase).

    - ``update_mode=False`` (full submit): fhir_build → upload full dataset →
      finalize (compute URLs, rebuild fhir.json, persist descriptions, re-upload
      fhir.json) → push to hapi-fhir.
    - ``update_mode=True`` (retry-fhir): skip fhir_build + dataset upload (already
      on MinIO); finalize uses the annotator in ``update`` mode; then push.

    On success flips the row to COMPLETED. On failure: records the failure and
    raises :class:`ApprovalError`.
    """
    descriptions = annotation.descriptions
    dataset_path = Path(measurement.dataset_path) if measurement.dataset_path else None
    expose = measurement.expose_name

    if not update_mode:
        # --- Stage 2: fhir_build (fhir.json with mock endpoint URLs) ----------
        try:
            annotator = MeasurementsFhirAnnotator(dataset_path)
            apply_descriptions(annotator, descriptions, dataset_path)
            annotator.save()
        except Exception as e:
            set_stage_failure(measurement, "fhir_build", e, db=db,
                              terminal_status=MeasurementStatus.SUBMIT_FAILED)
            raise ApprovalError("fhir_build", measurement.failure_message)

        # --- Stage 3: upload full dataset to MinIO ---------------------------
        try:
            measurement.s3_path = upload_full_dataset(dataset_path, expose, minio)
            db.commit()
        except Exception as e:
            set_stage_failure(measurement, "upload", e, db=db,
                              terminal_status=MeasurementStatus.SUBMIT_FAILED)
            # Best-effort rollback so a retry doesn't see half-uploaded blobs.
            rollback_minio(expose, minio)
            raise ApprovalError("upload", measurement.failure_message)

    # --- Stage 4 (finalize) + Stage 5 (re-upload single fhir.json) -----------
    try:
        updated_descriptions = compute_endpoint_urls(measurement, descriptions)
        # update_mode loads the saved measurements.json; default mode re-walks
        # primary/ from scratch (avoids fhir-cda 1.2.5's no-arg DocumentReference
        # bug when loading documentReference entries).
        annotator2 = (
            MeasurementsFhirAnnotator(dataset_path, mode="update")
            if update_mode
            else MeasurementsFhirAnnotator(dataset_path)
        )
        apply_descriptions(annotator2, updated_descriptions, dataset_path)
        annotator2.save()
        annotation.descriptions = updated_descriptions
        annotation.updated_at = datetime.utcnow()
        upload_fhir_json(dataset_path, expose, minio)
        db.commit()
    except Exception as e:
        set_stage_failure(measurement, "finalize", e, db=db,
                          terminal_status=MeasurementStatus.FHIR_FAILED)
        # Don't roll back MinIO — partial upload + mock-URL fhir.json is still
        # recoverable; retry-fhir overwrites the fhir.json.
        raise ApprovalError("finalize", measurement.failure_message)

    # --- Stage 6: fhir_push --------------------------------------------------
    try:
        fhir_dict = read_fhir_json(dataset_path)
        # Defensive cleanup: drop any half-baked resources a prior failed push
        # left under this dataset's identifier before re-pushing.
        await delete_hapi_fhir_resources(measurement.uuid, fhir_async_client)
        await push_to_hapi_fhir(fhir_dict, adapter)
    except Exception as e:
        set_stage_failure(measurement, "fhir_push", e, db=db,
                          terminal_status=MeasurementStatus.FHIR_FAILED)
        raise ApprovalError("fhir_push", measurement.failure_message)

    measurement.status = MeasurementStatus.COMPLETED.value
    measurement.failure_stage = None
    measurement.failure_message = None
    measurement.updated_at = datetime.utcnow()
    db.commit()
    logger.info(f"Measurement {measurement.id} approval complete (expose={expose})")
