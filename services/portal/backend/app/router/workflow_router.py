import os
import json
import mimetypes
import uvicorn
import zipfile
from botocore.exceptions import ClientError
from fastapi import APIRouter, FastAPI, Depends, HTTPException, BackgroundTasks, Request, Query, UploadFile, File
from fastapi.responses import StreamingResponse, JSONResponse
from app.database.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import select

from typing import List, Dict, Any, Literal
from contextlib import asynccontextmanager
from pydantic import BaseModel
import uuid
import requests
from app.models.db_model import (
    Plugin,
    Workflow, WorkflowBuild, WorkflowAnnotation, WorkflowBase,
    WorkflowResponse, WorkflowCreate, WorkflowAnnotationCreate,
    WorkflowAnnotationResponse, WorkflowBuildResponse, BuildStatus,
    SessionLocal
)
from app.builder.logger import get_logger, configure_logging
from app.client.minio import get_minio_client
from app.client.fhir import get_fhir_adapter, get_fhir_async_client
from app.builder.build_workflow import WorkflowBuilder
from app.utils.workflow_tool_utils import get_build_record_or_404, get_public_url_for_build, get_latest_build_record
from app.utils.builder_utils import (
    execute_build_in_background,
    extract_uploaded_archive,
    inspect_uploaded_source,
    read_root_cwl,
    resolve_project_root,
)

import json

from pathlib import Path
from uuid import UUID
from app.utils.utils import force_rmtree, is_empty
from fhir_cda import Annotator
from pprint import pprint

configure_logging()
logger = get_logger(__name__)
router = APIRouter(prefix="/api/workflow")
minio = get_minio_client("workflows")
adapter = get_fhir_adapter()
builder = WorkflowBuilder()
fhir_async_client = get_fhir_async_client()


@router.get("/check-name")
async def check_name(name: str, db: Session = Depends(get_db)):
    print(name)
    existing_workflow = db.query(Workflow).filter(Workflow.name == name).first()  # type:ignore
    if existing_workflow:
        raise HTTPException(status_code=400, detail="Workflow with this name already exists")
    return {"available": True, "message": "Name is available"}


@router.post("/upload-source")
async def upload_workflow_source(file: UploadFile = File(...)):
    """Receive a zip archive of a CWL workflow source folder, extract to staging.
    Workflows must contain at least one .cwl file at the root.
    """
    tmp_zip = builder.tmp_dir / f"upload_archive_{uuid.uuid4().hex[:8]}.zip"
    try:
        with open(tmp_zip, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)

        try:
            staging = extract_uploaded_archive(builder.tmp_dir, tmp_zip)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except zipfile.BadZipFile:
            raise HTTPException(status_code=400, detail="Uploaded file is not a valid zip archive")

        meta = inspect_uploaded_source(staging, want_npm=False, want_cwl=True)
        logger.info(f"Workflow source uploaded: upload_id={staging.name}, meta={meta}")

        if not meta["has_cwl"]:
            # cleanup before reporting back so we don't leak staging dirs on bad uploads
            force_rmtree(staging)
            raise HTTPException(
                status_code=400,
                detail="No .cwl file found at the root of the uploaded folder",
            )

        return {
            "upload_id": staging.name,
            "folders_in_root": meta["folders_in_root"],
            "package_version": meta["package_version"],
            "package_author": meta["package_author"],
            "has_cwl": meta["has_cwl"],
        }
    finally:
        if tmp_zip.exists():
            try:
                tmp_zip.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove temp zip {tmp_zip}: {e}")


@router.get("/{workflow_id}/cwl")
async def get_workflow_cwl(workflow_id: str, db: Session = Depends(get_db)):
    """Read the root .cwl file for a local-source workflow from its staging dir.
    Used by the annotation step in local mode (github mode still hits GitHub directly)."""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()  # type: ignore
    if workflow is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if workflow.source_type != "local" or not workflow.local_archive_path:
        raise HTTPException(
            status_code=400,
            detail="Workflow is not a local-source workflow; use GitHub API for github workflows",
        )

    staging = Path(workflow.local_archive_path)
    if not staging.exists() or not staging.is_dir():
        raise HTTPException(
            status_code=410,
            detail="Staging directory has been removed (build already completed?)",
        )

    result = read_root_cwl(staging)
    if result is None:
        raise HTTPException(status_code=404, detail="No .cwl file found at the root of the uploaded folder")
    return result


