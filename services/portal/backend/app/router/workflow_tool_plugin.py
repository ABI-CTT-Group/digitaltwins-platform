import os
import json
import uvicorn
from fastapi import APIRouter, FastAPI, Depends, HTTPException, BackgroundTasks, Request, Query
from fastapi.responses import StreamingResponse
from app.database.database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
from typing import List, Dict, Any
from contextlib import asynccontextmanager
from pydantic import BaseModel
import uuid
import threading
import logging
import requests
from app.models.db_model import (
    Plugin, PluginCreate, PluginBuild, PluginResponse,
    PluginBuildResponse, BuildStatus, SessionLocal
)
from app.builder.logger import get_logger, configure_logging
from app.builder.build import PluginBuilder
from app.builder.minio_client import get_minio_client
from pathlib import Path
from botocore.exceptions import ClientError
from app.utils.workflow_tool_utils import (get_build_record_or_404, get_public_url_for_build)
from uuid import UUID

configure_logging()
logger = get_logger(__name__)
router = APIRouter(prefix="/api/workflow-tools")
builder = PluginBuilder()
minio = get_minio_client()


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


@router.get("/", response_model=List[PluginResponse])
async def get_plugins(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    plugins = db.query(Plugin).offset(skip).limit(limit).all()
    return plugins


@router.get("/plugin/{plugin_id}", response_model=PluginResponse)
async def get_plugin(plugin_id: str, db: Session = Depends(get_db)):
    plugin = db.query(Plugin).filter(Plugin.id == plugin_id).first()  # type: ignore
    if plugin is None:
        raise HTTPException(status_code=404, detail="Plugin not found")
    return plugin


@router.delete("/plugin/{plugin_id}")
async def delete_plugin(plugin_id: str, db: Session = Depends(get_db)):
    plugin = db.query(Plugin).filter(Plugin.id == plugin_id).first()  # type: ignore
    if plugin is not None:
        db.delete(plugin)
        db.commit()

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
        return {"message": "Plugin deleted successfully"}
    else:
        raise HTTPException(status_code=404, detail="Plugin not exist in metadata.json")


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
    logger.info(f"Building plugin: {json.dumps(plugin_dict, indent=4)}")

    build_id = str(uuid.uuid4())

    db_build = PluginBuild(
        plugin_id=plugin.id,
        build_id=build_id,
        status=BuildStatus.PENDING.value,
    )

    db.add(db_build)
    db.commit()
    db.refresh(db_build)

    def run_build():
        try:
            with SessionLocal() as session:
                build_record = session.query(PluginBuild).filter(PluginBuild.build_id == build_id).first()  # type: ignore
                if build_record:
                    build_record.status = BuildStatus.BUILDING.value
                    session.commit()

            builder = PluginBuilder()
            result = builder.build_plugin(plugin_dict)
            with SessionLocal() as session:
                build_record = session.query(PluginBuild).filter(PluginBuild.build_id == build_id).first()
                if build_record:
                    if result["success"]:
                        build_record.status = BuildStatus.COMPLETED.value
                        build_record.s3_path = result["s3_path"]
                    else:
                        build_record.status = BuildStatus.FAILED.value
                        build_record.error = result["error_message"]

                    build_record.build_logs = result["build_logs"]
                    build_record.updated_at = datetime.now()
                    session.commit()

        except Exception as e:
            # Update build record with error
            with SessionLocal() as session:
                build_record = session.query(PluginBuild).filter(PluginBuild.id == build_id).first()
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
        build_record = get_build_record_or_404(build_id, db)
        url, s3_path = get_public_url_for_build(build_record)

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
        build_record = get_build_record_or_404(build_id, db)
        url, s3_path = get_public_url_for_build(build_record)

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
        obj = minio.client.get_object(Bucket=os.getenv("MINIO_BUCKET_NAME", "workflow-tools"), Key="metadata.json")
        data = obj['Body'].read().decode('utf-8')
        return json.loads(data)
    except ClientError as e:
        raise HTTPException(status_code=404, detail=f"File not found: metadata.json")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail=f"File is not valid JSON: metadata.json")


@router.get("/get-file/{object_key:path}")
async def get_file(object_key: str):
    try:
        obj = minio.client.get_object(Bucket=os.getenv("MINIO_BUCKET_NAME", "workflow-tools"), Key=object_key)
        return StreamingResponse(obj['Body'], media_type="application/octet-stream")
    except ClientError:
        raise HTTPException(status_code=404, detail=f"File not found: {object_key}")
