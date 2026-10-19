"""Staging volume layout (``DATASET_STAGING_DIR``, default ``./dataset_staging``).

    <root>/chunks/upload_<upload_id>/   chunk-store parts (see chunk_store.py)
    <root>/datasets/<upload_id>/        validated dataset root: staged until commit,
                                        then kept as the local cache for FHIR build
"""
import os
from pathlib import Path


def staging_root() -> Path:
    return Path(os.getenv("DATASET_STAGING_DIR", "./dataset_staging"))


def chunk_root() -> Path:
    return staging_root() / "chunks"


def dataset_dir(upload_id: str) -> Path:
    return staging_root() / "datasets" / str(upload_id)


def max_upload_bytes() -> int:
    """Largest dataset accepted, unzipped (``MAX_UPLOAD_MB``, default 20 GiB)."""
    try:
        mb = int(os.getenv("MAX_UPLOAD_MB", "20480"))
    except ValueError:
        mb = 20480
    return max(mb, 1) * 1024 * 1024
