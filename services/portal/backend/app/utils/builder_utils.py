from __future__ import annotations
import json
import os
import subprocess
import uuid
import zipfile
from pathlib import Path
import logging
import shutil
from app.utils.utils import force_rmtree, safe_path
import re
from typing import Dict, Any, Union, Type, TYPE_CHECKING, Optional
import threading
from app.models.db_model import (
    BuildStatus, SessionLocal, PluginBuild, WorkflowBuild)
from datetime import datetime
from fastapi import BackgroundTasks
from app.builder.logger import get_logger

logger = get_logger(__name__)

if TYPE_CHECKING:
    from app.builder.build_tool import PluginBuilder
    from app.builder.build_workflow import WorkflowBuilder

def clone_repository(
    tmp_dir: Path,
    repo_url: str,
    logger: logging.Logger,
    branch: str = "main",
    *,
    shallow: bool = False,
    env_overrides: Optional[Dict[str, str]] = None,
) -> Path:
    """Clone a git repository to a temporary directory.

    `shallow=True` adds `--depth 1` — used by metadata probe paths where we
    only need the working tree, not history.

    `env_overrides` merges with ``os.environ`` for the subprocess (used by
    callers that need to set ``GIT_SSL_NO_VERIFY`` for self-signed certs,
    or any other one-off git env tweak). Pass ``None`` to inherit the parent
    environment unchanged.
    """
    try:
        clone_dir = tmp_dir / f"build_{uuid.uuid4().hex[:8]}"
        clone_dir.mkdir(exist_ok=True)
        if not repo_url.endswith(".git"):
            repo_url += ".git"
        cmd = ["git", "clone"]
        if shallow:
            cmd += ["--depth", "1"]
        cmd += ["--branch", branch, repo_url, str(clone_dir)]
        logger.info(f"Cloning repository {repo_url} to {clone_dir} (shallow={shallow})")
        env = {**os.environ, **env_overrides} if env_overrides else None
        subprocess.run(cmd, capture_output=True, text=True, check=True, env=env)
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
        shutil.copytree(safe_path(src), safe_path(dst / src.name), dirs_exist_ok=True)
    else:
        try:
            shutil.copy2(safe_path(src), safe_path(dst / src.name))
        except Exception as e:
            logger.error(f"Failed to copy item {src} to {dst}: {e}")


# Directories that should never appear inside a plugin source archive.
# We filter at extraction time as a belt-and-suspenders measure (client also filters).
_ARCHIVE_BLACKLIST_PREFIXES = ("node_modules/", ".git/", "dist/", "build/")
_ARCHIVE_BLACKLIST_NAMES = {"node_modules", ".git", "dist", "build"}


def _archive_entry_blacklisted(name: str) -> bool:
    """Return True if a zip entry path lives under a blacklisted directory at any depth."""
    parts = name.split("/")
    return any(p in _ARCHIVE_BLACKLIST_NAMES for p in parts if p)


def extract_uploaded_archive(
    tmp_dir: Path,
    archive_path: Path,
    max_total_bytes: int = 500 * 1024 * 1024,
) -> Path:
    """Extract a user-uploaded zip into a fresh staging directory under tmp_dir.

    Safety:
    - zip-slip: every resolved entry path must remain inside the target
    - zip-bomb: sum of declared uncompressed sizes must not exceed max_total_bytes
    - blacklist: skip entries under node_modules / .git / dist / build at any depth

    Returns the staging directory Path.
    """
    target = tmp_dir / f"upload_{uuid.uuid4().hex[:8]}"
    target.mkdir(parents=True, exist_ok=False)
    target_resolved = target.resolve()

    with zipfile.ZipFile(archive_path) as zf:
        infos = zf.infolist()
        total = sum(info.file_size for info in infos if not info.is_dir())
        if total > max_total_bytes:
            shutil.rmtree(target, ignore_errors=True)
            raise ValueError(
                f"Archive too large after extraction ({total} bytes > {max_total_bytes} bytes limit)"
            )

        for info in infos:
            name = info.filename
            if not name or name.endswith("/"):
                continue
            if _archive_entry_blacklisted(name):
                continue

            dest = (target / name).resolve()
            try:
                dest.relative_to(target_resolved)
            except ValueError:
                shutil.rmtree(target, ignore_errors=True)
                raise ValueError(f"Unsafe archive entry escapes target: {name}")

            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)

    return target


