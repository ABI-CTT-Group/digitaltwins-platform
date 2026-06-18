"""Measurements upload router.

Endpoints implemented here:
  - POST /upload-source / GET /check-name / POST /create / GET /{id}/tree
  - POST /{id}/annotation (upsert) / GET /{id}/annotation
  - POST /{id}/submit (6-stage pipeline) / POST /{id}/retry-fhir
  - GET / / GET /{id} / DELETE /{id} / GET /metadata
  - GET /{expose}/primary/{path:path} (stream proxy)

Bucket: ``measurements`` (private, streamed through this backend; never
direct from MinIO). Staging directory: ``DATASET_DIR_MEASUREMENT`` env, default
``./datasets_measurement`` for local dev (Docker compose sets it to
``/portal_workspace/measurement``).
"""
from __future__ import annotations

import json
import mimetypes
import os
import uuid
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.builder.build_workflow import WorkflowBuilder
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
    MeasurementStatus,
)
from app.services.measurement_approval import (
    ApprovalError,
    run_measurement_approval,
    set_stage_failure,
)
from app.services.measurement_chunk_store import (
    PART_SIZE,
    ChunkStoreError,
    MeasurementChunkStore,
)
from app.services.measurement_classifier import (
    _TRUNCATED_MARKER,
    ClassifyResult,
    classify_sample,
)
from app.services.measurement_service import (
    apply_descriptions,
    deep_camelize_keys,
    delete_hapi_fhir_resources,
    read_fhir_json,
    read_fhir_json_from_minio,
)
from app.services.measurements_fhir_adapter import (
    MeasurementsFhirAnnotator,
    NiiCompatibleImagingStudy,
)
from app.utils.builder_utils import (
    extract_uploaded_archive,
    resolve_project_root,
    unique_name,
    validate_sparc_structure,
)
from app.utils.measurement_mocks import (
    folder_dataset_uuid,
    folder_endpoint_uuid,
    folder_patient_uuid,
    folder_resource_uuid,
)
from app.utils.utils import force_rmtree

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
# Layout after /create:
#   <_DATASET_DIR>/<expose_name>/
#     ├─ dataset_description.xlsx
#     └─ primary/sub-XXX/sam-YYY/<files>
_DATASET_DIR = Path(os.getenv("DATASET_DIR_MEASUREMENT", "./datasets_measurement"))
_DATASET_DIR.mkdir(parents=True, exist_ok=True)

def _read_max_upload_mb(default_mb: int = 20480) -> int:
    """Single source of truth for the upload ceiling.

    ``MAX_UPLOAD_MB`` env var feeds all three layers — nginx
    ``client_max_body_size``, this backend's zip-bomb guard, and the value
    surfaced to the frontend via ``GET /api/measurement/config``. Operators
    bump it via ``.env`` + ``docker compose restart`` without recompiling
    anything.

    A non-numeric or non-positive value silently falls back to the default
    so a typo in ``.env`` can't render the upload path 0-byte.
    """
    raw = os.getenv("MAX_UPLOAD_MB", str(default_mb))
    try:
        mb = int(raw)
        return mb if mb > 0 else default_mb
    except (TypeError, ValueError):
        logger.warning(
            f"MAX_UPLOAD_MB={raw!r} is not a positive integer; falling back to {default_mb}"
        )
        return default_mb


_MEASUREMENT_UPLOAD_MAX_MB = _read_max_upload_mb()
_MEASUREMENT_UPLOAD_MAX_BYTES = _MEASUREMENT_UPLOAD_MAX_MB * 1024 * 1024

# Reuse the workflow builder's tmp dir for upload staging — extract_uploaded_archive
# writes to tmp/upload_<id>/ regardless of source type, and orphan cleanup in
# main.py already scans tmp/ for stale uploads.
_builder = WorkflowBuilder()
TMP_DIR = _builder.tmp_dir

# Chunk store for the chunked-upload pipeline. Rooted at the same tmp dir so its
# ``upload_<id>/`` dirs are swept by the existing orphan-cleanup scan.
chunk_store = MeasurementChunkStore(TMP_DIR)


# ---------------------------------------------------------------------------
# Runtime configuration surface — frontend bootstraps from this
# ---------------------------------------------------------------------------


@router.get("/config")
async def get_measurement_config():
    """Runtime config consumed by the frontend Information step.

    Surfacing the upload ceiling here lets operators dial it via
    ``MAX_UPLOAD_MB`` in ``.env`` and pick up the change with a single
    ``docker compose restart`` — no frontend rebuild required. The same
    env var drives nginx ``client_max_body_size`` and the backend
    extract guard, so all three layers stay in sync.
    """
    return {
        "maxUploadBytes": _MEASUREMENT_UPLOAD_MAX_BYTES,
        "maxUploadMb": _MEASUREMENT_UPLOAD_MAX_MB,
    }


# ---------------------------------------------------------------------------
# Source acquisition + create + tree
# ---------------------------------------------------------------------------


