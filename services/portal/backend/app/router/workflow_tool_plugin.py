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
import logging
import requests
from app.models.db_model import (
    Plugin, PluginCreate, PluginBuild, PluginResponse,
    PluginBuildResponse, BuildStatus, SessionLocal,
    DeployStatus, PluginDeployment, PluginDeployResponse,
    PluginAnnotationResponse, PluginAnnotationCreate,
    PluginAnnotation
)
from app.builder.logger import get_logger, configure_logging
from app.builder.build_tool import PluginBuilder
from app.builder.deploy_tool import PluginDeployer
from app.client.minio import get_minio_client
from app.client.fhir import get_fhir_adapter

from pathlib import Path
from botocore.exceptions import ClientError
from app.utils.workflow_tool_utils import (
    get_build_record_or_404,
    get_public_url_for_build,
    get_latest_build_record,
    shuttle_down_deployed_backend)
from app.utils.builder_utils import execute_build_in_background
from uuid import UUID
from app.utils.utils import force_rmtree
from fhir_cda import Annotator

configure_logging()
logger = get_logger(__name__)
router = APIRouter(prefix="/api/workflow-tools")
builder = PluginBuilder()
deployer = PluginDeployer()
minio = get_minio_client()
adapter = get_fhir_adapter()


@router.get("/", response_model=List[PluginResponse])
async def get_plugins(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    plugins = db.query(Plugin).offset(skip).limit(limit).all()
    responses = []
    for p in plugins:
        response = PluginResponse.model_validate(p)
        response.workflow_ids = [w.id for w in p.workflows]
        responses.append(response)

    return responses

@router.get("/check-name")
async def check_name(name: str, db: Session = Depends(get_db)):
    existing_plugin = db.query(Plugin).filter(Plugin.name == name).first()  # type:ignore
    if existing_plugin:
        raise HTTPException(status_code=400, detail="Plugin with this name already exists")
    return {"available": True, "message": "Name is available"}


@router.post("/create", response_model=PluginResponse)
async def create_tool_plugin(plugin: PluginCreate, db: Session = Depends(get_db)):

    db_plugin = Plugin(**plugin.model_dump())
    db.add(db_plugin)
    db.commit()
    db.refresh(db_plugin)
    return db_plugin


@router.post("/plugin/{plugin_id}/annotation", response_model=PluginAnnotationResponse)
async def create_tool_annotation(plugin_id: str, annotation: PluginAnnotationCreate, db: Session = Depends(get_db)):
    plugin = db.query(Plugin).filter(Plugin.id == plugin_id).first()  # type: ignore
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    annotation_id = str(uuid.uuid4())

    db_annotation = PluginAnnotation(
        plugin_id=plugin.id,
        annotation_id=annotation_id,
        fhir_note=annotation.fhir_note,
        sparc_note=annotation.sparc_note
    )

    db.add(db_annotation)
    db.commit()
    db.refresh(db_annotation)
    return db_annotation



@router.get("/plugin/{plugin_id}", response_model=PluginResponse)
async def get_plugin(plugin_id: str, db: Session = Depends(get_db)):
    plugin = db.query(Plugin).filter(Plugin.id == plugin_id).first()  # type: ignore
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return plugin


@router.delete("/plugin/{plugin_id}")
async def delete_plugin(plugin_id: str, db: Session = Depends(get_db)):
    try:
        plugin = db.query(Plugin).filter(Plugin.id == plugin_id).first()  # type: ignore
        logger.info(f"Deleting plugin {plugin_id}")
        if plugin is not None:
            # Check if plugin is used in any workflow
            if plugin.workflows:
                workflow_names = [w.name for w in plugin.workflows]
                raise HTTPException(
                    status_code=400,
                    detail=f"Cannot delete plugin. It is used in workflows: {', '.join(workflow_names)}",
                )

            builds = db.query(PluginBuild).filter(PluginBuild.plugin_id == plugin.id).all()
            if plugin.has_backend:
                logger.info(f"Shuttle down backend for plugin {plugin_id}")
                shuttle_down_deployed_backend(plugin.id, deployer)
            for build in builds:
                logger.info("Deleting build {}".format(build.id))
                # remove all images volume in docker
                if build.s3_path is not None:
                    logger.info("Deleting s3 path {}".format(build.s3_path))
                    prefix = build.s3_path.split("/")[-1]
                    object_keys = minio.list_objects(prefix=prefix)
                    if len(object_keys) > 0:
                        minio.delete_objects(delete_keys=object_keys)
                    # Delete dataset in dataset folder
                    dataset_path = builder.dataset_dir / prefix
                    force_rmtree(dataset_path)
                # db.delete(build)
            db.delete(plugin)
            db.commit()

        try:
            logger.info(f"Deleting plugin {plugin_id}: modify the minio metadata.json")
            # delete the record form the metadata.json file in MinIO
            metadata_file = await get_metadata_json()
            delete_plugin_component = next((c for c in metadata_file["components"] if c['id'] == plugin_id), None)
            if delete_plugin_component is not None:
                object_keys = minio.list_objects(prefix=delete_plugin_component.get("expose"))
                if len(object_keys) > 0:
                    minio.delete_objects(delete_keys=object_keys)
                # Update metadata.json file in minio
                metadata_file["components"] = [component for component in metadata_file["components"] if
                                               component['id'] != plugin_id]
                minio.update_metadata(metadata_file)
                logger.info(f"Deleting plugin {plugin_id} successfully, and metadata updated successfully.")
                return {"status": True, "message": "Plugin deleted successfully, and metadata updated successfully."}
            else:
                logger.info(
                    f"Deleting plugin {plugin_id} successfully. and there is no tool component information in metadata.json")
                return {"status": True,
                        "message": "Plugin deleted successfully and no longer found in the metadata file."}
        except Exception as e:
            logger.info(
                f"Deleting plugin {plugin_id} successfully, but not find the metadata.json file in Minio, failed due to {e}")
            return {"status": True, "message": str(e)}
    except Exception as e:
        logger.info("Deleting plugin failed due to exception {}".format(e))
        return {"status": False, "message": str(e)}


@router.get("/plugin/{plugin_id}/build")
async def execute_build(
        plugin_id: str,
        background_tasks: BackgroundTasks = None,
        db: Session = Depends(get_db)):
    """Execute a plugin build using git CLI and npm or yarn"""
    plugin = db.query(Plugin).filter(Plugin.id == plugin_id).first()  # type: ignore
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    # Covert Plugin object to dict for JSON serialization
    plugin_dict = {
        "id": plugin.id,
        "name": plugin.name,
        "description": plugin.description,
        "version": plugin.version,
        "author": plugin.author,
        "label": plugin.label,
        "has_backend": plugin.has_backend,
        "repo_url": plugin.repository_url,
        "frontend_folder": plugin.frontend_folder,
        "frontend_build_command": plugin.frontend_build_command,
        "backend_folder": plugin.backend_folder,
        "backend_deploy_command": plugin.backend_deploy_command,
        "plugin_metadata": plugin.plugin_metadata,
        "created_at": plugin.created_at.isoformat() if plugin.created_at else None,
        "updated_at": plugin.updated_at.isoformat() if plugin.updated_at else None,
    }
    logger.info(f"Building GUI plugin: {json.dumps(plugin_dict, indent=4)}")

    build_id = str(uuid.uuid4())

    db_build = PluginBuild(
        plugin_id=plugin.id,
        build_id=build_id,
        status=BuildStatus.PENDING.value,
    )

    db.add(db_build)
    db.commit()
    db.refresh(db_build)

    # TODO: check deploy status
    if plugin.has_backend:
        shuttle_down_deployed_backend(plugin.id, deployer)

    # executing build in backend
    execute_build_in_background(
        build_id=build_id,
        data=plugin_dict,
        builder=builder,
        Build=PluginBuild,
        background_tasks=background_tasks,
    )

    return {
        "build_id": build_id,
        "status": BuildStatus.PENDING.value,
        "message": "Build started in background",
        "repo_url": plugin.repository_url
    }


@router.get("/plugin/{plugin_id}/builds", response_model=List[PluginBuildResponse])
async def get_plugin_builds(plugin_id: str, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # Check if plugin exists
    plugin = db.query(Plugin).filter(Plugin.id == plugin_id).first()  # type: ignore
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")

    builds = db.query(PluginBuild).filter(PluginBuild.plugin_id == plugin.id).offset(skip).limit(limit).all()
    return builds

@router.get("/plugin/{plugin_id}/annotation", response_model=PluginAnnotationResponse)
async def get_plugin_annotations(plugin_id: str, db: Session = Depends(get_db)):
    plugin = db.query(Plugin).filter(Plugin.id == plugin_id).first() # type: ignore
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    annotation = db.query(PluginAnnotation).filter(PluginAnnotation.plugin_id == plugin.id).all()
    if len(annotation) == 0:
        raise HTTPException(status_code=404, detail="Annotation not found")
    return annotation[0]

@router.get("/plugin/{plugin_id}/deploy")
async def get_plugin_deploy(plugin_id: str, background_tasks: BackgroundTasks = None, db: Session = Depends(get_db)):
    plugin, latest_build = get_latest_build_record(plugin_id, db)
    # Covert Plugin, PluginBuild object to dict for JSON serialization
    plugin_dict = {
        "expose_name": latest_build.expose_name,
        "dataset_path": latest_build.dataset_path,
        "backend_folder": plugin.backend_folder,
        "backend_deploy_command": plugin.backend_deploy_command,
    }
    logger.info(f"Building plugin: {json.dumps(plugin_dict, indent=4)}")
    deploy_id = str(uuid.uuid4())
    db_deploy = PluginDeployment(
        plugin_id=plugin.id,
        build_id=latest_build.build_id,
        deploy_id=deploy_id,
        status=DeployStatus.PENDING.value,
    )

    db.add(db_deploy)
    db.commit()
    db.refresh(db_deploy)

    def run_deploy():
        try:
            with SessionLocal() as session:
                deploy_record = session.query(PluginDeployment).filter(
                    PluginDeployment.deploy_id == deploy_id).first()  # type: ignore
                if deploy_record:
                    deploy_record.status = DeployStatus.DEPLOYING.value
                    session.commit()
            logger.info("Starting plugin deployment...")
            result = deployer.deploy(plugin_dict)
            with SessionLocal() as session:
                deploy_record = session.query(PluginDeployment).filter(PluginDeployment.deploy_id == deploy_id).first()
                if deploy_record:
                    if result["success"]:
                        deploy_record.status = DeployStatus.COMPLETED.value
                        deploy_record.source_path = result["backend_dir"]
                        deploy_record.up = True
                    else:
                        deploy_record.status = BuildStatus.FAILED.value
                        deploy_record.error = result["error_message"]

                    deploy_record.updated_at = datetime.now()
                    session.commit()
        except Exception as e:
            logger.error(f"Deploy failed: {e}")
            with SessionLocal() as session:
                deploy_record = session.query(PluginDeployment).filter(PluginDeployment.deploy_id == deploy_id).first()
                if deploy_record:
                    deploy_record.status = DeployStatus.FAILED.value
                    deploy_record.error_message = str(e)
                    deploy_record.updated_at = datetime.now()
                    session.commit()

    if background_tasks:
        background_tasks.add_task(run_deploy)
    else:
        thread = threading.Thread(target=run_deploy)
        thread.start()

    return {
        "build_id": latest_build.build_id,
        "deploy_id": deploy_id,
        "status": DeployStatus.PENDING.value,
        "message": "Deploy started in background",
    }


@router.get("/plugin/build/{build_id}/deploys", response_model=List[PluginDeployResponse])
async def get_plugin_builds(build_id: str, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    # Check if plugin exists
    build_record = db.query(PluginBuild).filter(PluginBuild.build_id == build_id).first()  # type: ignore
    if build_record is None:
        raise HTTPException(status_code=404, detail="Plugin Build record not found")

    deployments = db.query(PluginDeployment).filter(PluginDeployment.build_id == build_record.build_id).offset(
        skip).limit(limit).all()
    return deployments


@router.get("/plugin/deploy/{deploy_id}/execute")
async def execute_plugin_backend_by_docker(deploy_id: str, command: Literal["up", "down"],
                                           db: Session = Depends(get_db)):
    deploy_record = db.query(PluginDeployment).filter(PluginDeployment.deploy_id == deploy_id).first()  # type: ignore
    if deploy_record is None:
        raise HTTPException(status_code=404, detail="Plugin Deploy record not found")
    if deploy_record.status == DeployStatus.COMPLETED.value:
        if command == "up":
            result = deployer.compose_up({
                "backend_dir": deploy_record.source_path
            })
            if result["success"]:
                deploy_record.up = True
                logger.info("Successfully executed docker compose up for plugin deployment")
        elif command == "down":
            result = deployer.compose_down({
                "backend_dir": deploy_record.source_path
            })
            if result["success"]:
                deploy_record.up = False
                logger.info("Successfully executed docker compose down for plugin deployment")
        db.commit()
        return {
            "success": True,
            "message": "Successfully executed docker compose command",
        }
    else:
        return {
            "success": False,
            "message": "Execution failed, because the deployment is not completed",
        }


@router.get("/check/deploy/{deploy_id}/")
async def get_check_deploy(deploy_id: str, db: Session = Depends(get_db)):
    deploy_record = db.query(PluginDeployment).filter(PluginDeployment.deploy_id == deploy_id).first()  # type: ignore
    if deploy_record is None:
        raise HTTPException(status_code=404, detail="Plugin Deploy record not found")
    return deploy_record.up


@router.get("/plugin/{plugin_id}/approval")
async def get_plugin_approval(plugin_id: str, db: Session = Depends(get_db)):
    plugin, latest_build = get_latest_build_record(plugin_id, db)
    dataset_path = Path(latest_build.dataset_path)
    # TODO 1: Upload dataset to Digitaltwins Platform,and get the uuid
    # dataset_uuid = upload_dataset(dataset_path)
    dataset_uuid = "sparc-tool-001"
    # TODO 2: Annotate tool dataset and upload to FHIR server
    annotator = Annotator(dataset_path).workflow_tool()
    annotator.update_uuid(dataset_uuid).update_name(plugin.name).update_title("Workflow tool").update_version(
        plugin.version).save()
    adapter_workflow_tool = adapter.digital_twin().workflow_tool()

    await adapter_workflow_tool.add_workflow_tool_description(annotator.get_descriptions()).generate_resources()
    return latest_build


@router.get("/builds/{build_id}", response_model=PluginBuildResponse)
async def get_build(build_id: str, db: Session = Depends(get_db)):
    build = db.query(PluginBuild).filter(PluginBuild.build_id == build_id).first()  # type: ignore
    if build is None:
        raise HTTPException(status_code=404, detail="Build not found")
    return build


@router.get("/builds", response_model=List[PluginBuildResponse])
async def get_all_builds(skip: int = 0, limit: int = 100, status: BuildStatus = None, db: Session = Depends(get_db)):
    query = db.query(PluginBuild)
    if status:
        query = query.filter(PluginBuild.status == status)  # type: ignore

    builds = query.offset(skip).limit(limit).all()
    return builds


@router.get("/builds/{build_id}/download-url")
async def get_build_download_url(build_id: str, db: Session = Depends(get_db)):
    """Get a presigned download URL for a build's artifacts"""

    try:
        build_record = get_build_record_or_404(build_id, db, PluginBuild)
        url, s3_path = get_public_url_for_build(build_record, "workflow-tools")

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
        build_record = get_build_record_or_404(build_id, db, PluginBuild)
        url, s3_path = get_public_url_for_build(build_record, "workflow-tools")

        return {
            "build_id": build_id,
            "direct_url": url,
            "s3_path": s3_path,
            "note": "This URL has no expiration and is publicly accessible"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate direct url for build {build_id}: {e}")


@router.get("/test-build")
async def get_test_build_info():
    try:
        result = builder.build_plugin({
            "id": "1",
            "repo_url": "https://github.com/Copper3D-brids/Plugin-AI-Image-Annotator",
            "name": "AI-Image-Annotator",
            "version": "1.0.0",
            "has_backend": True,
            "frontend_folder": "plugin-ai-annotator-frontend",
            "frontend_build_command": "yarn build",
            "backend_folder": "plugin-ai-annotator-backend",
            "backend_deploy_command": "docker compose up --build -d",
        })
        return result
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"build failed: {e}")


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


@router.get("/get-file/{object_key:path}")
async def get_file(object_key: str):
    try:
        obj = minio.get_object(object_key)
        return StreamingResponse(obj['Body'], media_type="application/octet-stream")
    except ClientError:
        raise HTTPException(status_code=404, detail=f"File not found: {object_key}")
