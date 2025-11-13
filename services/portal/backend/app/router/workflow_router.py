import os
import json
import uvicorn
from fastapi import APIRouter, FastAPI, Depends, HTTPException, BackgroundTasks, Request, Query
from fastapi.responses import StreamingResponse
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
from botocore.exceptions import ClientError
from app.builder.build_workflow import WorkflowBuilder
from app.utils.workflow_tool_utils import get_build_record_or_404, get_public_url_for_build, get_latest_build_record
from app.utils.builder_utils import execute_build_in_background

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


@router.post("/create", response_model=WorkflowResponse)
async def create_tool_plugin(workflow: WorkflowCreate, db: Session = Depends(get_db)):
    db_workflow = Workflow(**workflow.model_dump())
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
async def get_metadata_json():
    try:
        obj = minio.get_object("metadata.json")
        data = obj['Body'].read().decode('utf-8')
        return json.loads(data)
    except ClientError as e:
        raise HTTPException(status_code=404, detail=f"File not found: metadata.json")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail=f"File is not valid JSON: metadata.json")


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

        try:
            logger.info(f"Deleting workflow {workflow_id}: modify the minio metadata.json")
            # delete the record form the metadata.json file in MinIO
            metadata_file = await get_metadata_json()
            delete_plugin_component = next((c for c in metadata_file["components"] if c['id'] == workflow_id), None)
            if delete_plugin_component is not None:
                object_keys = minio.list_objects(prefix=delete_plugin_component.get("expose"))
                if len(object_keys) > 0:
                    minio.delete_objects(delete_keys=object_keys)
                # Update metadata.json file in minio
                metadata_file["components"] = [component for component in metadata_file["components"] if
                                               component['id'] != workflow_id]
                minio.update_metadata(metadata_file)
                logger.info(f"Deleting plugin {workflow_id} successfully, and metadata updated successfully.")
                return {"status": True, "message": "Plugin deleted successfully, and metadata updated successfully."}
            else:
                logger.info(
                    f"Deleting plugin {workflow_id} successfully. and there is no tool component information in metadata.json")
                return {"status": True,
                        "message": "Plugin deleted successfully and no longer found in the metadata file."}
        except Exception as e:
            logger.info(
                f"Deleting plugin {workflow_id} successfully, but not find the metadata.json file in Minio, failed due to {e}")
            return {"status": True, "message": str(e)}
    except Exception as e:
        logger.info("Deleting plugin failed due to exception {}".format(e))
        return {"status": False, "message": str(e)}