def _walk_sparc_meta(project_root: Path) -> Dict[str, Any]:
    """Walk ``primary/`` and produce the metadata payload that the
    Information step's dropzone surfaces back to the user (patient + sample
    counts + per-sample file count).

    Returns a dict with ``patients``, ``samples_per_patient``,
    ``file_count_per_sample``. Keys for file_count_per_sample are
    ``"<patient>/<sample>"`` strings — matches the frontend's
    ``MeasurementSourceMeta.fileCountPerSample`` shape after deepCamelize.
    """
    primary = project_root / "primary"
    patients: List[str] = []
    samples_per_patient: Dict[str, List[str]] = {}
    file_count_per_sample: Dict[str, int] = {}

    for patient_dir in sorted(p for p in primary.iterdir() if p.is_dir()):
        patient_name = patient_dir.name
        patients.append(patient_name)
        sams: List[str] = []
        for sample_dir in sorted(s for s in patient_dir.iterdir() if s.is_dir()):
            sams.append(sample_dir.name)
            key = f"{patient_name}/{sample_dir.name}"
            file_count_per_sample[key] = sum(1 for f in sample_dir.iterdir() if f.is_file())
        samples_per_patient[patient_name] = sams

    return {
        "patients": patients,
        "samples_per_patient": samples_per_patient,
        "file_count_per_sample": file_count_per_sample,
    }


@router.post("/upload-source")
async def upload_measurement_source(file: UploadFile = File(...)):
    """Receive a zip of a SPARC measurements dataset, extract to staging,
    strict-validate, and surface the patient/sample tree to the dropzone.

    Returns:
        ``{ upload_id, patients, samples_per_patient, file_count_per_sample }``
    """
    tmp_zip = TMP_DIR / f"upload_archive_{uuid.uuid4().hex[:8]}.zip"
    try:
        with open(tmp_zip, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)

        try:
            staging = extract_uploaded_archive(
                TMP_DIR, tmp_zip, max_total_bytes=_MEASUREMENT_UPLOAD_MAX_BYTES
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid zip archive")

        ok, message = validate_sparc_structure(staging)
        if not ok:
            force_rmtree(staging)
            raise HTTPException(status_code=400, detail=message)

        project_root = resolve_project_root(staging)
        meta = _walk_sparc_meta(project_root)
        if not meta["patients"]:
            force_rmtree(staging)
            raise HTTPException(
                status_code=400,
                detail="primary/ contains no patient subdirectories.",
            )

        logger.info(
            f"Measurement source uploaded: upload_id={staging.name}, "
            f"patients={len(meta['patients'])}, samples_total={sum(len(s) for s in meta['samples_per_patient'].values())}"
        )

        return {
            "upload_id": staging.name,
            "patients": meta["patients"],
            "samples_per_patient": meta["samples_per_patient"],
            "file_count_per_sample": meta["file_count_per_sample"],
        }
    finally:
        if tmp_zip.exists():
            try:
                tmp_zip.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove temp zip {tmp_zip}: {e}")


@router.get("/check-name")
async def check_name(name: str, db: Session = Depends(get_db)):
    """Mirror of workflow.check-name but against the measurements table."""
    existing = db.query(Measurement).filter(Measurement.name == name).first()  # type: ignore
    if existing:
        raise HTTPException(status_code=400, detail="Measurement with this name already exists")
    return {"available": True, "message": "Name is available"}


@router.post("/create", response_model=MeasurementResponse)
async def create_measurement(measurement: MeasurementCreate, db: Session = Depends(get_db)):
    """Materialise a Measurement DB row and move staging from
    ``tmp/upload_<id>/<project_root>`` to ``_DATASET_DIR/<expose_name>``.
    status starts at ``pending``.
    """
    upload_id = measurement.upload_id
    staging = (TMP_DIR / upload_id).resolve()
    if not staging.exists() or not staging.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Staging directory not found for upload_id={upload_id}. "
                   "The upload may have expired or already been consumed.",
        )

    # Defence in depth — re-validate before moving so stale stagings can't
    # smuggle non-SPARC content through into the canonical dataset dir.
    ok, message = validate_sparc_structure(staging)
    if not ok:
        raise HTTPException(status_code=400, detail=message)

    project_root = resolve_project_root(staging)

    expose = unique_name(measurement.name)
    target = (_DATASET_DIR / expose).resolve()
    if target.exists():
        # unique_name's 8-hex suffix makes a collision astronomically unlikely,
        # but if it happens we fail closed rather than overwrite.
        raise HTTPException(
            status_code=500,
            detail=f"expose_name {expose} already occupies the dataset dir; retry.",
        )

    import shutil as _shutil
    target.parent.mkdir(parents=True, exist_ok=True)
    _shutil.move(str(project_root), str(target))

    # If staging is now empty (project_root was the only entry under it), reap
    # the upload_<id> wrapper so orphan-cleanup doesn't keep flagging it.
    try:
        if staging.exists() and not any(staging.iterdir()):
            force_rmtree(staging)
    except Exception as e:
        logger.warning(f"Failed to clean staging wrapper {staging}: {e}")

    db_row = Measurement(
        name=measurement.name,
        description=measurement.description,
        dataset_path=str(target),
        expose_name=expose,
        local_archive_path=str(target),
        status=MeasurementStatus.PENDING.value,
    )
    db.add(db_row)
    db.commit()
    db.refresh(db_row)

    logger.info(f"Created measurement {db_row.id} (expose={expose}) at {target}")
    return db_row


