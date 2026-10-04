import os
import shutil
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any

from sparc_me import Dataset
from .logger import get_logger
from app.client.minio import get_minio_client
from sqlalchemy.orm import Session
from app.builder.build_tool import PluginBuilder, TOOL_BUILDS_BUCKET
from app.builder.source_acquirer import SourceAcquirer, SourceSpec
from app.builder.workflow_layout import detect_workflow_layout
from app.utils.builder_utils import (
    copy_item,
    remove_tmp_folder,
    unique_name,
)
from app.models.db_model import DEFAULT_GUI_BUILD_COMMAND
from app.utils.utils import force_rmtree, safe_path

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

            layout = detect_workflow_layout(project_dir)
            if layout.is_sds:
                # digitaltwins-api ingests the package as it is (its metadata, primary/ CWLs and code/).
                for item in layout.root.iterdir():
                    copy_item(item, dataset_dir)  # skips .git, node_modules, dist, build
                logger.info(f"Copied SDS workflow package {layout.root} to {dataset_dir}")
                return dataset_dir

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

    def build_gui_tool(self, package_root: Path, dataset_dir: Path, workflow: Dict[str, Any], expose_name: str) -> str:
        """Build a gui SDS workflow's tool frontend into ``primary/<tool stem>/`` of the dataset; returns the stem.

        digitaltwins-api copies that folder into the tool dataset's primary/ on approval. The build runs in a
        scratch copy of code/, so the source (for a local upload, its staging folder) is never modified.
        """
        tool_cwls = sorted(p for p in (package_root / "primary").glob("tool_*.cwl") if p.is_file())
        if len(tool_cwls) != 1:
            raise RuntimeError(f"A gui workflow must have exactly one primary/tool_*.cwl (found {len(tool_cwls)})")
        tool_name = tool_cwls[0].stem
        has_backend = bool(workflow.get("has_backend"))
        scratch = Path(tempfile.mkdtemp(prefix="gui_build_", dir=self.tmp_dir))
        try:
            code = scratch / "code"
            code.mkdir()
            for item in (package_root / "code").iterdir():
                copy_item(item, code)  # skips .git, node_modules, dist, build
            frontend = code / workflow["frontend_folder"] if has_backend else code
            command = workflow.get("frontend_build_command") or DEFAULT_GUI_BUILD_COMMAND
            output = PluginBuilder(dataset_dir=str(self.dataset_dir)).build_frontend(
                frontend, expose_name, command, has_backend)
            if output is None:
                raise RuntimeError("The frontend build produced no dist/ or build/ folder")
            shutil.copytree(output, dataset_dir / "primary" / tool_name, dirs_exist_ok=True)
        finally:
            force_rmtree(scratch)
        return tool_name

    @staticmethod
    def upload_bundle(bundle_dir: Path, expose_name: str) -> Optional[str]:
        """Serve a gui workflow's bundle before approval from the public tool-builds bucket, like a tool test build.

        Returns the bundle's prefix, or None if the upload failed (the build still succeeds, as for tools).
        """
        prefix = f"{expose_name}/primary"
        try:
            get_minio_client(TOOL_BUILDS_BUCKET).upload_directory(str(bundle_dir), prefix)
        except Exception as e:
            logger.error(f"Failed to upload the gui tool bundle to {TOOL_BUILDS_BUCKET}: {e}")
            return None
        return f"{TOOL_BUILDS_BUCKET}/{prefix}"

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
        # Transient secrets — see build_tool.py for the full contract.
        token = workflow.get("token")
        auth_username = workflow.get("auth_username")
        verify_ssl = workflow.get("verify_ssl", True)
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
                token=token,
                auth_username=auth_username,
                verify_ssl=verify_ssl,
            )
            acquirer = SourceAcquirer.for_type(source_type, self.tmp_dir)
            project_dir = acquirer.acquire(spec)
            tmp_source_dir = project_dir  # Mark for cleanup

            layout = detect_workflow_layout(project_dir)
            workflow_type = workflow.get("workflow_type")
            if layout.is_sds and not workflow_type:
                raise RuntimeError("An SDS workflow package needs a workflow type (script, notebook or gui)")

            # Step 2: Create SPARC dataset for cwl plugin script
            logger.info("Step 2: Creating SPARC dataset by sparc-me")
            dataset_dir = self.create_sparc_dataset(project_dir, None,
                                                    f"{workflow_unique_expose_name}")
            logger.info(f"SPARC dataset created in {dataset_dir}")

            # Step 2.1: a gui SDS workflow builds its one tool's frontend, as GUI tools do
            tool_name = bundle_path = None
            if layout.is_sds and workflow_type == "gui":
                logger.info("Step 2.1: Building the gui tool's frontend")
                tool_name = self.build_gui_tool(layout.root, dataset_dir, workflow, workflow_unique_expose_name)
                bundle_path = self.upload_bundle(dataset_dir / "primary" / tool_name, workflow_unique_expose_name)

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

            # Step 4: Clean up temporary source directory.
            # See build_tool.py — local staging dir is canonical source for
            # the workflow record and must survive the build for rebuilds.
            logger.info("Step 4: Cleaning up temporary files")
            if source_type == "local":
                logger.info(
                    f"Step 4: Skipping cleanup for local source — staging dir "
                    f"{tmp_source_dir} preserved for rebuild"
                )
            else:
                try:
                    remove_tmp_folder(tmp_source_dir, logger)
                except Exception as e:
                    logger.error(f"Failed to remove temporary source directory: {e}")

            logger.info("Build process completed successfully")

            return {
                "success": True,
                "dataset_path": str(dataset_dir),
                "is_sds": layout.is_sds,
                "tool_name": tool_name,
                "bundle_path": bundle_path,
                "expose_name": workflow_unique_expose_name,
                "s3_path": s3_path,
                "build_logs": "\n".join(build_logs),
                "error_message": None,
            }
        except Exception as e:
            error_message = str(e)
            logger.info(f"Build failed: {error_message}")
            logger.error(f"Build process failed: {e}")
            if source_type != "local":
                remove_tmp_folder(tmp_source_dir, logger)
            return {
                "success": False,
                "dataset_path": None,
                "build_logs": "\n".join(build_logs),
                "error_message": error_message
            }
