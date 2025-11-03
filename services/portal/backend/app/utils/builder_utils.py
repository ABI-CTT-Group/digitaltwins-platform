from __future__ import annotations
import subprocess
import uuid
from pathlib import Path
import logging
import shutil
from app.utils.utils import force_rmtree
import re
from app.client.minio import MinioClient

from typing import Dict, Any, Union, Type, TYPE_CHECKING
import threading
from app.models.db_model import (
    BuildStatus, SessionLocal, PluginBuild, WorkflowBuild)
from datetime import datetime
from fastapi import BackgroundTasks

if TYPE_CHECKING:
    from app.builder.build_tool import PluginBuilder
    from app.builder.build_workflow import WorkflowBuilder

def clone_repository(tmp_dir: Path, repo_url: str, logger: logging.Logger, branch: str = "main") -> Path:
    """Clone a git repository to a temporary directory"""
    try:
        clone_dir = tmp_dir / f"build_{uuid.uuid4().hex[:8]}"
        clone_dir.mkdir(exist_ok=True)
        if not repo_url.endswith(".git"):
            repo_url += ".git"
        logger.info(f"Cloning repository {repo_url} to {clone_dir}")
        subprocess.run(
            ["git", "clone", "--branch", branch, repo_url, str(clone_dir)],
            capture_output=True,
            text=True,
            check=True
        )
        logger.info(f"Successfully cloned repository to {clone_dir}")
        return clone_dir
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to clone repository: {e}")
        logger.error(f"stdout: {e.stdout}")
        logger.error(f"stderr: {e.stderr}")
        raise RuntimeError(f"Git clone failed: {e}")


def copy_item(src: Path, dst: Path, exclude: set = None):
    if exclude is None:
        exclude = {".git", "node_modules", "dist", "build"}

    if src.name in exclude:
        return

    if src.is_dir():
        shutil.copytree(src, dst / src.name, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dst / src.name)


def is_git_url(repo_url: str) -> bool:
    """Check if the repository URL is a valid git url"""
    return repo_url.startswith("git@") or repo_url.startswith("https://") or repo_url.startswith("http://")


def unique_name(name: str) -> str:
    """Make the name unique by adding a random string to the end"""
    clean = re.sub(r'[^a-zA-Z0-9]', '', name)
    return f"{clean}_{uuid.uuid4().hex[:8]}"


def remove_tmp_folder(path: Path, logger: logging.Logger):
    if not path.exists():
        return
    force_rmtree(path)
    logger.info("Cleaning up cloned repository")
    # force_rmtree(dataset_dir)
    # logger.info("Cleaning up sparc dataset")


def update_minio_bucket_metadata(minio_client: MinioClient, component_entry: Dict[str, Any], logger: logging.Logger):
    component_exists = False
    existing_metadata = minio_client.metadata
    for i, component in enumerate(existing_metadata.get("components", [])):
        # TODO: need to tweak, using DigitalTWIN Platform tool dataset uuid
        if component.get("name") == component_entry.get("name"):
            existing_metadata["components"][i] = component_entry
            component_exists = True
            logger.info(f"Updated existing component: {component_entry['name']}")
            break

    if not component_exists:
        existing_metadata["components"].append(component_entry)
        logger.info(f"Added new component: {component_entry['name']}")

    logger.info(f"Write metadata to MinIO metadata file")
    minio_client.update_metadata(existing_metadata)


def execute_build_in_background(
        build_id: str,
        data: Dict[str, Any],
        builder: Union[PluginBuilder, WorkflowBuilder],
        Build: Type[Union[PluginBuild, WorkflowBuild]],
        background_tasks: BackgroundTasks = None):
    def run_build():
        try:
            with SessionLocal() as session:
                build_record = session.query(Build).filter(
                    Build.build_id == build_id).first()  # type: ignore
                if build_record:
                    build_record.status = BuildStatus.BUILDING.value
                    session.commit()

            result = builder.build(data)
            with SessionLocal() as session:
                build_record = session.query(Build).filter(Build.build_id == build_id).first()
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
                build_record = session.query(Build).filter(Build.build_id == build_id).first()
                if build_record:
                    build_record.status = BuildStatus.FAILED.value
                    build_record.error_message = str(e)
                    build_record.updated_at = datetime.now()
                    session.commit()
                else:
                    print("⚠️ Build record not found when writing error message")

    if background_tasks:
        background_tasks.add_task(run_build)
    else:
        thread = threading.Thread(target=run_build)
        thread.start()
