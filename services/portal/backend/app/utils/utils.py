import os
import stat
import shutil
from pathlib import Path


def force_rmtree(path: Path, keep_folder: bool = False):
    """
    Forcefully delete a directory or all files within it.
    - If keep_folder=False (default), the entire directory will be deleted (same as shutil.rmtree).
    - If keep_folder=True, only the files and subdirectories inside the directory will be removed, while keeping the directory itself.
    """
    def onerror(func, p, exc_info):
        if not os.access(p, os.W_OK):
            os.chmod(p, stat.S_IWRITE)
            func(p)
        else:
            raise

    if not path.exists():
        return

    if keep_folder:
        for child in path.iterdir():
            if child.is_dir():
                shutil.rmtree(child, onerror=onerror)
            else:
                os.remove(child)
        (path / ".gitkeep").touch(exist_ok=True)
    else:
        shutil.rmtree(path, onerror=onerror)
