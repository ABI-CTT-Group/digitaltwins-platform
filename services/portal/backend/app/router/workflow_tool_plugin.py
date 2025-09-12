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

configure_logging()
logger = get_logger(__name__)
router = APIRouter(prefix="/api/workflow-tool")
builder = PluginBuilder()
minio = get_minio_client()


@router.get("/check-name")
async def check_name(name: str, db: Session = Depends(get_db)):
    existing_plugin = db.query(Plugin).filter(Plugin.name == name).first()  # type:ignore
    if existing_plugin:
        raise HTTPException(status_code=400, detail="Plugin with this name already exists")
    return {"available": True, "message": "Name is available"}


@router.post("/plugins", response_model=PluginResponse)
async def create_tool_plugin(plugin: PluginCreate, db: Session = Depends(get_db)):
    db_plugin = Plugin(**plugin.model_dump())
    db.add(db_plugin)
    db.commit()
    db.refresh(db_plugin)
    return db_plugin


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


@router.get("/api/metadata")
async def get_metadata_json():
    try:
        obj = minio.client.get_object(Bucket=os.getenv("MINIO_BUCKET_NAME", "workflow-tools"), Key="metadata.json")
        data = obj['Body'].read().decode('utf-8')
        return json.loads(data)
    except ClientError as e:
        raise HTTPException(status_code=404, detail=f"File not found: metadata.json")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail=f"File is not valid JSON: metadata.json")


@router.get("/api/get-file/{object_key:path}")
async def get_file(object_key: str):
    try:
        obj = minio.client.get_object(Bucket=os.getenv("MINIO_BUCKET_NAME", "workflow-tools"), Key=object_key)
        return StreamingResponse(obj['Body'], media_type="application/octet-stream")
    except ClientError:
        raise HTTPException(status_code=404, detail=f"File not found: {object_key}")