@router.post("/create", response_model=WorkflowResponse)
async def create_tool_plugin(workflow: WorkflowCreate, db: Session = Depends(get_db)):
    data = workflow.model_dump()
    upload_id = data.pop("upload_id", None)
    local_archive_path = None

    if workflow.source_type == "local":
        if not upload_id:
            raise HTTPException(
                status_code=400,
                detail="upload_id is required when source_type='local'",
            )
        staging = (builder.tmp_dir / upload_id).resolve()
        if not staging.exists() or not staging.is_dir():
            raise HTTPException(
                status_code=400,
                detail=f"Staging directory not found for upload_id={upload_id}. The upload may have expired or already been built.",
            )
        local_archive_path = str(resolve_project_root(staging))
        data["repository_url"] = f"local://{upload_id}"
    else:
        if not data.get("repository_url"):
            raise HTTPException(
                status_code=400,
                detail="repository_url is required when source_type='github'",
            )

    db_workflow = Workflow(**data, local_archive_path=local_archive_path)
    db.add(db_workflow)
    db.commit()
    db.refresh(db_workflow)
    return db_workflow


@router.post("/{workflow_id}/annotation", response_model=WorkflowAnnotationResponse)
async def create_tool_annotation(workflow_id: str, annotation: WorkflowAnnotationCreate, db: Session = Depends(get_db)):
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()  # type: ignore
    if workflow is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Update workflow plugins
    data = json.loads(annotation.fhir_note)
    if isinstance(data, list):
        plugin_ids = [p["id"] for p in data]
        plugins = db.query(Plugin).filter(Plugin.id.in_(plugin_ids)).all()
        if len(plugins) != len(plugin_ids):
            missing_ids = set(plugin_ids) - {p.id for p in plugins}
            raise HTTPException(status_code=404, detail=f"Plugins not found: {missing_ids}")
        workflow.plugins = plugins

    annotation_id = str(uuid.uuid4())

    db_annotation = WorkflowAnnotation(
        workflow_id=workflow.id,
        annotation_id=annotation_id,
        fhir_note=annotation.fhir_note,
        sparc_note=annotation.sparc_note
    )

    db.add(db_annotation)
    db.commit()
    db.refresh(db_annotation)
    return db_annotation


