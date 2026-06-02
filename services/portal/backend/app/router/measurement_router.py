"""Measurements upload router (plan 07).

Phase 2 (upload-source / check-name / create / tree) is implemented here.
Phase 3 (annotation / submit / retry-fhir / CRUD / stream) endpoints still
return 501; they delegate to ``app.services.measurement_service`` once that
module lands.

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
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
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
from app.services.measurement_classifier import (
    _TRUNCATED_MARKER,
    ClassifyResult,
    classify_sample,
)
from app.utils.builder_utils import (
    extract_uploaded_archive,
    resolve_project_root,
    unique_name,
    validate_sparc_structure,
)
from app.utils.measurement_mocks import (
    mock_dataset_uuid,
    mock_patient_uuid,
    mock_resource_uuid,
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

# Reuse the workflow builder's tmp dir for upload staging — extract_uploaded_archive
# writes to tmp/upload_<id>/ regardless of source type, and orphan cleanup in
# main.py already scans tmp/ for stale uploads.
_builder = WorkflowBuilder()
TMP_DIR = _builder.tmp_dir


def _not_implemented(detail: str):
    """Phase-3 placeholder. Returning 501 (not 500) flags this as designed
    behaviour to anyone hitting the endpoint during the build-out window."""
    raise HTTPException(status_code=501, detail=f"{detail} — phase 3 placeholder")


# ---------------------------------------------------------------------------
# Phase 2: source acquisition + create + tree
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
            staging = extract_uploaded_archive(TMP_DIR, tmp_zip)
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
        "uuid": mock_resource_uuid("obs"),
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
    classify: ClassifyResult, patient: str, sample: str
) -> Dict[str, Any]:
    """Build the prefilled ImagingStudy description. The endpointUrl on both
    the study and its series is filled with placeholder mocks here; the
    submit pipeline (finalize stage) overwrites them with the real
    portal-backend stream proxy URL after MinIO upload."""
    series = {
        "uid": None,
        "endpointUrl": f"MOCK://placeholder/{patient}/{sample}",
        "endpointUuid": mock_resource_uuid("endpoint"),
        "name": sample,
        "numberOfInstances": len(classify.files),
        "bodySite": None,
        "instances": [],
    }
    return {
        "resourceType": "ImagingStudy",
        "uuid": mock_resource_uuid("img"),
        "endpointUrl": f"MOCK://placeholder/{patient}/{sample}",
        "description": "",
        "display": "",
        "series": [series],
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
        "uuid": mock_resource_uuid("doc"),
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
        "dataset": {"uuid": mock_dataset_uuid(), "name": measurement.name},
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
            "uuid": mock_patient_uuid(patient_name),
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
                    _imaging_study_description_from_classify(classify, patient_name, sample_name)
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
# Phase 3 placeholders — to be filled in by Tasks 3.1-3.6
# ---------------------------------------------------------------------------


@router.post("/{measurement_id}/annotation", response_model=MeasurementAnnotationResponse)
async def upsert_measurement_annotation(
    measurement_id: str,
    annotation: MeasurementAnnotationCreate,
    db: Session = Depends(get_db),
):
    _not_implemented("annotation")


@router.post("/{measurement_id}/submit", response_model=MeasurementResponse)
async def submit_measurement(measurement_id: str, db: Session = Depends(get_db)):
    _not_implemented("submit")


@router.post("/{measurement_id}/retry-fhir", response_model=MeasurementResponse)
async def retry_measurement_fhir(measurement_id: str, db: Session = Depends(get_db)):
    _not_implemented("retry-fhir")


@router.get("/", response_model=List[MeasurementResponse])
async def list_measurements(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    _not_implemented("list")


@router.get("/metadata")
async def get_metadata_json(db: Session = Depends(get_db)):
    _not_implemented("metadata")


@router.get("/{measurement_id}", response_model=MeasurementResponse)
async def get_measurement(measurement_id: str, db: Session = Depends(get_db)):
    _not_implemented("get")


@router.delete("/{measurement_id}")
async def delete_measurement(measurement_id: str, db: Session = Depends(get_db)):
    _not_implemented("delete")


@router.get("/{measurement_id}/annotation", response_model=MeasurementAnnotationResponse)
async def get_measurement_annotation(measurement_id: str, db: Session = Depends(get_db)):
    _not_implemented("get-annotation")


@router.get("/{expose_name}/primary/{path:path}")
async def stream_measurement_object(expose_name: str, path: str):
    _not_implemented("stream-object")
