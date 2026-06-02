"""Measurements upload router (plan 07).

Skeleton only — every endpoint returns 501 until phases 2-3 fill it in:
  - Phase 2: /upload-source, /check-name, /create, /tree, validate_sparc_structure
  - Phase 3: /annotation, /submit, /retry-fhir, /get, /list, /delete, /metadata, /stream

Bucket: ``measurements`` (private, streamed through this backend; never
direct from MinIO). Staging directory: ``DATASET_DIR_MEASUREMENT`` env, default
``/portal_workspace/measurement/<expose_name>``.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.builder.logger import configure_logging, get_logger
from app.client.fhir import get_fhir_adapter, get_fhir_async_client
from app.client.minio import get_minio_client
from app.database.database import get_db
from app.models.db_model import (
    Measurement,
    MeasurementAnnotation,
    MeasurementAnnotationCreate,
    MeasurementAnnotationResponse,
    MeasurementCreate,
    MeasurementResponse,
)

configure_logging()
logger = get_logger(__name__)

router = APIRouter(prefix="/api/measurement", tags=["measurement"])

# Bucket and adapters are initialised at import time so phases 2-3 can use them
# directly. Same pattern as workflow_router.
minio = get_minio_client("measurements")
adapter = get_fhir_adapter()
fhir_async_client = get_fhir_async_client()

# Staging root for measurement datasets. Lives on the named volume
# ``portal_workspace`` inside the backend container — see docker-compose.yml.
# A typical layout after /create is:
#   /portal_workspace/measurement/<expose_name>/
#     ├─ dataset_description.xlsx
#     └─ primary/sub-XXX/sam-YYY/<files>
_DATASET_DIR = Path(os.getenv("DATASET_DIR_MEASUREMENT", "/portal_workspace/measurement"))

# Reuse the workflow builder's tmp dir for upload staging — extract_uploaded_archive
# writes to tmp/upload_<id>/ regardless of the source type, and orphan cleanup in
# main.py already scans tmp/ for stale uploads.
from app.builder.build_workflow import WorkflowBuilder

_builder = WorkflowBuilder()
TMP_DIR = _builder.tmp_dir


def _not_implemented(detail: str):
    """Stage 1 placeholder. Phase 2/3 agents replace each call site with the
    real implementation. Returning 501 (not 500) flags this as designed
    behaviour to anyone hitting the endpoint during the build-out window."""
    raise HTTPException(status_code=501, detail=f"{detail} — phase 2/3 placeholder")


# ---------------------------------------------------------------------------
# Source acquisition + create (Phase 2)
# ---------------------------------------------------------------------------

@router.post("/upload-source")
async def upload_measurement_source(file: UploadFile = File(...)):
    """Receive a zip of a SPARC measurements dataset, extract, strict-validate.

    Returns metadata for the dropzone preview:
        {
          "upload_id": str,
          "patients": list[str],
          "samples_per_patient": dict[str, list[str]],
          "file_count_per_sample": dict[str, int],
        }
    """
    _not_implemented("upload-source")


@router.get("/check-name")
async def check_name(name: str, db: Session = Depends(get_db)):
    """Mirror of workflow.check-name but against the measurements table."""
    _not_implemented("check-name")


@router.post("/create", response_model=MeasurementResponse)
async def create_measurement(measurement: MeasurementCreate, db: Session = Depends(get_db)):
    """Materialise a Measurement DB row and move staging from tmp/upload_<id>
    to DATASET_DIR_MEASUREMENT/<expose_name>. status starts at ``pending``."""
    _not_implemented("create")


@router.get("/{measurement_id}/tree")
async def get_measurement_tree(measurement_id: str, db: Session = Depends(get_db)):
    """Auto-classify every sample folder and return a prefilled descriptions
    payload for the annotation step. Phase 2 fills in the classifier."""
    _not_implemented("tree")


# ---------------------------------------------------------------------------
# Annotation + submit (Phase 3)
# ---------------------------------------------------------------------------

@router.post("/{measurement_id}/annotation", response_model=MeasurementAnnotationResponse)
async def upsert_measurement_annotation(
    measurement_id: str,
    annotation: MeasurementAnnotationCreate,
    db: Session = Depends(get_db),
):
    """Insert or update the single MeasurementAnnotation row tied to this
    measurement. Idempotent so /submit retries don't trip the unique constraint."""
    _not_implemented("annotation")


@router.post("/{measurement_id}/submit", response_model=MeasurementResponse)
async def submit_measurement(measurement_id: str, db: Session = Depends(get_db)):
    """Run the 6-stage submit pipeline synchronously:
    staging → fhir_build → upload → finalize → fhir_push.

    Stage failures bucket into one of two terminal states:
      - stages 1-3 fail → status=submit_failed, MinIO rolled back
      - stages 4-6 fail → status=fhir_failed, MinIO retained (retry via /retry-fhir)
    """
    _not_implemented("submit")


@router.post("/{measurement_id}/retry-fhir", response_model=MeasurementResponse)
async def retry_measurement_fhir(measurement_id: str, db: Session = Depends(get_db)):
    """Re-run stages 4-6 only. Rejects when status != fhir_failed (409)."""
    _not_implemented("retry-fhir")


# ---------------------------------------------------------------------------
# Read / list / delete / metadata (Phase 3)
# ---------------------------------------------------------------------------

@router.get("/", response_model=List[MeasurementResponse])
async def list_measurements(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    _not_implemented("list")


@router.get("/metadata")
async def get_metadata_json(db: Session = Depends(get_db)):
    """Components-shape payload (uuid/id/name/path/expose/...) for downstream
    consumers, mirroring workflow_router.get_metadata_json."""
    _not_implemented("metadata")


@router.get("/{measurement_id}", response_model=MeasurementResponse)
async def get_measurement(measurement_id: str, db: Session = Depends(get_db)):
    _not_implemented("get")


@router.delete("/{measurement_id}")
async def delete_measurement(measurement_id: str, db: Session = Depends(get_db)):
    """Cascade-delete: MinIO prefix, dataset_path on disk, DB row (with annotation),
    and hapi-fhir resources searched by identifier."""
    _not_implemented("delete")


@router.get("/{measurement_id}/annotation", response_model=MeasurementAnnotationResponse)
async def get_measurement_annotation(measurement_id: str, db: Session = Depends(get_db)):
    """Return the stored annotation so retries can rehydrate the form."""
    _not_implemented("get-annotation")


# ---------------------------------------------------------------------------
# Stream proxy for the private bucket (Phase 3)
# ---------------------------------------------------------------------------

@router.get("/{expose_name}/primary/{path:path}")
async def stream_measurement_object(expose_name: str, path: str):
    """StreamingResponse mirror of workflow_router.stream_workflow_object —
    needed because ``measurements`` is a private bucket and the nginx
    /tools/ pass-through only handles the public tools bucket."""
    _not_implemented("stream-object")