def _find_shallowest_package_json(root: Path) -> Optional[Path]:
    """Walk the tree under ``root`` and return the shallowest non-blacklisted
    ``package.json`` (or ``None`` if no manifest exists).

    Blacklisted dirs are pruned from the walk so we never descend into
    ``node_modules`` etc. — both for performance and to avoid picking up a
    transitive dep's manifest.
    """
    best: Optional[Path] = None
    best_depth = -1
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _ARCHIVE_BLACKLIST_NAMES]
        if "package.json" not in filenames:
            continue
        candidate = Path(dirpath) / "package.json"
        depth = len(candidate.relative_to(root).parts)
        if best is None or depth < best_depth:
            best = candidate
            best_depth = depth
    return best


def resolve_project_root(staging_dir: Path) -> Path:
    """Walk down through single-wrapper directories until we hit the real project root.

    A "wrapper" is a directory whose only contents are exactly one subdirectory
    and no files. Stripping wrappers iteratively handles both GitHub-style
    ``repo-main/...`` zips and accidental nested cases like
    ``outer/inner/project/...``, so the returned path always points at the
    directory containing ``package.json`` / ``.cwl`` / etc.

    Bounded to 20 iterations to defend against pathological structures.
    """
    current = staging_dir
    for _ in range(20):
        children = [c for c in current.iterdir() if c.name != "__MACOSX"]
        dirs = [c for c in children if c.is_dir()]
        files = [c for c in children if c.is_file()]
        if len(dirs) == 1 and not files:
            current = dirs[0]
        else:
            break
    return current


def inspect_uploaded_source(
    staging_dir: Path,
    *,
    want_npm: bool,
    want_cwl: bool,
) -> Dict[str, Any]:
    """Scan a freshly extracted staging dir and return metadata for the frontend form.

    - folders_in_root: top-level directory names (excluding blacklist)
    - package_version / package_author: extracted from root package.json if present
    - has_cwl: True if any .cwl file exists at root
    """
    root = resolve_project_root(staging_dir)

    folders_in_root: list[str] = []
    has_cwl = False
    pkg_version = ""
    pkg_author = ""

    for entry in root.iterdir():
        if entry.name in _ARCHIVE_BLACKLIST_NAMES:
            continue
        if entry.is_dir():
            folders_in_root.append(entry.name)
        elif entry.is_file() and entry.suffix == ".cwl":
            has_cwl = True

    if want_npm:
        # Search recursively for package.json (excluding blacklisted dirs) and
        # pick the shallowest. Mirrors the GitHub-mode behaviour of scanning
        # the whole tree rather than only the project root, so plugins that
        # keep their npm manifest under e.g. `frontend/` still resolve.
        pkg_path = _find_shallowest_package_json(root)
        if pkg_path is not None:
            try:
                with open(pkg_path, "r", encoding="utf-8") as f:
                    pkg = json.load(f)
                if isinstance(pkg.get("version"), str):
                    pkg_version = pkg["version"]
                author = pkg.get("author")
                if isinstance(author, str):
                    pkg_author = author
                elif isinstance(author, dict) and isinstance(author.get("name"), str):
                    pkg_author = author["name"]
            except Exception as e:
                logger.warning(f"Failed to parse {pkg_path}: {e}")

    return {
        "root": str(root),
        "folders_in_root": folders_in_root,
        "package_version": pkg_version,
        "package_author": pkg_author,
        "has_cwl": has_cwl,
        "cwl_required": want_cwl,
    }


def read_root_cwl(staging_dir: Path) -> Optional[Dict[str, str]]:
    """Read the first .cwl file at the root of the (possibly nested) staging dir.
    Returns {"cwl_file": <name>, "content": <raw text>} or None if not found.
    """
    root = resolve_project_root(staging_dir)
    for entry in sorted(root.iterdir()):
        if entry.is_file() and entry.suffix == ".cwl":
            try:
                with open(entry, "r", encoding="utf-8") as f:
                    return {"cwl_file": entry.name, "content": f.read()}
            except Exception as e:
                logger.error(f"Failed to read CWL {entry}: {e}")
                return None
    return None


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
