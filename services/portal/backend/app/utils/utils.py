import os
import stat
import shutil
from pathlib import Path
from typing import Any
import math
import platform
from app.builder.logger import get_logger

logger = get_logger(__name__)

def force_rmtree(path: Path, keep_folder: bool = False, keep_gitkeep: bool = True):
    """
    Recursively delete a directory or its contents in a cross-platform safe way.

    Args:
        path: Path object for the directory to delete.
        keep_folder: If True, only deletes contents, keeps the folder itself.
        keep_gitkeep: If True and keep_folder=True, keeps a `.gitkeep` file inside.
    """
    def onerror(func, p, exc_info):
        """Error handler for shutil.rmtree: fixes read-only files."""
        try:
            if not os.access(p, os.W_OK):
                os.chmod(p, stat.S_IWRITE)
                func(p)
            else:
                raise
        except Exception as e:
            logger.error(f"Failed to handle error on {p}: {e}")
            raise

    path = Path(path)
    if not path.exists():
        logger.info(f"Path does not exist: {path}")
        return

    try:
        if keep_folder:
            # Delete all contents
            for child in path.iterdir():
                child_path = Path(safe_path(child))
                if child.is_dir():
                    shutil.rmtree(child_path, onerror=onerror)
                else:
                    os.remove(child_path)
            # Keep .gitkeep if requested
            if keep_gitkeep:
                (path / ".gitkeep").touch(exist_ok=True)
        else:
            # Delete the entire folder
            shutil.rmtree(Path(safe_path(path)), onerror=onerror)
        logger.info(f"Deleted {'contents of' if keep_folder else ''} folder: {path}")
    except Exception as e:
        logger.error(f"Failed to remove path {path}: {e}")
        raise


def is_empty(value: Any) -> bool:
    if isinstance(value, str):
        return value.strip() == ""

    if isinstance(value, (float, int)):
        return math.isnan(value) if isinstance(value, float) else False

    return not bool(value)


def safe_path(p: Path) -> str:
    """
    Return a string safe for long paths on Windows, normal string on other OS.
    """
    p = p.resolve()
    if platform.system() == "Windows":
        s = str(p)
        if not s.startswith("\\\\?\\"):
            s = s.replace("/", "\\")
            s = "\\\\?\\" + s
        return s
    else:
        return str(p)


def safe_open(path: Path, mode="rb"):
    """
    Open a file safely on Windows for long paths.
    On Windows, adds \\?\ prefix if needed.
    On other OS, normal open.
    """
    p = path.resolve()
    if platform.system() == "Windows":
        s = str(p)
        if not s.startswith("\\\\?\\"):
            s = "\\\\?\\" + s
        return open(s, mode)
    else:
        return open(p, mode)
