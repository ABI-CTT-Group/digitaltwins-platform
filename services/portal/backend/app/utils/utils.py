import os
import stat
import shutil
from pathlib import Path


def force_rmtree(path: Path):
    """
    Delete entire directories (including read-only files), compatible with Linux/Windows.
    """
    def onerror(func, p, exc_info):
        if not os.access(p, os.W_OK):
            os.chmod(p, stat.S_IWRITE)
            func(p)
        else:
            raise

    if path.exists():
        shutil.rmtree(path, onerror=onerror)