@router.get("/", response_model=List[WorkflowResponse])
async def get_plugins(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    workflows = db.query(Workflow).offset(skip).limit(limit).all()
    return workflows


@router.get("/metadata")
async def get_metadata_json(db: Session = Depends(get_db)):
    use_ssl = os.getenv('USE_SSL', "false").lower() == 'true'
    http_protocol = 'https' if use_ssl else 'http'
    host = os.environ.get('PORTAL_BACKEND_HOST', 'localhost')

    workflows = db.query(Workflow).all()
    components = []
    for workflow in workflows:
        latest_build = (db.query(WorkflowBuild)
            .filter(WorkflowBuild.workflow_id == workflow.id,
                    WorkflowBuild.status == BuildStatus.COMPLETED.value)
            .order_by(WorkflowBuild.created_at.desc())
            .first())
        if not latest_build or not latest_build.expose_name:
            continue

        build_ts = int(latest_build.created_at.timestamp()) if latest_build.created_at else 0
        is_local = latest_build.s3_path is None

        if is_local:
            path = ""
        else:
            path = f"{http_protocol}://{host}/api/workflow/{latest_build.expose_name}/primary"

        components.append({
            "uuid": workflow.uuid or "",
            "id": workflow.id,
            "name": workflow.name,
            "path": path,
            "expose": latest_build.expose_name,
            "description": workflow.description or "",
            "version": workflow.version,
            "created_at": workflow.created_at.isoformat() if workflow.created_at else "",
            "author": workflow.author or "",
            "repository_url": workflow.repository_url,
            "is_local": is_local,
            "config": {},
        })

    return JSONResponse(
        content={"components": components},
        headers={"Cache-Control": "no-cache, no-store"}
    )


@router.get("/{expose_name}/primary/{path:path}")
async def stream_workflow_object(expose_name: str, path: str):
    # Streams workflow build artifacts (e.g. CWL files) from the private MinIO
    # `workflows` bucket via the backend, replacing the legacy direct-MinIO URL
    # that depended on MINIO_PORT being published to the host.
    object_key = f"{expose_name}/primary/{path}"
    try:
        obj = minio.client.get_object(Bucket=minio.bucket_name, Key=object_key)
    except ClientError as e:
        code = e.response.get('Error', {}).get('Code')
        if code in ('404', 'NoSuchKey'):
            raise HTTPException(status_code=404, detail=f"Workflow object not found: {object_key}")
        logger.error(f"MinIO get_object failed for {object_key}: {e}")
        raise HTTPException(status_code=503, detail="Workflow storage temporarily unavailable")

    content_type = obj.get('ContentType') or mimetypes.guess_type(path)[0] or 'application/octet-stream'

    headers = {"Cache-Control": "public, max-age=300"}
    content_length = obj.get('ContentLength')
    if content_length is not None:
        headers['Content-Length'] = str(content_length)

    return StreamingResponse(
        obj['Body'].iter_chunks(chunk_size=64 * 1024),
        media_type=content_type,
        headers=headers,
    )


@router.get("/builds/{build_id}", response_model=WorkflowBuildResponse)
async def get_build(build_id: str, db: Session = Depends(get_db)):
    build = db.query(WorkflowBuild).filter(WorkflowBuild.build_id == build_id).first()  # type: ignore
    if build is None:
        raise HTTPException(status_code=404, detail="Build not found")
    return build


@router.get("/builds", response_model=List[WorkflowBuildResponse])
async def get_all_builds(skip: int = 0, limit: int = 100, status: BuildStatus = None, db: Session = Depends(get_db)):
    query = db.query(WorkflowBuild)
    if status:
        query = query.filter(WorkflowBuild.status == status)  # type: ignore

    builds = query.offset(skip).limit(limit).all()
    return builds


@router.get("/builds/{build_id}/download-url")
async def get_build_download_url(build_id: str, db: Session = Depends(get_db)):
    """Get a presigned download URL for a build's artifacts"""

    try:
        build_record = get_build_record_or_404(build_id, db, WorkflowBuild)
        url, s3_path = get_public_url_for_build(build_record, "workflows")

        return {
            "build_id": build_id,
            "download_url": url,
            "expires_in": None,  # No expiration for public URLs
            "s3_path": s3_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate download url for build {build_id}: {e}")


@router.get("/builds/{build_id}/direct-url")
async def get_build_direct_url(build_id: str, db: Session = Depends(get_db)):
    """Get a direct public URL for a build's artifacts (no expiration)"""
    try:
        build_record = get_build_record_or_404(build_id, db, WorkflowBuild)
        url, s3_path = get_public_url_for_build(build_record, "workflows")

        return {
            "build_id": build_id,
            "direct_url": url,
            "s3_path": s3_path,
            "note": "This URL has no expiration and is publicly accessible"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate direct url for build {build_id}: {e}")


@router.get("/{workflow_id}/build")
async def execute_build(
        workflow_id: str,
        background_tasks: BackgroundTasks = None,
        db: Session = Depends(get_db)):
    """Build a workflow using git CLI"""
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()  # type: ignore
    if workflow is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Covert Workflow object to dict for JSON serialization
    workflow_dict = {
        "id": workflow.id,
        "name": workflow.name,
        "description": workflow.description,
        "version": workflow.version,
        "author": workflow.author,
        "repo_url": workflow.repository_url,
        "source_type": workflow.source_type,
        "local_archive_path": workflow.local_archive_path,
        "metadata": {},
        "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
        "updated_at": workflow.updated_at.isoformat() if workflow.updated_at else None,
    }
    logger.info(f"Building Workflow: {json.dumps(workflow_dict, indent=4)}")

    build_id = str(uuid.uuid4())

    db_build = WorkflowBuild(
        workflow_id=workflow.id,
        build_id=build_id,
        status=BuildStatus.PENDING.value,
    )

    db.add(db_build)
    db.commit()
    db.refresh(db_build)

    execute_build_in_background(
        build_id=build_id,
        data=workflow_dict,
        builder=builder,
        Build=WorkflowBuild,
        background_tasks=background_tasks,
    )

    return {
        "build_id": build_id,
        "status": BuildStatus.PENDING.value,
        "message": "Build started in background",
        "repo_url": workflow.repository_url
    }


@router.get("/{workflow_id}/builds", response_model=List[WorkflowBuildResponse])
async def get_workflow_builds(workflow_id: str, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # Check if plugin exists
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()  # type: ignore
    if workflow is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    builds = db.query(WorkflowBuild).filter(WorkflowBuild.workflow_id == workflow.id).offset(skip).limit(limit).all()
    return builds


@router.get("/{workflow_id}/annotation", response_model=WorkflowAnnotationResponse)
async def get_workflow_annotation(workflow_id: str, db: Session = Depends(get_db)) -> WorkflowAnnotationResponse:
    annotation = db.query(WorkflowAnnotation).filter(
        WorkflowAnnotation.workflow_id == workflow_id).first()  # type: ignore
    if annotation is None:
        raise HTTPException(status_code=404, detail="Workflow Annotation not found")

    return annotation


@router.get("/{workflow_id}/approval")
async def get_workflow_approval(workflow_id: str, db: Session = Depends(get_db)):
    workflow, latest_build = get_latest_build_record(workflow_id, "workflow", db)
    dataset_path = Path(latest_build.dataset_path)
    # TODO 1: Upload dataset to Digitaltwins Platform,and get the uuid
    # dataset_uuid = upload_dataset(dataset_path)
    if is_empty(workflow.uuid):
        dataset_uuid = f"sparc-workflow-${uuid.uuid4()}"
        # TODO 2: Update workflow uuid
        workflow.uuid = dataset_uuid
        db.commit()
    else:
        dataset_uuid = workflow.uuid
    # TODO 3: Annotate tool dataset and upload to FHIR server
    annotator = Annotator(dataset_path).workflow()

    annotation = db.query(WorkflowAnnotation).filter(
        WorkflowAnnotation.workflow_id == workflow_id).first()  # type: ignore

    if annotation is None:
        raise HTTPException(status_code=404, detail="Workflow Annotation not found")

    try:
        # annotation.fhir_note
        fhir_note = json.loads(annotation.fhir_note)

        (annotator.update_uuid(dataset_uuid)
         .update_name(workflow.name)
         .update_author(workflow.author)
         .update_version(workflow.version))

        actions = annotator.annotate_action()
        for action in actions:
            step_annotation = next((item for item in fhir_note if item["name"] == action.title), None)
            if step_annotation is None:
                continue
            action.set_related_tool_uuid(step_annotation["uuid"])
            tool_fhir_note = step_annotation["tool_fhir_note"]
            for i in action.annotate_input():
                step_annotation_input = next((item for item in tool_fhir_note["inputs"] if item["name"] == i.display),
                                             None)
                if step_annotation_input is None:
                    continue
                i.set_resource_type(step_annotation_input["resource"])

            for o in action.annotate_output():
                step_annotation_output = next(
                    (item for item in tool_fhir_note["outputs"] if item["name"] == o.display), None)
                if step_annotation_output is None:
                    continue
                o.set_resource_type(step_annotation_output["resource"])
                if step_annotation_output["resource"] == "Observation":
                    o.set_code(step_annotation_output["code"]).set_system(step_annotation_output["system"]).set_unit(
                        step_annotation_output["unit"])

        annotator.save()
        adapter_workflow = adapter.digital_twin().workflow()
        await adapter_workflow.add_workflow_description(annotator.get_descriptions()).generate_resources()
        return latest_build
    except Exception as e:
        logger.error(f"Failed to get annotation for workflow {workflow_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get workflow annotation: {e}")


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(workflow_id: str, db: Session = Depends(get_db)):
    annotation = db.query(Workflow).filter(Workflow.id == workflow_id).first()  # type: ignore
    if annotation is None:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return annotation


@router.delete("/{workflow_id}")
async def delete_plugin(workflow_id: str, db: Session = Depends(get_db)):
    try:
        workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()  # type: ignore
        logger.info(f"Deleting plugin {workflow_id}")
        if workflow is not None:

            # Check if workflow instance exists
            if workflow.uuid:
                resource_workflows = await fhir_async_client.resources("PlanDefinition").search(
                    identifier=workflow.uuid).fetch_all()
                logger.info(f"Delete: find workflow fhir resources: {resource_workflows}")
                for w in resource_workflows:
                    try:
                        await w.delete()
                        logger.info(f"Deleted workflow fhir resource uuid: {workflow_id}, resource: {w.to_reference()}")
                    except Exception as e:
                        logger.error(f"Failed to delete workflow {workflow_id} in FHIR server: {e}")

            builds = db.query(WorkflowBuild).filter(WorkflowBuild.workflow_id == workflow.id).all()  # type: ignore
            for build in builds:
                logger.info("Deleting build {}".format(build.id))
                if build.s3_path is not None:
                    logger.info("Deleting s3 path {}".format(build.s3_path))
                    prefix = build.s3_path.split("/")[-1]
                    object_keys = minio.list_objects(prefix=prefix)
                    if len(object_keys) > 0:
                        minio.delete_objects(delete_keys=object_keys)
                    # Delete dataset in dataset folder
                    dataset_path = builder.dataset_dir / prefix
                    print("delete: ", dataset_path)
                    force_rmtree(dataset_path)
            db.delete(workflow)
            db.commit()

        logger.info(f"Deleting workflow {workflow_id} successfully.")
        return {"status": True, "message": "Workflow deleted successfully."}
    except Exception as e:
        logger.info("Deleting plugin failed due to exception {}".format(e))
        return {"status": False, "message": str(e)}
