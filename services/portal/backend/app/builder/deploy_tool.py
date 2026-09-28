from pathlib import Path
from typing import Dict, Any
from .logger import get_logger
import subprocess
import shlex
from app.client.minio import get_minio_client
from sqlalchemy.orm import Session
from app.models.db_model import Plugin, SessionLocal

logger = get_logger(__name__)


class PluginDeployer:
    """Handle Deploy plugin backend"""

    def __init__(self):
        pass

    @staticmethod
    def _check_compose_file(backend_dir: Path):
        compose_yml = backend_dir / 'docker-compose.yml'
        compose_yaml = backend_dir / 'docker-compose.yaml'
        if compose_yml.exists() or compose_yaml.exists():
            logger.info("Docker compose file is exist")
            return True
        else:
            logger.error("Docker compose file is not exist")
            raise Exception("Docker compose file is not exist")

    @staticmethod
    def _compose_execute(backend_dir: Path, command: str):
        try:
            logger.info(f"Running command {command} for deployment of {backend_dir}")
            with subprocess.Popen(
                    shlex.split(command),
                    cwd=backend_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1
            ) as process:
                for line in process.stdout:
                    logger.info(line.strip())

                return_code = process.wait()
                if return_code == 0:
                    logger.info("Docker compose command executed successfully.")
                else:
                    logger.error(f"Docker compose command failed with return code: {return_code}")

        except FileNotFoundError as e:
            logger.error(f"Docker or Docker Compose has not been installed or configured correctly. Error: {e}")
        except Exception as e:
            logger.error(f"An unexpected error occurred when running docker compose up: {e}")

    def deploy(self, plugin: Dict[str, Any]) -> Dict[str, Any]:

        deploy_logs = []
        expose_name = plugin.get("expose_name", )
        dataset_path = plugin.get("dataset_path", "unknown")
        backend_folder = plugin.get("backend_folder", "unknown")
        backend_deploy_command = plugin.get("backend_deploy_command", "docker compose up --build -d")

        try:
            # Step 1 get backend dir
            backend_dir = Path(dataset_path) / "code" / backend_folder
            logger.info(f"Step 1: Get backend dir {backend_dir.as_posix()} for docker deploy...")
            # Step 2: check if docker-compose.yml exist
            logger.info("Step 2: Check docker compose file...")
            self._check_compose_file(backend_dir)
            # Step 3 deploy backend in docker
            logger.info("Step 3: Start docker compose...")
            self._compose_execute(backend_dir, backend_deploy_command)
            return {
                "success": True,
                "backend_dir": str(backend_dir) if backend_dir else None,
                "deploy_logs": "\n".join(deploy_logs)
            }

        except Exception as e:
            error_message = str(e)
            logger.info(f"Deploy failed: {error_message}")
            logger.error(f"Deploy process failed: {e}")

            return {
                "success": False,
                "backend_dir": None,
                "deploy_logs": "\n".join(deploy_logs),
                "error_message": error_message
            }

    def compose_up(self, plugin: Dict[str, Any]) -> Dict[str, Any]:
        dir_path = plugin.get("backend_dir", "unknown")
        if dir_path is None or dir_path == "unknown":
            return {"success": False, "backend_dir": None}

        backend_dir = Path(dir_path)
        command = plugin.get("command", "docker compose up -d")

        if backend_dir.exists():
            try:
                self._compose_execute(backend_dir, command)
                logger.info(f"successfully run docker compose up -d for {backend_dir}")
                return {
                    "success": True,
                    "message": f"successfully run docker compose up -d for {backend_dir}",
                }
            except Exception as e:
                logger.error(f"Failed run docker compose up -d for {backend_dir}, error: {e}")
                return {
                    "success": False,
                    "message": f"Failed run docker compose up -d for {backend_dir}, error: {e}",
                }
        else:
            logger.error(f"Docker compose up failed, backend_dir {backend_dir} does not exist")
            return {
                "success": False,
                "message": f"Docker compose up for {backend_dir} does not exist",
            }

    def compose_down(self, plugin: Dict[str, Any]) -> Dict[str, Any]:
        dir_path = plugin.get("backend_dir", "unknown")
        if dir_path is None or dir_path == "unknown":
            return {"success": False, "backend_dir": None}

        backend_dir = Path(dir_path)
        command = plugin.get("command", "docker compose down")

        if backend_dir.exists():
            try:
                self._compose_execute(backend_dir, command)
                logger.info(f"successfully run docker compose down for {backend_dir}")
                return {
                    "success": True,
                    "message": f"successfully run docker compose down for {backend_dir}",
                }
            except Exception as e:
                logger.error(f"Failed run docker compose down for {backend_dir}, error: {e}")
                return {
                    "success": False,
                    "message": f"Failed run docker compose down for {backend_dir}, error: {e}",
                }
        else:
            logger.error(f"Docker compose down failed, backend_dir {backend_dir} does not exist")
            return {
                "success": False,
                "message": f"Docker compose down for {backend_dir} does not exist",
            }

    def delete(self, plugin: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute docker compose down and,
        Remove all images and volumes which belong to this compose
        """
        dir_path = plugin.get("backend_dir", "unknown")
        if dir_path is None or dir_path == "unknown":
            return {"success": False, "backend_dir": None}

        backend_dir = Path(dir_path)
        command = plugin.get("command", "docker compose down --rmi all --volumes")

        if backend_dir.exists():
            try:
                self._compose_execute(backend_dir, command)
                logger.info(f"successfully removed all images and volumes for {backend_dir}")
                return {
                    "success": True,
                    "message": f"successfully removed all images and volumes for {backend_dir}",
                }
            except Exception as e:
                logger.error(f"Failed removed all images and volumes for {backend_dir}, error: {e}")
                return {
                    "success": False,
                    "message": f"Failed removed all images and volumes for {backend_dir}, error: {e}",
                }
        else:
            logger.error(f"Removed all images and volumes failed, backend_dir {backend_dir} does not exist")
            return {
                "success": False,
                "message": f"Removed all images and volumes failed, because {backend_dir} does not exist",
            }
