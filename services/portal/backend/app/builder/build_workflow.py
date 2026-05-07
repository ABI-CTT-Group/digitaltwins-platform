import os
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, Literal

from sparc_me import Dataset
from .logger import get_logger
from app.client.minio import get_minio_client
from sqlalchemy.orm import Session
from app.builder.source_acquirer import SourceAcquirer, SourceSpec
from app.utils.builder_utils import (
    copy_item,
    remove_tmp_folder,
    unique_name,
)
from app.utils.utils import safe_path

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
        self.use_ssl = os.getenv('USE_SSL', "false").lower() == 'true'
        self._http_protocol: Literal['http', 'https'] = 'https' if self.use_ssl else 'http'

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
                    try:
                        shutil.copy2(safe_path(item), safe_path(primary_dir / item.name))
                    except Exception as e:
                        logger.error(f"Failed to copy {item} to {primary_dir / item.name}: {e}")
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
        source_type = workflow.get("source_type", "github")
        local_archive_path = workflow.get("local_archive_path")
        tmp_source_dir = None
        config = {}

        try:
            workflow_unique_expose_name = unique_name(workflow_name)
            logger.info("Workflow unique name is %s", workflow_unique_expose_name)
            metadata["expose"] = workflow_unique_expose_name
            # Step 0: Check for existing metadata
            logger.info("Step 0: Checking for existing plugin metadata...")

            # Step 1: Acquire project_dir via the registered SourceAcquirer.
            # Each acquirer owns its source-materialization details; from
            # step 2 onward the pipeline operates on project_dir uniformly.
            # tmp_source_dir is set so steps 2/3/4 trigger the same way.
            spec = SourceSpec(
                source_type=source_type,
                url=repo_url,
                branch=branch,
                local_archive_path=local_archive_path,
            )
            acquirer = SourceAcquirer.for_type(source_type, self.tmp_dir)
            project_dir = acquirer.acquire(spec)
            tmp_source_dir = project_dir  # Mark for cleanup

            # Step 2: Create SPARC dataset for cwl plugin script
            logger.info("Step 2: Creating SPARC dataset by sparc-me")
            dataset_dir = self.create_sparc_dataset(project_dir, None,
                                                    f"{workflow_unique_expose_name}")
            logger.info(f"SPARC dataset created in {dataset_dir}")

            # Step 3: Upload dataset to MinIO
            s3_path = None
            minio_client = get_minio_client("workflows")
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

            # Step 4: Clean up temporary source directory
            logger.info("Step 4: Cleaning up temporary files")
            try:
                remove_tmp_folder(tmp_source_dir, logger)
            except Exception as e:
                logger.error(f"Failed to remove temporary source directory: {e}")

            logger.info("Build process completed successfully")

            return {
                "success": True,
                "dataset_path": str(dataset_dir),
                "expose_name": workflow_unique_expose_name,
                "s3_path": s3_path,
                "build_logs": "\n".join(build_logs),
                "error_message": None,
            }
        except Exception as e:
            error_message = str(e)
            logger.info(f"Build failed: {error_message}")
            logger.error(f"Build process failed: {e}")
            remove_tmp_folder(tmp_source_dir, logger)
            return {
                "success": False,
                "dataset_path": None,
                "build_logs": "\n".join(build_logs),
                "error_message": error_message
            }
