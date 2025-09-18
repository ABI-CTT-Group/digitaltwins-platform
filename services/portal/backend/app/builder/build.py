import os
import re
import subprocess
import shutil
import platform
import uuid
import json
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.parse import quote

from app.utils.utils import force_rmtree

from sparc_me import Dataset
from .logger import get_logger
from .minio_client import get_minio_client
from sqlalchemy.orm import Session
from app.models.db_model import Plugin, SessionLocal

logger = get_logger(__name__)


class PluginBuilder:
    """Handles building plugins using git CLI and npm"""

    def __init__(self, dataset_dir: str = None, db: Optional[Session] = None):
        if dataset_dir is None:
            # Use environment variable or default to ./dataset for local, /datasets for Docker
            dataset_dir = os.environ.get('DATASET_DIR', "./datasets")
        self.tmp_dir = Path("./tmp")
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_dir = Path(dataset_dir)
        self.dataset_dir.mkdir(parents=True, exist_ok=True)

    def clone_repository(self, repo_url: str, branch: str = "main") -> Path:
        """Clone a git repository to a temporary directory"""
        try:
            clone_dir = self.tmp_dir / f"plugin_build_{uuid.uuid4().hex[:8]}"
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

    def check_npm_project(self, project_dir: Path) -> bool:
        """Check if the project directory contains npm project files"""
        package_json = project_dir / "package.json"
        return package_json.exists()

    def frontend_install(self, project_dir: Path) -> Dict[str, Any]:
        """Run npm install in the project directory"""
        try:
            logger.info(f"Running npm install in {project_dir}")

            result = subprocess.run(
                self._convert_command("npm install --force"),
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=True
            )
            logger.info("npm installation completed successfully")
            return {
                "success": True,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"npm install failed: {e}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            return {
                "success": False,
                "stdout": e.stdout,
                "stderr": e.stderr,
                "error": str(e)
            }

    def frontend_build(self, project_dir: Path, build_cmd: str) -> Dict[str, Any]:
        """Run npm build in the project directory"""
        try:
            logger.info(f"Running {build_cmd} in {project_dir}")
            result = subprocess.run(
                self._convert_command(cmd=build_cmd),
                cwd=project_dir,
                capture_output=True,
                text=True,
                check=True
            )
            logger.info("npm build completed successfully")
            return {
                "success": True,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
        except subprocess.CalledProcessError as e:
            logger.error(f"npm build failed: {e}")
            logger.error(f"stdout: {e.stdout}")
            logger.error(f"stderr: {e.stderr}")
            return {
                "success": False,
                "stdout": e.stdout,
                "stderr": e.stderr,
                "error": str(e)
            }

    @staticmethod
    def _convert_command(cmd: str) -> list:
        if isinstance(cmd, str):
            cmd = cmd.split()

        node_path = shutil.which("node")
        npm_path = shutil.which("npm")
        yarn_path = shutil.which("yarn")
        docker_path = shutil.which("docker")

        if platform.system() == "Windows":
            if cmd[0] == "npm" and not npm_path:
                npm_path = shutil.which("npm.cmd")
            if cmd[0] == "yarn" and not yarn_path:
                yarn_path = shutil.which("yarn.cmd")

        if cmd[0] == "node" and not node_path:
            logger.error("Node is not in the PATH. Please install Node.js or add it to the PATH.")
            raise FileNotFoundError("Node is not in the PATH. Please install Node.js or add it to the PATH.")
        if cmd[0] == "npm" and not npm_path:
            logger.error("npm is not in the PATH. Please install Node.js/npm or use Conda to install nodejs.")
            raise FileNotFoundError(
                "npm is not in the PATH. Please install Node.js/npm or use Conda to install nodejs.")
        if cmd[0] == "yarn" and not yarn_path:
            logger.error("yarn is not in the PATH. Please install yarn or add it to the PATH.")
            raise FileNotFoundError("yarn is not in the PATH. Please install yarn or add it to the PATH.")
        if cmd[0] == "docker" and not docker_path:
            logger.error("docker is not in the PATH. Please install docker or add it to the PATH.")
            raise FileNotFoundError("docker is not in the PATH. Please install docker or add it to the PATH.")

        if cmd[0] == "node":
            cmd[0] = node_path
        elif cmd[0] == "npm":
            cmd[0] = npm_path
        elif cmd[0] == "yarn":
            cmd[0] = yarn_path
        elif cmd[0] == "docker":
            cmd[0] = docker_path

        return cmd

    def create_sparc_dataset(self,
                             project_dir: Path,
                             has_backend: bool,
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
            dataset_description.add_values(element='Title', values=f"{dataset_name} - Plugin Build")
            dataset_description.add_values(element='keywords', values=["plugin", "build", "software"])
            dataset_description.set_values(
                element='Contributor orcid',
                values=["https://orcid.org/0000-0000-0000-0000"]  # placeholder
            )

            code_dir = dataset_dir / "code"
            code_dir.mkdir(exist_ok=True)

            if has_backend:
                for layer in project_dir.iterdir():
                    if layer.name == ".git":
                        continue
                    if layer.is_dir():
                        for item in layer.iterdir():
                            dest = code_dir / layer.name
                            dest.mkdir(exist_ok=True)
                            self._copy_item(item, dest)
                    else:
                        self._copy_item(layer, code_dir)
            else:
                for item in project_dir.iterdir():
                    self._copy_item(item, code_dir)

            if build_output_dir and build_output_dir.exists():
                primary_dir = dataset_dir / "primary"
                primary_dir.mkdir(exist_ok=True)

                for item in build_output_dir.iterdir():
                    if item.is_dir():
                        shutil.copytree(item, primary_dir / item.name, dirs_exist_ok=True)
                    else:
                        shutil.copy2(item, primary_dir / item.name)

                logger.info(f"Copied build artifacts from {build_output_dir} to {primary_dir}")

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

    @staticmethod
    def _copy_item(src: Path, dst: Path, exclude: set = None):

        if exclude is None:
            exclude = {".git", "node_modules", "dist", "build"}

        if src.name in exclude:
            return

        if src.is_dir():
            shutil.copytree(src, dst / src.name, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst / src.name)

    def is_git_url(self, repo_url: str) -> bool:
        """Check if the repository URL is a valid git url"""
        return repo_url.startswith("git@") or repo_url.startswith("https://") or repo_url.startswith("http://")

    def replace_path_in_umd_js(self, project_dir: Path, has_backend: bool, expose_name: str,
                               frontend_folder: Optional[str] = None):
        """Replace the path in file ends with .umd.js file for other files in the dist directory to the new path with the minio path"""
        other_files = []
        umd_js_file_path = None
        if has_backend:
            if frontend_folder is None:
                logger.error("Must provide frontend_folder with has_backend=True")
                raise
            dist_dir = project_dir / frontend_folder / "dist"
        else:
            dist_dir = project_dir / "dist"
        for file in dist_dir.iterdir():
            if file.is_file() and not file.name.endswith(".umd.js"):
                other_files.append(file)
            elif file.is_file() and file.name.endswith(".umd.js"):
                umd_js_file_path = file
            else:
                logger.warning(f"File {file} is not a file")

        if umd_js_file_path is None:
            raise RuntimeError("umd.js file not found")

        with open(umd_js_file_path, "r") as f:
            umd_js_content = f.read()

        new_path_prefix = f"http://{os.environ.get('HOST', 'localhost')}:9000/{os.environ.get('MINIO_BUCKET_NAME', 'workflow-tools')}/{expose_name}/primary/"
        umd_js_content = umd_js_content.replace(new_path_prefix, expose_name)

        with open(umd_js_file_path, "w") as f:
            f.write(umd_js_content)

    def unique_name(self, name: str) -> str:
        """Make the name unique by adding a random string to the end"""
        clean = re.sub(r'[^a-zA-Z0-9]', '', name)
        return f"{clean}_{uuid.uuid4().hex[:8]}"

    def replace_vite_build_config(self, file_path: Path, new_name: str) -> bool:
        """
        Replace `name`, `formats`, and `fileName` fields in a Vite config file.

        Returns a dict indicating which fields were replaced.
        """
        patterns = {
            "name": re.compile(r'name:\s*["\']([^"\']*)["\']', re.IGNORECASE),
            "formats": re.compile(r'formats:\s*\[.*?]', re.IGNORECASE | re.DOTALL),
            "fileName": re.compile(r'fileName\s*:\s*.*', re.IGNORECASE)
        }
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            replaced = {"name": False, "formats": False, "fileName": False}

            # replace name
            def name_replacer(match):
                replaced["name"] = True
                quote = '"' if '"' in match.group(0) else "'"
                return f'name: {quote}{new_name}{quote}'

            content = patterns["name"].sub(name_replacer, content)

            # replace formats
            def formats_replacer(match):
                replaced["formats"] = True
                return "formats: ['umd']"

            content = patterns["formats"].sub(formats_replacer, content)

            # replace fileName
            def filename_replacer(match):
                replaced["fileName"] = True
                return "fileName: (format) => `my-app.${format}.js`"

            content = patterns["fileName"].sub(filename_replacer, content)

            # Write back to file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"Updated name in {file_path}")
            return True
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return False

    def update_vite_config(self, project_dir: Path, plugin_expose_name: str):
        """Update the vite.config.js file to use the unique name"""
        vite_config_js = project_dir / "vite.config.js"
        vite_config_ts = project_dir / "vite.config.ts"
        if vite_config_js.exists():
            vite_config_file = vite_config_js
        elif vite_config_ts.exists():
            vite_config_file = vite_config_ts
        else:
            logger.error("vite.config.js or vite.config.ts not found")
            raise RuntimeError("vite.config.js or vite.config.ts not found")

        self.replace_vite_build_config(vite_config_file, plugin_expose_name)

    def update_plugin_version(self, project_dir: Path, plugin_id: str):
        package_json = project_dir / "package.json"
        with open(package_json, "r") as f:
            package_json = json.load(f)
        version = package_json.get("version", None)
        if version is not None:
            with SessionLocal() as session:
                plugin = session.query(Plugin).filter(Plugin.id == plugin_id).first()  # type: ignore
                plugin.version = version
                session.commit()
        return version


    def build_plugin(self, plugin: Dict[str, Any]) -> Dict[str, Any]:
        """Complete plugin build process"""
        build_logs = []
        error_message = None
        repo_url = plugin.get("repo_url")
        branch = plugin.get("branch", "main")
        metadata = plugin.get("metadata", {})
        plugin_id = plugin.get("id")
        plugin_name = plugin.get("name", "unknown")
        version = plugin.get("version", "1.0.0")
        created_at = plugin.get("created_at", "unknown")
        author = plugin.get("author", "unknown")
        description = plugin.get("description", "No description provided")
        has_backend = plugin.get("has_backend", True)
        frontend_folder = plugin.get("frontend_folder", "unknown")
        frontend_build_command = plugin.get("frontend_build_command", "npm run build")
        backend_folder = plugin.get("backend_folder", "unknown")
        backend_deploy_command = plugin.get("backend_deploy_command")
        cloned_dir = None

        try:
            plugin_unique_name = self.unique_name(plugin_name)
            logger.info("Plugin unique name is %s", plugin_unique_name)
            metadata["expose"] = plugin_unique_name
            # Step 0: Check for existing metadata
            logger.info("Step 0: Checking for existing plugin metadata...")

            # Step 1: Clone the repository or use local path
            if self.is_git_url(repo_url):
                logger.info("Step 1: Cloning repository...")
                project_dir = self.clone_repository(repo_url, branch)
                cloned_dir = project_dir  # Mark for cleanup
                logger.info(f"Repository cloned to: {cloned_dir}")
            else:
                logger.info("Step 1: Cloning repository...")
                logger.info(f"DEBUG: repo_url = '{repo_url}' (type: {type(repo_url)}, length: {len(repo_url)})")
                logger.info(f"DEBUG: repo_url.startswith('./plugins/') = {repo_url.startswith('./plugins/')}")
                logger.info(f"DEBUG: repo_url.startswith('/plugins/') = {repo_url.startswith('/plugins/')}")

                # For local paths, map them to the mounted volume
                # If the path starts with ./plugins or /plugins, use it as-is
                # Otherwise, assume it's a relative path under /plugins
                if repo_url.startswith("./plugins/"):
                    logger.info("DEBUG: Taking ./plugins/ branch")
                    # Convert relative path to absolute within container
                    plugin_name = repo_url.replace("./plugins/", "")
                    project_dir = Path(f'/plugins/{plugin_name}')
                elif repo_url.startswith('/plugins/'):
                    logger.info("DEBUG: Taking /plugins/ branch")
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

            # Step 2: Check if it's an npm project and extract metadata
            logger.info("Step 2: Checking if the frontend is an npm project...")
            if has_backend:
                frontend_path = project_dir / frontend_folder
            else:
                frontend_path = project_dir
            if not self.check_npm_project(frontend_path):
                raise RuntimeError("No package.json found - not an npm project")
            logger.info("npm project detected")

            # Step 2.1: update vite.config.js
            logger.info("Step 2.1: Updating vite.config.js...")
            self.update_vite_config(frontend_path, metadata["expose"])
            logger.info("vite.config.js updated successfully")

            # Step 2.2: update plugin version base on plugin frontend package.json version
            logger.info("Step 2.2: Updating plugin version...")
            new_version = self.update_plugin_version(frontend_path, plugin_id)
            version = new_version if new_version is not None else version

            # Step 3: npm install
            logger.info("Step 3: Running npm install")
            install_result = self.frontend_install(frontend_path)
            if not install_result["success"]:
                raise RuntimeError(f"npm install failed: {install_result.get('error', 'Unknown error')}")
            logger.info("npm install completed successfully")

            # Step 4: npm build
            logger.info("Step 4: Running npm build...")
            build_result = self.frontend_build(frontend_path, frontend_build_command)
            if not build_result["success"]:
                raise RuntimeError(f"npm build failed: {build_result.get('error', 'Unknown error')}")
            logger.info("npm build completed successfully")

            # Step 5: replace the path in the umd.js file (only for remote repos, not local)
            if cloned_dir:
                logger.info("Step 5: Replacing path in umd.js file...")
                self.replace_path_in_umd_js(project_dir, has_backend, metadata["expose"], frontend_folder)
                logger.info("Path in umd.js file replaced successfully")
            else:
                logger.info("Step 5: Skipping path replacement for local plugin...")

            # read config file in the cloned directory
            config_file = project_dir / "config.portal.json"
            config = {}
            if config_file.exists():
                logger.info(f"Reading config from {config_file}")
                with open(config_file, "r") as f:
                    config = json.loads(f.read())
            else:
                logger.warning(f"No config.portal.json found in {project_dir}")

            # Step 5: Create SPARC dataset (only for remote repos)
            dataset_dir = None
            if cloned_dir:
                logger.info("Step 5: Creating SPARC dataset by sparc-me")

                # Look for common build output directories
                build_output_dir = None
                possible_build_dir = ["dist", "build"]
                for dir_name in possible_build_dir:
                    potential_dir = frontend_path / dir_name
                    if potential_dir.exists():
                        build_output_dir = potential_dir
                        logger.info(f"Found build output directory: {build_output_dir}")
                        break

                dataset_dir = self.create_sparc_dataset(project_dir, has_backend, build_output_dir,
                                                        f"sparc-{plugin_unique_name}")
                logger.info(f"SPARC dataset created in {dataset_dir}")
            else:
                logger.info("Step 5: Skipping SPARC dataset creation for local plugin...")

            # Step 6: Upload dataset to MinIO or copy to public folder
            s3_path = None
            minio_client = get_minio_client()
            if cloned_dir:
                logger.info("Step 6: Uploading dataset to MinIO...")
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
                logger.info("Step 6: Copying local tool plugin to public directory")
                # For local tool plugins, copy dist files to public directory using the path from metadata
                pass

            # Step 7: Clean up temporary files (only for cloned repos, not local paths)
            logger.info("Step 7: Cleaning up temporary files")
            if cloned_dir:
                try:
                    force_rmtree(cloned_dir)
                    logger.info("Cleaning up cloned repository")
                    force_rmtree(dataset_dir)
                    logger.info("Cleaning up sparc dataset")
                except Exception as e:
                    logger.error(f"Failed to remove cloned repository: {e}")
            else:
                logger.info("Skiping cleanup for local path")

            # Step 8: update metadata.json in MinIO
            # Determine the path based on whether it's a local plugin or remote
            if cloned_dir:
                # Remote plugin - use public directory path with metadata path
                plugin_path = f"http://{os.environ.get('HOST', 'localhost')}:9000/{os.environ.get('MINIO_BUCKET_NAME', 'workflow-tools')}/{metadata['expose']}/primary/my-app.umd.js"
                if has_backend:
                    backend_path = f"http://{os.environ.get('HOST', 'localhost')}:9000/{os.environ.get('MINIO_BUCKET_NAME', 'workflow-tools')}/{metadata['expose']}/code/{backend_folder}"
            else:
                # Local plugin - use public directory path with metadata expose folder name
                plugin_path = f"/{metadata['expose']}/my-app.umd.js"

            component_entry = {
                "uuid": "",
                "id": plugin_id,
                "name": plugin_name,
                "path": plugin_path,
                "expose": metadata.get("expose", "MyApp"),
                "description": description,
                "version": version,
                "created_at": created_at,
                "author": author,
                "repository_url": repo_url,
                "is_local": not bool(cloned_dir),
                "frontend_folder": frontend_folder,
                "has_backend": has_backend,
                "backend_folder": backend_folder if has_backend else None,
                "backend_deploy_command": backend_deploy_command if has_backend else None,
                "config": config
            }
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

            logger.info("Build process completed successfully")

            return {
                "success": True,
                "dataset_path": str(dataset_dir) if dataset_dir else None,
                "s3_path": s3_path,
                "build_logs": "\n".join(build_logs),
                "error_message": None,
                "is_local": not bool(cloned_dir)
            }
        except Exception as e:
            error_message = str(e)
            logger.info(f"Build failed: {error_message}")
            logger.error(f"Build process failed: {e}")

            return {
                "success": False,
                "dataset_path": None,
                "build_logs": "\n".join(build_logs),
                "error_message": error_message
            }