# ---------------------------------------------------------------------------
# Chunked upload (Approach A) — pre-create row, stream parts, finalize
#
# For datasets too large for the single-POST /upload-source path (tens of GiB
# DICOM queues): the row is created up front (status=pending_upload) and source
# bytes arrive as parts. Finalize assembles them and reuses the exact same SPARC
# validation + move the sync path uses, so everything downstream is unchanged.
# ---------------------------------------------------------------------------


class _ManifestEntryIn(BaseModel):
    rel_path: str
    size: int
    parts: int


class UploadInitRequest(BaseModel):
    name: str
    description: Optional[str] = None
    source_kind: str  # 'folder' | 'zip'
    manifest: List[_ManifestEntryIn]


class UploadInitResponse(BaseModel):
    measurement_id: str
    max_part_size: int


def _require_pending_upload(measurement_id: str, db: Session) -> Measurement:
    """Fetch a measurement that must be mid-upload, else map to 404/409."""
    row = db.query(Measurement).filter(Measurement.id == measurement_id).first()  # type: ignore
    if not row:
        raise HTTPException(status_code=404, detail="Measurement not found")
    if row.status != MeasurementStatus.PENDING_UPLOAD.value:
        raise HTTPException(
            status_code=409,
            detail=f"Measurement is not accepting chunks (status={row.status}).",
        )
    return row


