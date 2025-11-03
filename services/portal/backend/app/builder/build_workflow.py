import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any

from sparc_me import Dataset
from .logger import get_logger
from app.client.minio import get_minio_client
from sqlalchemy.orm import Session
from app.utils.builder_utils import (
    clone_repository,
    copy_item,
    is_git_url,
    remove_tmp_folder,
    unique_name,
    update_minio_bucket_metadata)

logger = get_logger(__name__)


class WorkflowBuilder:
    """Handles building Workflow using git CLI and Sparc-me"""

    def __init__(self, dataset_dir: str = None, db: Optional[Session] = None):
        if dataset_dir is None:
            # Use environment variable or default to ./dataset for local, /datasets for Docker
            dataset_dir = os.environ.get('DATASET_DIR_WORKFLOW', "./datasets_workflow")
        self.tmp_dir = Path("./tmp")
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_dir = Path(dataset_dir)
        self.dataset_dir.mkdir(parents=True, exist_ok=True)

    def create_sparc_dataset(self,
                             project_dir: Path,
                             build_output_dir: Optional[Path] = None,
                             dataset_name: str = "plugin_build_dataset") -> Path:
        """Create a SPARC dataset with the build outputs and source code"""
        try:
            dataset_dir = self.dataset_dir / dataset_name
            dataset_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"Creating SPARC dataset {dataset_name}")

            dataset = Dataset()
            dataset.set_path(str(dataset_dir))

            dataset.create_empty_dataset(version="2.0.0")

            dataset_description = dataset.get_metadata(metadata_file="dataset_description")
            dataset_description.add_values(element="type", values="software")
            dataset_description.add_values(element='Title', values=f"{dataset_name} - Workflow")
            dataset_description.add_values(element='keywords', values=["plugin", "build", "software"])
            dataset_description.set_values(
                element='Contributor orcid',
                values=["https://orcid.org/0000-0000-0000-0000"]  # placeholder
            )

            code_dir = dataset_dir / "code"
            code_dir.mkdir(exist_ok=True)

            primary_dir = dataset_dir / "primary"
            primary_dir.mkdir(exist_ok=True)

            for item in project_dir.iterdir():
                if item.name == ".git":
                    continue
                copy_item(item, code_dir)
                if item.is_file() and item.suffix == ".cwl":
                    shutil.copy2(item, primary_dir / item.name)
            logger.info(f"Copied cwl artifacts from {project_dir} to {primary_dir}")

            dataset.save(save_dir=str(dataset_dir))

            print("saved dataset")

            logger.info(f"SPARC dataset created successfully in {dataset_dir}")
            logger.info(f"- Source code in: {code_dir}")
            if build_output_dir and build_output_dir.exists():
                logger.info(f"- Build artifacts in: {dataset_dir / 'primary'}")

            return dataset_dir

        except Exception as e:
            logger.error(f"Failed to create SPARC dataset: {e}")
            raise RuntimeError(f"Failed to create SPARC dataset: {e}")

    def build(self, workflow: Dict[str, Any]) -> Dict[str, Any]:
        """Complete plugin build process"""
        build_logs = []
        error_message = None
        repo_url = workflow.get("repo_url")
        branch = workflow.get("branch", "main")
        workflow_id = workflow.get("id")
        workflow_name = workflow.get("name", "unknown")
        version = workflow.get("version", "1.0.0")
        created_at = workflow.get("created_at", "unknown")
        author = workflow.get("author", "unknown")
        description = workflow.get("description", "No description provided")
        metadata = workflow.get("metadata", {})
        cloned_dir = None
        config = {}

        try:
            workflow_unique_expose_name = unique_name(workflow_name)
            logger.info("Workflow unique name is %s", workflow_unique_expose_name)
            metadata["expose"] = workflow_unique_expose_name
            # Step 0: Check for existing metadata
            logger.info("Step 0: Checking for existing plugin metadata...")

            # Step 1: Clone the repository or use local path
            if is_git_url(repo_url):
                logger.info("Step 1: Cloning repository...")
                project_dir = clone_repository(self.tmp_dir, repo_url, logger, branch)
                cloned_dir = project_dir  # Mark for cleanup
                logger.info(f"Repository cloned to: {cloned_dir}")
            else:
                logger.info("Step 1: Cloning repository...")
                logger.info(f"DEBUG: repo_url = '{repo_url}' (type: {type(repo_url)}, length: {len(repo_url)})")
                logger.info(f"DEBUG: repo_url.startswith('./workflow/') = {repo_url.startswith('./workflow/')}")
                logger.info(f"DEBUG: repo_url.startswith('/workflow/') = {repo_url.startswith('/workflow/')}")

                # For local paths, map them to the mounted volume
                # If the path starts with ./plugins or /plugins, use it as-is
                # Otherwise, assume it's a relative path under /plugins
                if repo_url.startswith("./workflow/"):
                    logger.info("DEBUG: Taking ./workflow/ branch")
                    # Convert relative path to absolute within container
                    workflow_name = repo_url.replace("./workflow/", "")
                    project_dir = Path(f'/workflow/{workflow_name}')
                elif repo_url.startswith('/workflow/'):
                    logger.info("DEBUG: Taking /workflow/ branch")
                    # Already an absolute path in the container
                    project_dir = Path(repo_url)
                else:
                    logger.info("DEBUG: Taking else branch")
                    # Assume it's a plugin name/path under /plugins
                    # Remove leading ./ if present
                    clean_path = repo_url.lstrip('./')
                    logger.info(f"DEBUG: clean_path = '{clean_path}'")
                    project_dir = Path(f'/plugins/{clean_path}')

                if not project_dir.exists():
                    raise RuntimeError(f"Local path does not exist: {project_dir}")
                if not project_dir.is_dir():
                    raise RuntimeError(f"Local path does not a directory: {project_dir}")
                logger.info(f"Using local project dictory: {project_dir}")

            # Step 2: Create SPARC dataset (only for remote repos) for cwl plugin script
            dataset_dir = None
            if cloned_dir:
                logger.info("Step 2 Creating SPARC dataset by sparc-me")
                dataset_dir = self.create_sparc_dataset(project_dir, None,
                                                        f"{workflow_unique_expose_name}")
                logger.info(f"SPARC dataset created in {dataset_dir}")
            else:
                logger.info("Step 2 Skipping SPARC dataset creation for local plugin...")

            # Step 3: Upload dataset to MinIO or copy to public folder
            s3_path = None
            minio_client = get_minio_client("workflows")
            if cloned_dir:
                logger.info("Step 3: Uploading dataset to MinIO...")
                try:
                    logger.info(f"Uploading dataset to MinIO: {metadata}")
                    dataset_name = metadata.get("expose", '')
                    logger.info(f"Uploading dataset to S3: {dataset_name}")
                    s3_path = minio_client.upload_directory(str(dataset_dir), dataset_name)
                    logger.info(f"Dataset uploaded to MinIO: {s3_path}")
                except Exception as e:
                    logger.error(f"Failed to upload dataset to S3: {e}")
                    s3_path = None
            else:
                logger.info("Step 3: Copying local tool plugin to public directory")
                # For local tool plugins, copy dist files to public directory using the path from metadata
                pass

            # Step 4: Clean up temporary files (only for cloned repos, not local paths)
            logger.info("Step 4: Cleaning up temporary files")
            if cloned_dir:
                try:
                    remove_tmp_folder(cloned_dir, logger)
                except Exception as e:
                    logger.error(f"Failed to remove cloned repository: {e}")
            else:
                logger.info("Skiping cleanup for local path")

            # Step 5: update metadata.json in MinIO
            # Determine the path based on whether it's a local plugin or remote
            if cloned_dir:
                # Remote plugin - use public directory path with metadata path
                plugin_path = f"http://{os.environ.get('HOST', 'localhost')}:{os.environ.get('MINIO_EXPOSE_PORT', 9000)}/{os.environ.get('MINIO_BUCKET_NAME', 'workflows')}/{metadata['expose']}/primary"
            else:
                # Local plugin - use public directory path with metadata expose folder name
                plugin_path = f""

            component_entry = {
                "uuid": "",
                "id": workflow_id,
                "name": workflow_name,
                "path": plugin_path,
                "expose": metadata.get("expose", ""),
                "description": description,
                "version": version,
                "created_at": created_at,
                "author": author,
                "repository_url": repo_url,
                "is_local": not bool(cloned_dir),
                "config": config
            }

            update_minio_bucket_metadata(minio_client, component_entry, logger)
            logger.info("Build process completed successfully")

            return {
                "success": True,
                "dataset_path": str(dataset_dir) if dataset_dir else None,
                "expose_name": workflow_unique_expose_name,
                "s3_path": s3_path,
                "build_logs": "\n".join(build_logs),
                "error_message": None,
                "is_local": not bool(cloned_dir)
            }
        except Exception as e:
            error_message = str(e)
            logger.info(f"Build failed: {error_message}")
            logger.error(f"Build process failed: {e}")
            remove_tmp_folder(cloned_dir, logger)
            return {
                "success": False,
                "dataset_path": None,
                "build_logs": "\n".join(build_logs),
                "error_message": error_message
            }
