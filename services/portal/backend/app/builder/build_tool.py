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
from dotenv import dotenv_values

from app.utils.utils import force_rmtree

from sparc_me import Dataset
from .logger import get_logger
from app.client.minio import get_minio_client
from sqlalchemy.orm import Session
from app.models.db_model import Plugin, SessionLocal
from app.utils.builder_utils import (
    clone_repository,
    copy_item,
    remove_tmp_folder,
    unique_name)

logger = get_logger(__name__)


class PluginBuilder:
    """Handles building plugins using git CLI and npm"""

    def __init__(self, dataset_dir: str = None, db: Optional[Session] = None):
        if dataset_dir is None:
            # Use environment variable or default to ./dataset for local, /datasets for Docker
            dataset_dir = os.environ.get('DATASET_DIR_TOOL', "./datasets_tool")
        self.tmp_dir = Path("./tmp")
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.dataset_dir = Path(dataset_dir)
        self.dataset_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def check_npm_project(project_dir: Path) -> bool:
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
                             label: str,
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

            logger.info(f"the tool label is {label}")
            if label == "GUI":
                if has_backend:
                    for layer in project_dir.iterdir():
                        if layer.name == ".git":
                            continue
                        if layer.is_dir():
                            for item in layer.iterdir():
                                dest = code_dir / layer.name
                                dest.mkdir(exist_ok=True)
                                copy_item(item, dest)
                        else:
                            copy_item(layer, code_dir)
                else:
                    for item in project_dir.iterdir():
                        if item.name == ".git":
                            continue
                        copy_item(item, code_dir)

                if build_output_dir and build_output_dir.exists():
                    primary_dir = dataset_dir / "primary"
                    primary_dir.mkdir(exist_ok=True)

                    for item in build_output_dir.iterdir():
                        if item.is_dir() and item.name != ".git":
                            shutil.copytree(item, primary_dir / item.name, dirs_exist_ok=True)
                        else:
                            shutil.copy2(item, primary_dir / item.name)

                    logger.info(f"Copied build artifacts from {build_output_dir} to {primary_dir}")
            else:
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

    @staticmethod
    def _replace_vite_build_config(file_path: Path, new_name: str) -> bool:
        """
        Replace `name`, `formats`, and `fileName` fields in a Vite config file.
        Only replaces 'name' inside the lib: { ... } block to avoid corrupting
        other 'name' fields (e.g. globalName in replaceNamedImportsFromGlobals).

        Returns True if successful, False otherwise.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()

            replaced = {"name": False, "formats": False, "fileName": False}

            # Replace 'name' ONLY inside the lib: { ... } block.
            # Pattern: find `lib: {` then the first `name: 'xxx'` inside it.
            # We use a multi-step approach: locate the lib block, replace name inside it only.
            def replace_lib_name(text: str) -> str:
                # Match lib: { ... } block (non-greedy, handles multi-line)
                lib_block_pattern = re.compile(
                    r'(lib\s*:\s*\{)(.*?)((?=\}[\s\r\n]*,)|\})',
                    re.DOTALL
                )
                name_in_lib_pattern = re.compile(r'(name\s*:\s*)["\']([^"\']*)["\']')

                def lib_replacer(m):
                    replaced["name"] = True
                    prefix = m.group(1)
                    body = m.group(2)
                    suffix = m.group(3)
                    # Replace name inside the lib block
                    new_body = name_in_lib_pattern.sub(
                        lambda nm: f"{nm.group(1)}'{new_name}'",
                        body,
                        count=1
                    )
                    return prefix + new_body + suffix

                return lib_block_pattern.sub(lib_replacer, text, count=1)

            content = replace_lib_name(content)

            # Replace formats (safe — unique enough in context)
            formats_pattern = re.compile(r'formats:\s*\[.*?]', re.IGNORECASE | re.DOTALL)

            def formats_replacer(match):
                replaced["formats"] = True
                return "formats: ['umd']"

            content = formats_pattern.sub(formats_replacer, content)

            # Replace fileName (safe — unique enough in context)
            filename_pattern = re.compile(r'fileName\s*:\s*\(format\)\s*=>\s*`[^`]*`', re.IGNORECASE)

            def filename_replacer(match):
                replaced["fileName"] = True
                return "fileName: (format) => `my-app.${format}.js`"

            content = filename_pattern.sub(filename_replacer, content)

            # Write back to file
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(content)

            logger.info(f"Updated vite build config in {file_path}: {replaced}")
            return True
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return False


    # Required externalized deps for the portal's per-app Pinia isolation contract.
    # If a plugin bundles its own copy of `pinia`, the per-app `createPinia()` instance
    # in RemoteComponentApp.vue will NOT be the same library instance the plugin uses,
    # so `defineStore` lookups fall back to a stray module-scope instance and isolation
    # silently breaks. Same reasoning for `vue` (provide/inject + reactivity identity)
    # and `vuetify` / `vue-toastification` (singleton plugins shared with the host).
    _REQUIRED_EXTERNALIZED_DEPS = ("vue", "pinia", "vuetify", "vue-toastification")

    @staticmethod
    def _build_store_namespace_plugin_snippet(expose_name: str) -> str:
        """
        Build the inline Vite plugin source that rewrites `defineStore('foo', ...)`
        into `defineStore('<expose>__foo', ...)` at transform time.

        We deliberately keep this plugin string-injected (not a separate npm package)
        so plugin authors don't need to add a dev-dependency.

        Limitations:
        - Only literal-string IDs are rewritten (single or double quotes).
          `defineStore(useFooId, ...)` and template-literal IDs are left untouched —
          per-app Pinia in the portal is the primary isolation; this rewrite is just
          a secondary safety net.
        - Skips files inside `node_modules`.
        - Idempotent: store IDs that already start with the expose prefix are kept as-is.
        """
        # Sanitize: expose_name is already produced by `unique_name(plugin_name)` and
        # safe for JS identifiers, but defend against quote injection regardless.
        safe_expose = re.sub(r"[^A-Za-z0-9_\-]", "", expose_name)
        return (
            "    {\n"
            "      name: 'portal-plugin-store-namespace',\n"
            "      enforce: 'pre',\n"
            "      transform(code, id) {\n"
            "        if (!/\\.(ts|tsx|js|jsx|mjs|cjs|vue)(\\?.*)?$/.test(id)) return null;\n"
            "        if (id.indexOf('node_modules') !== -1) return null;\n"
            "        if (code.indexOf('defineStore(') === -1) return null;\n"
            f"        var __ns = '{safe_expose}__';\n"
            "        var changed = false;\n"
            "        var out = code.replace(\n"
            "          /defineStore\\(\\s*(['\"])([^'\"]+?)\\1/g,\n"
            "          function (m, q, sid) {\n"
            "            if (sid.indexOf(__ns) === 0) return m;\n"
            "            changed = true;\n"
            "            return 'defineStore(' + q + __ns + sid + q;\n"
            "          }\n"
            "        );\n"
            "        if (!changed) return null;\n"
            "        return { code: out, map: null };\n"
            "      }\n"
            "    },\n"
        )

    @classmethod
    def _inject_store_namespace_plugin(cls, vite_config_file: Path, expose_name: str) -> bool:
        """
        Inject the per-expose store-namespacing Vite plugin at the head of the
        first `plugins: [` array in the plugin's vite.config.

        Returns True if injected (or already present), False if no `plugins: [`
        array could be located. Failure is non-fatal — the portal's per-app
        Pinia isolation still applies, just without the secondary expose-prefix
        safety net.
        """
        try:
            content = vite_config_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read {vite_config_file} for store namespace injection: {e}")
            return False

        if "portal-plugin-store-namespace" in content:
            logger.info(f"Store namespace plugin already present in {vite_config_file}; skipping")
            return True

        snippet = cls._build_store_namespace_plugin_snippet(expose_name)
        plugins_pattern = re.compile(r"plugins\s*:\s*\[")
        match = plugins_pattern.search(content)
        if not match:
            logger.warning(
                f"Could not locate `plugins: [...]` array in {vite_config_file}; "
                f"skipping store-id namespace injection. Per-app Pinia isolation in "
                f"the portal still applies — this only loses the secondary expose-prefix safety net."
            )
            return False

        insertion_pos = match.end()
        new_content = content[:insertion_pos] + "\n" + snippet + content[insertion_pos:]

        try:
            vite_config_file.write_text(new_content, encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to write {vite_config_file} after store namespace injection: {e}")
            return False

        logger.info(
            f"Injected store-id namespace Vite plugin into {vite_config_file} "
            f"with prefix `{expose_name}__`"
        )
        return True

    @classmethod
    def _validate_externalize(cls, vite_config_file: Path) -> None:
        """
        Verify the plugin externalizes vue / pinia / vuetify / vue-toastification.

        Without this, the plugin would bundle its own copy of pinia and the
        per-app Pinia instance the portal creates in RemoteComponentApp.vue
        wouldn't be the instance the plugin's `defineStore` calls bind to —
        cross-plugin state isolation would silently break.

        Heuristic: pool every `external: [...]` array in the file (the plugin
        config commonly has conditional branches — plugin build vs app build),
        then check each required dep appears as a quoted string somewhere in the
        pooled content. Raises RuntimeError on missing deps.
        """
        try:
            content = vite_config_file.read_text(encoding="utf-8")
        except Exception as e:
            logger.error(f"Failed to read {vite_config_file} for externalize validation: {e}")
            raise RuntimeError(f"Cannot validate vite config: {e}")

        external_pattern = re.compile(r"external\s*:\s*\[([^\]]*)\]", re.DOTALL)
        external_blocks = external_pattern.findall(content)

        if not external_blocks:
            raise RuntimeError(
                "Plugin vite.config has no `external: [...]` array under rollupOptions. "
                "For the portal's per-app Pinia isolation to work, the plugin must "
                "externalize vue, pinia, vuetify, and vue-toastification so that the "
                "plugin and portal share the same library code while each plugin instance "
                "gets its own Pinia store registry. "
                "Add `rollupOptions: { external: ['vue', 'vuetify', 'pinia', 'vue-toastification'], "
                "output: { globals: { vue: 'Vue', vuetify: 'Vuetify', pinia: 'Pinia', "
                "'vue-toastification': 'VueToastification' } } }` to the lib build config."
            )

        pooled = " ".join(external_blocks)
        missing = [
            dep for dep in cls._REQUIRED_EXTERNALIZED_DEPS
            if not re.search(rf"['\"]{re.escape(dep)}['\"]", pooled)
        ]
        if missing:
            raise RuntimeError(
                f"Plugin vite.config does not externalize required dependencies: {missing}. "
                f"Without this, the portal's per-app Pinia isolation will fail — the plugin "
                f"would bundle its own copy of pinia and the per-app `createPinia()` instance "
                f"in RemoteComponentApp.vue would not be the instance the plugin's "
                f"`defineStore` calls bind to. "
                f"Add these names as quoted strings to `rollupOptions.external`: "
                f"{list(cls._REQUIRED_EXTERNALIZED_DEPS)}."
            )

        logger.info(f"Externalize validation passed for {vite_config_file}")

    def _update_vite_config(self, project_dir: Path, plugin_expose_name: str):
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

        self._replace_vite_build_config(vite_config_file, plugin_expose_name)
        self._inject_store_namespace_plugin(vite_config_file, plugin_expose_name)
        self._validate_externalize(vite_config_file)

    @staticmethod
    def _update_plugin_version(project_dir: Path, plugin_id: str):
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

    @staticmethod
    def _create_env_file(project_dir: Path, expose_name: str):
        config = {
            "VITE_PLUGIN_ROUTE_PREFIX": f"/plugin/{expose_name}"
        }
        env_path = project_dir / ".env"
        if env_path.exists():
            env = dotenv_values(env_path)
            # Remove legacy env vars that are no longer needed in production builds
            env.pop("VITE_PLUGIN_API_URL", None)
            env.pop("VITE_PLUGIN_API_PORT", None)
            config.update(env)
        else:
            env_path.touch(exist_ok=True)
        with open(env_path, "w", encoding="utf-8") as f:
            for key, val in config.items():
                f.write(f"{key}={val}\n")
        logger.info(f"Updated env file in {env_path} with route prefix /plugin/{expose_name}")

    def build(self, plugin: Dict[str, Any]) -> Dict[str, Any]:
        """Complete plugin build process"""
        build_logs = []
        error_message = None
        repo_url = plugin.get("repo_url")
        branch = plugin.get("branch", "main")
        metadata = plugin.get("metadata", {})
        plugin_id = plugin.get("id")
        plugin_name = plugin.get("name", "unknown")
        version = plugin.get("version", "1.0.0")
        label = plugin.get("label", "GUI")
        created_at = plugin.get("created_at", "unknown")
        author = plugin.get("author", "unknown")
        description = plugin.get("description", "No description provided")
        has_backend = plugin.get("has_backend", True)
        frontend_folder = plugin.get("frontend_folder", "unknown")
        frontend_build_command = plugin.get("frontend_build_command", "npm run build")
        backend_folder = plugin.get("backend_folder", "unknown")
        backend_deploy_command = plugin.get("backend_deploy_command")
        source_type = plugin.get("source_type", "github")
        local_archive_path = plugin.get("local_archive_path")
        tmp_source_dir = None
        config = {}

        try:
            plugin_unique_expose_name = unique_name(plugin_name)
            logger.info("Plugin unique name is %s", plugin_unique_expose_name)
            metadata["expose"] = plugin_unique_expose_name
            # Step 0: Check for existing metadata
            logger.info("Step 0: Checking for existing plugin metadata...")

            # Step 1: Acquire project_dir. Both branches own a temp dir and assign
            # tmp_source_dir so steps 5/6/7 (SPARC + MinIO upload + cleanup) trigger uniformly.
            if source_type == "local":
                logger.info("Step 1: Using uploaded local archive...")
                if not local_archive_path:
                    raise RuntimeError("source_type='local' but local_archive_path is missing")
                project_dir = Path(local_archive_path)
                if not project_dir.exists() or not project_dir.is_dir():
                    raise RuntimeError(f"Local staging dir not found: {project_dir}")
                tmp_source_dir = project_dir
                logger.info(f"Using uploaded source from: {project_dir}")
            elif source_type == "github":
                logger.info("Step 1: Cloning repository...")
                project_dir = clone_repository(self.tmp_dir, repo_url, logger, branch)
                tmp_source_dir = project_dir  # Mark for cleanup
                logger.info(f"Repository cloned to: {tmp_source_dir}")
            else:
                raise ValueError(f"Unknown source_type: {source_type!r} (expected 'github' or 'local')")

            # If the tool is a script, skip some of the steps below.
            if label == "GUI":
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
                self._update_vite_config(frontend_path, metadata["expose"])
                logger.info("vite.config.js updated successfully")

                # Step 2.2: update plugin version base on plugin frontend package.json version
                logger.info("Step 2.2: Updating plugin version...")
                new_version = self._update_plugin_version(frontend_path, plugin_id)
                version = new_version if new_version is not None else version

                # Step 2.3: create .env file with route prefix for nginx proxy
                if has_backend:
                    logger.info("Step 2.3: Create .env file for frontend...")
                    self._create_env_file(frontend_path, plugin_unique_expose_name)

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

                # read config file in the cloned directory
                config_file = project_dir / "config.portal.json"

                if config_file.exists():
                    logger.info(f"Reading config from {config_file}")
                    with open(config_file, "r") as f:
                        config = json.loads(f.read())
                else:
                    logger.warning(f"No config.portal.json found in {project_dir}")

                # Step 5: Create SPARC dataset
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

                dataset_dir = self.create_sparc_dataset(project_dir, label, has_backend, build_output_dir,
                                                        f"{plugin_unique_expose_name}")
                logger.info(f"SPARC dataset created in {dataset_dir}")
            else:
                # Step 5: Create SPARC dataset for cwl plugin script
                logger.info("Step 5: Creating SPARC dataset by sparc-me")
                dataset_dir = self.create_sparc_dataset(project_dir, label, has_backend, None,
                                                        f"{plugin_unique_expose_name}")
                logger.info(f"SPARC dataset created in {dataset_dir}")

            # Step 6: Upload dataset to MinIO
            s3_path = None
            minio_client = get_minio_client()
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

            # Step 7: Clean up temporary source directory
            logger.info("Step 7: Cleaning up temporary files")
            try:
                remove_tmp_folder(tmp_source_dir, logger)
            except Exception as e:
                logger.error(f"Failed to remove temporary source directory: {e}")

            logger.info("Build process completed successfully")

            return {
                "success": True,
                "dataset_path": str(dataset_dir),
                "expose_name": plugin_unique_expose_name,
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