@router.post("/upload/init", response_model=UploadInitResponse)
async def upload_init(req: UploadInitRequest, db: Session = Depends(get_db)):
    """Pre-create the Measurement row + chunk store for a chunked upload.

    Row creation and chunk-store init happen together: if the store rejects the
    manifest (e.g. file-count cap), the freshly created row is rolled back so we
    never leak an orphan ``pending_upload`` with no backing store.
    """
    if db.query(Measurement).filter(Measurement.name == req.name).first():  # type: ignore
        raise HTTPException(status_code=400, detail="Measurement with this name already exists")

    row = Measurement(
        name=req.name,
        description=req.description,
        status=MeasurementStatus.PENDING_UPLOAD.value,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    manifest = [e.model_dump() for e in req.manifest]
    try:
        chunk_store.init(row.id, req.source_kind, manifest, owner=None)
    except (ChunkStoreError, ValueError) as e:
        db.delete(row)
        db.commit()
        raise HTTPException(status_code=400, detail=str(e))

    logger.info(
        f"Upload init: measurement={row.id} kind={req.source_kind} files={len(manifest)}"
    )
    return UploadInitResponse(measurement_id=row.id, max_part_size=PART_SIZE)


@router.put("/upload/{measurement_id}/parts/{rel_path:path}")
async def upload_part(
    measurement_id: str,
    rel_path: str,
    request: Request,
    n: int,
    of: int,
    db: Session = Depends(get_db),
):
    """Receive one raw-bytes part for ``rel_path`` (query: ``n`` index, ``of`` count).

    Body is ``application/octet-stream``; never JSON, so the case-converter /
    pydantic layers are bypassed. Returns bytes received for this rel so far.
    """
    _require_pending_upload(measurement_id, db)
    data = await request.body()
    try:
        bytes_received = chunk_store.write_part(measurement_id, rel_path, n, of, data)
    except (ChunkStoreError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"rel_path": rel_path, "bytes_received": bytes_received}


@router.get("/upload/{measurement_id}/status")
async def upload_status(measurement_id: str, db: Session = Depends(get_db)):
    """Manifest + per-rel received parts/bytes for resume after reload/reconnect."""
    _require_pending_upload(measurement_id, db)
    try:
        return chunk_store.status(measurement_id)
    except ChunkStoreError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/upload/{measurement_id}/finalize", response_model=MeasurementResponse)
async def upload_finalize(measurement_id: str, db: Session = Depends(get_db)):
    """Assemble parts, run the existing SPARC validation, move into the dataset dir.

    On validation failure the row stays at ``pending_upload`` and the tmp parts
    are kept, so the user can rename / re-drop and finalize again rather than
    restart from zero. Only ``/cancel`` deletes the row + tmp.
    """
    row = _require_pending_upload(measurement_id, db)

    if not chunk_store.is_complete(measurement_id):
        raise HTTPException(status_code=400, detail="Upload incomplete; not all parts received.")

    import shutil as _shutil

    # 1. Assemble parts into a staging dir (folder) or a source.zip (zip).
    try:
        assembled = chunk_store.assemble(measurement_id)
    except ChunkStoreError as e:
        raise HTTPException(status_code=400, detail=str(e))

    source_kind = chunk_store.source_kind(measurement_id)
    extract_staging: Optional[Path] = None
    if source_kind == "zip":
        try:
            staging = extract_uploaded_archive(
                TMP_DIR, assembled, max_total_bytes=_MEASUREMENT_UPLOAD_MAX_BYTES
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Assembled archive is not a valid zip")
        extract_staging = staging
    else:
        staging = assembled  # the data/ tree

    # 2. Validate (resolve_project_root is applied inside validate + below).
    ok, message = validate_sparc_structure(staging)
    if not ok:
        # Keep row at pending_upload + keep tmp so the user can fix and retry.
        if extract_staging and extract_staging.exists():
            force_rmtree(extract_staging)
        raise HTTPException(status_code=400, detail=message)

    project_root = resolve_project_root(staging)
    if not _walk_sparc_meta(project_root)["patients"]:
        if extract_staging and extract_staging.exists():
            force_rmtree(extract_staging)
        raise HTTPException(status_code=400, detail="primary/ contains no patient subdirectories.")

    # 3. Move into the canonical dataset dir (mirrors /create's tail).
    expose = unique_name(row.name)
    target = (_DATASET_DIR / expose).resolve()
    if target.exists():
        raise HTTPException(
            status_code=500,
            detail=f"expose_name {expose} already occupies the dataset dir; retry.",
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    _shutil.move(str(project_root), str(target))

    # 4. Flip the row to the existing pending state; downstream is unchanged.
    row.dataset_path = str(target)
    row.expose_name = expose
    row.local_archive_path = str(target)
    row.status = MeasurementStatus.PENDING.value
    db.commit()
    db.refresh(row)

    # 5. Reap tmp: the chunk store dir + any zip-extract staging leftovers.
    chunk_store.cleanup(measurement_id)
    if extract_staging and extract_staging.exists():
        try:
            force_rmtree(extract_staging)
        except Exception as e:
            logger.warning(f"Failed to clean extract staging {extract_staging}: {e}")

    logger.info(f"Finalized chunked upload measurement={row.id} (expose={expose}) at {target}")
    return row


@router.post("/upload/{measurement_id}/cancel")
async def upload_cancel(measurement_id: str, db: Session = Depends(get_db)):
    """Abort an in-flight upload: drop the tmp parts and delete the row."""
    row = _require_pending_upload(measurement_id, db)
    chunk_store.cleanup(measurement_id)
    db.delete(row)
    db.commit()
    logger.info(f"Cancelled chunked upload measurement={measurement_id}")
    return {"success": True, "id": measurement_id}


# ---------------------------------------------------------------------------
# /tree — auto-classify + prefilled descriptions
# ---------------------------------------------------------------------------


def _observation_description_from_classify(
    classify: ClassifyResult, patient: str, sample: str
) -> Dict[str, Any]:
    """Build the prefilled Observation description for one sample folder.

    The frontend treats ``value_string`` as a string-valued Observation by
    default (``valueType="String"``); the user can flip it to Quantity in the
    UI. We attempt a best-effort numeric detection so simple measurements
    (e.g. ``28.5`` in a ``height.txt``) land as Quantity automatically.
    """
    raw = classify.value_string or ""
    # Strip the truncation banner before attempting the numeric check so that
    # an oversize file with leading numeric content still gets categorised.
    detect_target = raw
    if raw.startswith(_TRUNCATED_MARKER):
        detect_target = raw[len(_TRUNCATED_MARKER):].strip()
    detect_target = detect_target.strip()

    value_type = "String"
    value: Any = raw
    try:
        as_num = float(detect_target.splitlines()[0]) if detect_target else None
        if as_num is not None:
            value_type = "Quantity"
            value = as_num
    except (ValueError, IndexError):
        pass

    return {
        "resourceType": "Observation",
        "uuid": folder_resource_uuid(patient, sample),
        "value": value,
        "valueType": value_type,
        "code": "",
        "codeSystem": "http://loinc.org",
        "unit": "",
        "display": "",
        "_auto": {
            "samplePath": f"{patient}/{sample}",
            "sourceFile": classify.files[0] if classify.files else "",
            "truncated": classify.value_truncated,
        },
    }


def _imaging_study_description_from_classify(
    classify: ClassifyResult, patient: str, sample: str, sample_dir: Path
) -> Dict[str, Any]:
    """Build the prefilled ImagingStudy description.

    Constructs a ``NiiCompatibleImagingStudy`` so fhir-cda's pydicom reader
    pulls the real ``SeriesInstanceUID`` (DICOM tag ``(0020, 000e)``) and
    ``BodyPartExamined`` (``(0018, 0015)`` → SNOMED CT) out of the first
    DICOM in the sample. For NRRD / NII / NII.GZ samples the upstream
    branch leaves ``uid=None`` / ``body_site=None`` and we fall through to
    the same default shape.

    endpointUrl on both the study and the series is a placeholder mock
    here; the submit pipeline's finalize stage rewrites them to the real
    stream-proxy URL after MinIO upload.
    """
    img_uuid = folder_resource_uuid(patient, sample)
    endpoint_uuid = folder_endpoint_uuid(patient, sample)
    placeholder_url = f"MOCK://placeholder/{patient}/{sample}"

    # Default series payload; the fhir-cda probe below upgrades fields we
    # can actually read off the disk (uid / bodySite / numberOfInstances).
    series_payload: Dict[str, Any] = {
        "uid": None,
        "endpointUrl": placeholder_url,
        "endpointUuid": endpoint_uuid,
        "name": sample,
        "numberOfInstances": len(classify.files),
        "bodySite": None,
        "instances": [],
    }

    try:
        study = NiiCompatibleImagingStudy(
            uuid=img_uuid,
            sample_details=[{"uuid": endpoint_uuid, "path": sample_dir}],
            endpoint_url=placeholder_url,
            description=classify.modality_hint or "",
        )
        if study.series:
            real = study.series[0].get()
            series_payload["uid"] = real.get("uid") or None
            n = real.get("numberOfInstances")
            if isinstance(n, int) and n > 0:
                series_payload["numberOfInstances"] = n
            body_site = real.get("bodySite")
            if isinstance(body_site, dict) and body_site:
                series_payload["bodySite"] = body_site
    except Exception as e:
        # ``_read_sam`` already swallows pydicom errors internally; this catch
        # is for the constructor itself raising on e.g. mixed extensions,
        # which the classifier should have prevented but we play defensive.
        logger.warning(
            f"Could not extract ImagingStudy metadata from {sample_dir}: {e}"
        )

    return {
        "resourceType": "ImagingStudy",
        "uuid": img_uuid,
        "endpointUrl": placeholder_url,
        "description": classify.modality_hint or "",
        "display": "",
        "series": [series_payload],
        "_auto": {
            "samplePath": f"{patient}/{sample}",
            "modality": classify.modality_hint or "",
        },
    }


def _document_reference_description_from_classify(
    classify: ClassifyResult, patient: str, sample: str, sample_dir: Path
) -> Dict[str, Any]:
    """Build the prefilled DocumentReference description. One attachment per
    file, with a mime guess; ``url`` is mocked until the submit pipeline can
    point it at the stream proxy (we don't yet bother to compute per-file
    URLs in finalize — the submit only rewrites the fhir.json's ImagingStudy
    endpoint URLs to match the convention used by the FHIR client)."""
    attachments: List[Dict[str, Any]] = []
    for fname in classify.files:
        fpath = sample_dir / fname
        size = fpath.stat().st_size if fpath.exists() else 0
        content_type = mimetypes.guess_type(fname)[0] or "application/octet-stream"
        attachments.append(
            {
                "url": f"MOCK://placeholder/{patient}/{sample}/{fname}",
                "contentType": content_type,
                "title": fname,
                "size": size,
            }
        )
    return {
        "resourceType": "DocumentReference",
        "uuid": folder_resource_uuid(patient, sample),
        "description": "",
        "display": "",
        "attachments": attachments,
        "_auto": {
            "samplePath": f"{patient}/{sample}",
            "files": list(classify.files),
        },
    }


@router.get("/{measurement_id}/tree")
async def get_measurement_tree(measurement_id: str, db: Session = Depends(get_db)):
    """Walk every sample folder, run ``classify_sample``, and return:

      - ``tree``: hierarchical patient/sample/file view for the header card
      - ``descriptions``: prefilled fhir-cda descriptions ready for user edits
      - ``skipped_samples``: empty / un-classifiable sample paths (warning UI)
    """
    measurement: Optional[Measurement] = db.query(Measurement).filter(
        Measurement.id == measurement_id
    ).first()  # type: ignore
    if measurement is None:
        raise HTTPException(status_code=404, detail="Measurement not found")
    if not measurement.dataset_path:
        raise HTTPException(status_code=410, detail="Measurement has no dataset_path (was it deleted?)")

    dataset_root = Path(measurement.dataset_path)
    primary = dataset_root / "primary"
    if not primary.exists() or not primary.is_dir():
        raise HTTPException(
            status_code=410,
            detail="Dataset primary/ folder missing on disk (staging cleanup happened?)",
        )

    descriptions: Dict[str, Any] = {
        "dataset": {"uuid": folder_dataset_uuid(measurement.name), "name": measurement.name},
        "patients": [],
    }
    tree: Dict[str, Any] = {
        "name": measurement.name,
        "type": "dataset",
        "children": [],
    }
    skipped_samples: List[str] = []

    for patient_dir in sorted(p for p in primary.iterdir() if p.is_dir()):
        patient_name = patient_dir.name
        patient_entry: Dict[str, Any] = {
            "uuid": folder_patient_uuid(patient_name),
            "name": patient_name,
            "observations": [],
            "imagingStudy": [],
            "documentReference": [],
        }
        patient_node: Dict[str, Any] = {
            "name": patient_name,
            "type": "patient",
            "children": [],
        }

        for sample_dir in sorted(s for s in patient_dir.iterdir() if s.is_dir()):
            sample_name = sample_dir.name
            classify = classify_sample(sample_dir)
            sample_node: Dict[str, Any] = {
                "name": sample_name,
                "type": "sample",
                "fileCount": sum(1 for f in sample_dir.iterdir() if f.is_file()),
                "kind": classify.kind if classify else None,
            }
            patient_node["children"].append(sample_node)

            if classify is None:
                skipped_samples.append(f"{patient_name}/{sample_name}")
                continue

            if classify.kind == "Observation":
                patient_entry["observations"].append(
                    _observation_description_from_classify(classify, patient_name, sample_name)
                )
            elif classify.kind == "ImagingStudy":
                patient_entry["imagingStudy"].append(
                    _imaging_study_description_from_classify(
                        classify, patient_name, sample_name, sample_dir
                    )
                )
            else:  # DocumentReference
                patient_entry["documentReference"].append(
                    _document_reference_description_from_classify(
                        classify, patient_name, sample_name, sample_dir
                    )
                )

        descriptions["patients"].append(patient_entry)
        tree["children"].append(patient_node)

    return JSONResponse(
        content={
            "tree": tree,
            "descriptions": descriptions,
            "skipped_samples": skipped_samples,
        }
    )


# ---------------------------------------------------------------------------
# Annotation upsert + submit / retry-fhir + CRUD + stream proxy
# ---------------------------------------------------------------------------


@router.post("/{measurement_id}/annotation", response_model=MeasurementAnnotationResponse)
async def upsert_measurement_annotation(
    measurement_id: str,
    annotation: MeasurementAnnotationCreate,
    db: Session = Depends(get_db),
):
    """Insert or update the single MeasurementAnnotation row tied to this
    measurement. Idempotent so /submit retries don't trip the unique
    constraint.

    The inbound ``descriptions`` dict comes through the frontend's
    deepSnakeize interceptor (http.ts), so we canonicalise it via
    :func:`deep_camelize_keys` before storage. From this point on the
    in-DB shape matches what fhir-cda expects natively (camelCase keys).
    """
    measurement: Optional[Measurement] = db.query(Measurement).filter(
        Measurement.id == measurement_id
    ).first()  # type: ignore
    if measurement is None:
        raise HTTPException(status_code=404, detail="Measurement not found")

    descriptions = deep_camelize_keys(annotation.descriptions or {})

    existing: Optional[MeasurementAnnotation] = db.query(MeasurementAnnotation).filter(
        MeasurementAnnotation.measurement_id == measurement_id
    ).first()  # type: ignore

    if existing is None:
        row = MeasurementAnnotation(
            measurement_id=measurement_id,
            annotation_id=str(uuid.uuid4()),
            descriptions=descriptions,
        )
        db.add(row)
    else:
        existing.descriptions = descriptions
        existing.updated_at = datetime.utcnow()
        row = existing

    db.commit()
    db.refresh(row)
    return row


@router.post("/{measurement_id}/submit", response_model=MeasurementResponse)
async def submit_measurement(measurement_id: str, db: Session = Depends(get_db)):
    """Run the 6-stage submit pipeline synchronously:
    staging → fhir_build → upload → finalize → fhir_push.

    Stage failures bucket into one of two terminal states:
      - stages 1-3 (staging / fhir_build / upload) → SUBMIT_FAILED, MinIO rolled back
      - stages 4-6 (finalize / fhir_push) → FHIR_FAILED, MinIO retained (retry via /retry-fhir)
    """
    measurement: Optional[Measurement] = db.query(Measurement).filter(
        Measurement.id == measurement_id
    ).first()  # type: ignore
    if measurement is None:
        raise HTTPException(status_code=404, detail="Measurement not found")
    if measurement.status not in (
        MeasurementStatus.PENDING.value,
        MeasurementStatus.SUBMIT_FAILED.value,
    ):
        raise HTTPException(
            status_code=409,
            detail=f"Submit rejected: status={measurement.status} "
                   "(only pending / submit_failed can submit)",
        )

    annotation: Optional[MeasurementAnnotation] = db.query(MeasurementAnnotation).filter(
        MeasurementAnnotation.measurement_id == measurement_id
    ).first()  # type: ignore
    if annotation is None or not annotation.descriptions:
        raise HTTPException(
            status_code=400,
            detail="No annotation found; POST /api/measurement/{id}/annotation first.",
        )
    descriptions = annotation.descriptions  # already camelCase by /annotation contract
    # propagate the persisted dataset uuid onto the measurement row so retry / delete
    # can find hapi-fhir resources by identifier.
    dataset_uuid = descriptions.get("dataset", {}).get("uuid") or folder_dataset_uuid(measurement.name)
    measurement.uuid = dataset_uuid

    # Lock-in: any prior failure_* fields are obsolete the moment we re-submit.
    measurement.status = MeasurementStatus.UPLOADING.value
    measurement.failure_stage = None
    measurement.failure_message = None
    db.commit()

    dataset_path = Path(measurement.dataset_path) if measurement.dataset_path else None
    expose = measurement.expose_name

    # --- Stage 1: staging ----------------------------------------------------
    try:
        if dataset_path is None or not dataset_path.exists():
            raise FileNotFoundError(f"dataset_path missing on disk: {dataset_path}")
        primary = dataset_path / "primary"
        if not primary.exists():
            raise FileNotFoundError(f"primary/ missing under dataset_path: {dataset_path}")
    except Exception as e:
        set_stage_failure(measurement, "staging", e, db=db,
                          terminal_status=MeasurementStatus.SUBMIT_FAILED)
        raise HTTPException(status_code=500, detail=measurement.failure_message)

    # --- Stages 2–6 (shared with CLI import) ---------------------------------
    try:
        await run_measurement_approval(
            measurement, annotation,
            db=db, minio=minio, adapter=adapter, fhir_async_client=fhir_async_client,
        )
    except ApprovalError:
        raise HTTPException(status_code=500, detail=measurement.failure_message)

    db.refresh(measurement)
    logger.info(f"Measurement {measurement.id} submit complete (expose={expose})")
    return measurement


@router.post("/{measurement_id}/retry-fhir", response_model=MeasurementResponse)
async def retry_measurement_fhir(measurement_id: str, db: Session = Depends(get_db)):
    """Re-run stages 4-6 only. Rejects when status != fhir_failed (409).

    Uses ``delete_hapi_fhir_resources`` for idempotency: a prior failed push
    may have left partial resources on hapi-fhir; we sweep them by identifier
    before re-pushing so retries can't introduce duplicates."""
    measurement: Optional[Measurement] = db.query(Measurement).filter(
        Measurement.id == measurement_id
    ).first()  # type: ignore
    if measurement is None:
        raise HTTPException(status_code=404, detail="Measurement not found")
    if measurement.status != MeasurementStatus.FHIR_FAILED.value:
        raise HTTPException(
            status_code=409,
            detail=f"Retry rejected: status={measurement.status} (only fhir_failed can retry)",
        )

    annotation: Optional[MeasurementAnnotation] = db.query(MeasurementAnnotation).filter(
        MeasurementAnnotation.measurement_id == measurement_id
    ).first()  # type: ignore
    if annotation is None or not annotation.descriptions:
        raise HTTPException(status_code=400, detail="Annotation row missing; cannot retry.")
    descriptions = annotation.descriptions

    dataset_path = Path(measurement.dataset_path) if measurement.dataset_path else None
    if dataset_path is None or not dataset_path.exists():
        raise HTTPException(
            status_code=410,
            detail="dataset_path missing on disk; cannot retry — re-upload required.",
        )
    expose = measurement.expose_name

    measurement.status = MeasurementStatus.UPLOADING.value
    measurement.failure_stage = None
    measurement.failure_message = None
    db.commit()

    # Re-run finalize + push only (dataset already on MinIO) — shared with submit.
    try:
        await run_measurement_approval(
            measurement, annotation,
            db=db, minio=minio, adapter=adapter, fhir_async_client=fhir_async_client,
            update_mode=True,
        )
    except ApprovalError:
        raise HTTPException(status_code=500, detail=measurement.failure_message)

    db.refresh(measurement)
    logger.info(f"Measurement {measurement.id} retry-fhir complete (expose={expose})")
    return measurement


# ---------------------------------------------------------------------------
# Dry-run fhir.json preview (no upload) — backs the Preview page + Export action
# ---------------------------------------------------------------------------


@router.get("/{measurement_id}/fhir-preview")
async def preview_measurement_fhir(measurement_id: str, db: Session = Depends(get_db)):
    """Return the real FHIR bundle (fhir.json) for this measurement **without**
    uploading anything.

    - ``completed``: read the finalized fhir.json already on disk (endpoint URLs
      point at the live stream proxy).
    - any other non-uploading state: build it on the fly from the stored
      annotation (same logic as submit stage 2). endpointUrl values are
      placeholders here — they only get rewritten to real URLs by the submit
      pipeline's finalize stage after MinIO upload. The Preview page notes this.

    ``uploading`` returns 409 so this dry-run build can't race the submit
    pipeline writing the same fhir.json on disk.
    """
    measurement: Optional[Measurement] = db.query(Measurement).filter(
        Measurement.id == measurement_id
    ).first()  # type: ignore
    if measurement is None:
        raise HTTPException(status_code=404, detail="Measurement not found")
    if measurement.status == MeasurementStatus.UPLOADING.value:
        raise HTTPException(
            status_code=409,
            detail="Measurement is uploading; preview unavailable until it settles.",
        )

    # Completed datasets have a finalized fhir.json — read the canonical copy
    # from MinIO first (works even after the local dataset was cleaned up, e.g.
    # CLI imports), then the on-disk copy, before falling back to a rebuild.
    if measurement.status == MeasurementStatus.COMPLETED.value:
        if measurement.expose_name:
            try:
                return JSONResponse(content=read_fhir_json_from_minio(measurement.expose_name, minio))
            except FileNotFoundError:
                pass
        if measurement.dataset_path and Path(measurement.dataset_path).exists():
            try:
                return JSONResponse(content=read_fhir_json(Path(measurement.dataset_path)))
            except FileNotFoundError:
                pass

    # On-the-fly build (non-completed, or completed with no saved copy anywhere):
    # the annotator must walk primary/ on disk, so the dataset has to be present.
    dataset_path = Path(measurement.dataset_path) if measurement.dataset_path else None
    if dataset_path is None or not dataset_path.exists():
        raise HTTPException(
            status_code=410,
            detail="dataset_path missing on disk; cannot build fhir.json preview.",
        )

    annotation: Optional[MeasurementAnnotation] = db.query(MeasurementAnnotation).filter(
        MeasurementAnnotation.measurement_id == measurement_id
    ).first()  # type: ignore
    if annotation is None or not annotation.descriptions:
        raise HTTPException(
            status_code=404,
            detail="No annotation found; nothing to preview.",
        )

    try:
        annotator = MeasurementsFhirAnnotator(dataset_path)
        apply_descriptions(annotator, annotation.descriptions, dataset_path)
        annotator.save()
        return JSONResponse(content=read_fhir_json(dataset_path))
    except Exception as e:
        logger.error(f"fhir-preview build failed for {measurement_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to build fhir.json preview: {e}")


# ---------------------------------------------------------------------------
# Read / list / delete / metadata / stream
# ---------------------------------------------------------------------------


@router.get("/", response_model=List[MeasurementResponse])
async def list_measurements(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    rows = (
        db.query(Measurement)
        .order_by(Measurement.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return rows


@router.get("/metadata")
async def get_metadata_json(db: Session = Depends(get_db)):
    """Components-shape payload (uuid/id/name/path/expose/...) for downstream
    consumers, mirroring workflow_router.get_metadata_json. Only completed
    measurements appear here — pending / in-flight / failed ones are kept
    out of the public component listing."""
    use_ssl = os.getenv("USE_SSL", "false").lower() == "true"
    proto = "https" if use_ssl else "http"
    host = os.getenv("PORTAL_BACKEND_HOST", "localhost")

    components = []
    rows = db.query(Measurement).filter(
        Measurement.status == MeasurementStatus.COMPLETED.value
    ).all()
    for m in rows:
        if not m.expose_name:
            continue
        components.append(
            {
                "uuid": m.uuid or "",
                "id": m.id,
                "name": m.name,
                "path": f"{proto}://{host}/api/measurement/{m.expose_name}/primary",
                "expose": m.expose_name,
                "description": m.description or "",
                "created_at": m.created_at.isoformat() if m.created_at else "",
                "is_local": m.s3_path is None,
                "config": {},
            }
        )

    return JSONResponse(
        content={"components": components},
        headers={"Cache-Control": "no-cache, no-store"},
    )


@router.get("/{measurement_id}", response_model=MeasurementResponse)
async def get_measurement(measurement_id: str, db: Session = Depends(get_db)):
    measurement = db.query(Measurement).filter(
        Measurement.id == measurement_id
    ).first()  # type: ignore
    if measurement is None:
        raise HTTPException(status_code=404, detail="Measurement not found")
    return measurement


@router.delete("/{measurement_id}")
async def delete_measurement(measurement_id: str, db: Session = Depends(get_db)):
    """Cascade-delete: MinIO prefix, dataset_path on disk, DB row (with
    annotation via FK CASCADE), and hapi-fhir resources searched by
    identifier=measurement.uuid. Best-effort on each external system —
    we always close out the DB row even if MinIO / FHIR cleanup partially
    fails, so the user can rebuild from scratch."""
    try:
        measurement = db.query(Measurement).filter(
            Measurement.id == measurement_id
        ).first()  # type: ignore
        if measurement is None:
            return {"status": True, "message": "Already absent."}

        expose = measurement.expose_name
        dataset_path = Path(measurement.dataset_path) if measurement.dataset_path else None
        meas_uuid = measurement.uuid

        # MinIO cleanup
        if expose:
            try:
                keys = minio.list_objects(prefix=f"{expose}/")
                if keys:
                    minio.delete_objects(delete_keys=keys)
                    logger.info(f"Deleted {len(keys)} MinIO objects for {expose}")
            except Exception as e:
                logger.warning(f"MinIO cleanup failed for {expose}: {e}")

        # Disk cleanup
        if dataset_path and dataset_path.exists():
            try:
                force_rmtree(dataset_path)
                logger.info(f"Deleted dataset dir {dataset_path}")
            except Exception as e:
                logger.warning(f"Disk cleanup failed for {dataset_path}: {e}")

        # hapi-fhir cleanup
        if meas_uuid:
            removed = await delete_hapi_fhir_resources(meas_uuid, fhir_async_client)
            if removed:
                logger.info(f"Removed hapi-fhir resources: {removed}")

        db.delete(measurement)
        db.commit()
        return {"status": True, "message": "Measurement deleted successfully."}
    except Exception as e:
        logger.error(f"delete_measurement {measurement_id} failed: {e}")
        return {"status": False, "message": str(e)}


@router.get("/{measurement_id}/annotation", response_model=MeasurementAnnotationResponse)
async def get_measurement_annotation(measurement_id: str, db: Session = Depends(get_db)):
    """Return the stored annotation so retries / Step 2 rehydration can read
    back the descriptions tree (camelCase shape)."""
    annotation = db.query(MeasurementAnnotation).filter(
        MeasurementAnnotation.measurement_id == measurement_id
    ).first()  # type: ignore
    if annotation is None:
        raise HTTPException(status_code=404, detail="Measurement Annotation not found")
    return annotation


@router.get("/{expose_name}/primary/{path:path}")
async def stream_measurement_object(expose_name: str, path: str):
    """Stream a single object out of the private ``measurements`` bucket.
    Mirrors ``workflow_router.stream_workflow_object`` — needed because the
    public nginx ``/tools/`` pass-through doesn't serve the private bucket,
    and direct MinIO ports are no longer published to the host."""
    object_key = f"{expose_name}/primary/{path}"
    try:
        obj = minio.client.get_object(Bucket=minio.bucket_name, Key=object_key)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("404", "NoSuchKey"):
            raise HTTPException(status_code=404, detail=f"Measurement object not found: {object_key}")
        logger.error(f"MinIO get_object failed for {object_key}: {e}")
        raise HTTPException(status_code=503, detail="Measurement storage temporarily unavailable")

    content_type = obj.get("ContentType") or mimetypes.guess_type(path)[0] or "application/octet-stream"

    headers = {"Cache-Control": "private, max-age=300"}
    content_length = obj.get("ContentLength")
    if content_length is not None:
        headers["Content-Length"] = str(content_length)

    return StreamingResponse(
        obj["Body"].iter_chunks(chunk_size=64 * 1024),
        media_type=content_type,
        headers=headers,
    )
