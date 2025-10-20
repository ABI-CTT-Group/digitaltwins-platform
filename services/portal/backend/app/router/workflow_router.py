import os
import json
import uvicorn
from fastapi import APIRouter, FastAPI, Depends, HTTPException, BackgroundTasks, Request, Query
from fastapi.responses import StreamingResponse
from app.database.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
from typing import List, Dict, Any, Literal
from contextlib import asynccontextmanager
from pydantic import BaseModel
import uuid
import threading
import requests
from app.models.db_model import (
    Workflow, WorkflowBuild, WorkflowAnnotation, WorkflowBase,
    WorkflowAnnotationBase, WorkflowResponse, WorkflowCreate,
    WorkflowAnnotationResponse, WorkflowBuildResponse, BuildStatus,
    SessionLocal
)
from app.builder.logger import get_logger, configure_logging
from app.client.minio import get_minio_client
from app.client.fhir import get_fhir_adapter
from botocore.exceptions import ClientError
from app.builder.build_workflow import WorkflowBuilder
from app.utils.workflow_tool_utils import get_build_record_or_404, get_public_url_for_build

from pathlib import Path
from uuid import UUID
from app.utils.utils import force_rmtree
from fhir_cda import Annotator
from pprint import pprint

configure_logging()
logger = get_logger(__name__)
router = APIRouter(prefix="/api/workflow")
minio = get_minio_client("workflows")
adapter = get_fhir_adapter()


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

    def run_build():
        try:
            with SessionLocal() as session:
                build_record = session.query(WorkflowBuild).filter(
                    WorkflowBuild.build_id == build_id).first()  # type: ignore
                if build_record:
                    build_record.status = BuildStatus.BUILDING.value
                    session.commit()

            builder = WorkflowBuilder()
            result = builder.build_workflow(workflow_dict)
            with SessionLocal() as session:
                build_record = session.query(WorkflowBuild).filter(WorkflowBuild.build_id == build_id).first()
                if build_record:
                    if result["success"]:
                        build_record.status = BuildStatus.COMPLETED.value
                        build_record.s3_path = result["s3_path"]
                        build_record.dataset_path = result["dataset_path"]
                        build_record.expose_name = result["expose_name"]
                    else:
                        build_record.status = BuildStatus.FAILED.value
                        build_record.error = result["error_message"]

                    build_record.build_logs = result["build_logs"]
                    build_record.updated_at = datetime.now()
                    session.commit()

        except Exception as e:
            # Update build record with error
            with SessionLocal() as session:
                build_record = session.query(WorkflowBuild).filter(WorkflowBuild.build_id == build_id).first()
                if build_record:
                    build_record.status = BuildStatus.FAILED.value
                    build_record.error_message = str(e)
                    build_record.updated_at = datetime.now()
                    session.commit()

    if background_tasks:
        background_tasks.add_task(run_build)
    else:
        thread = threading.Thread(target=run_build)
        thread.start()

    return {
        "build_id": build_id,
        "status": BuildStatus.PENDING.value,
        "message": "Build started in background",
        "repo_url": workflow.repository_url
    }

@router.get("/{workflow_id}/builds", response_model=List[WorkflowBuildResponse])
async def get_plugin_builds(workflow_id: str, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # Check if plugin exists
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()  # type: ignore
    if workflow is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    builds = db.query(WorkflowBuild).filter(WorkflowBuild.workflow_id == workflow.id).offset(skip).limit(limit).all()
    return builds

@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_plugin(workflow_id: str, db: Session = Depends(get_db)):
    workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()  # type: ignore
    if workflow is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return workflow
#
#

#
#

#
#
#
# @router.get("/plugin/{plugin_id}/approval")
# async def get_plugin_approval(plugin_id: str, db: Session = Depends(get_db)):
#     plugin, latest_build = get_latest_build_record(plugin_id, db)
#     dataset_path = Path(latest_build.dataset_path)
#     # TODO 1: Upload dataset to Digitaltwins Platform,and get the uuid
#     # dataset_uuid = upload_dataset(dataset_path)
#     dataset_uuid = "sparc-tool-001"
#     # TODO 2: Annotate tool dataset and upload to FHIR server
#     annotator = Annotator(dataset_path).workflow_tool()
#     annotator.update_uuid(dataset_uuid).update_name(plugin.name).update_title("Workflow tool").update_version(
#         plugin.version).save()
#     adapter_workflow_tool = adapter.digital_twin().workflow_tool()
#
#     await adapter_workflow_tool.add_workflow_tool_description(annotator.get_descriptions()).generate_resources()
#     return latest_build
#
#


@router.delete("/{workflow_id}")
async def delete_plugin(workflow_id: str, db: Session = Depends(get_db)):
    try:
        workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()  # type: ignore
        logger.info(f"Deleting plugin {workflow_id}")
        if workflow is not None:
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
                logger.info(f"Deleting plugin {workflow_id} successfully. and there is no tool component information in metadata.json")
                return {"status": True,
                        "message": "Plugin deleted successfully and no longer found in the metadata file."}
        except Exception as e:
            logger.info(f"Deleting plugin {workflow_id} successfully, but not find the metadata.json file in Minio, failed due to {e}")
            return {"status": True, "message": str(e)}
    except Exception as e:
        logger.info("Deleting plugin failed due to exception {}".format(e))
        return {"status": False, "message": str(e)}