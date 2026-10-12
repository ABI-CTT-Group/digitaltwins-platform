"""Register a model dataset in Postgres + MinIO and store its optional FHIR annotation."""
from pathlib import Path
from typing import Any, Dict, Optional

from .. import models
from ..core.connection import Connection
from ..core.uploader import Uploader
from ..measurements.pipeline import CommitResult, save_annotation
from . import fhir


def commit_model(
    dataset_root: Path,
    dataset_name: Optional[str] = None,
    descriptions: Optional[Dict[str, Any]] = None,
    default_description: str = "",
) -> CommitResult:
    """Store the model dataset; with ``descriptions``, stamp and store its annotation.

    Subject/sample rows come from ``subjects.xlsx`` / ``samples.xlsx`` only:
    a model's ``primary/`` holds model files, not ``<subject>/<sample>`` folders.
    """
    dataset_uuid = Uploader().upload_dataset(str(dataset_root), category=models.CATEGORY, dataset_name=dataset_name)
    if descriptions is None:
        return CommitResult(dataset_uuid, None)
    stamped = fhir.build_descriptions(dataset_uuid, dataset_name or "", descriptions, default_description)
    conn, _ = Connection().connect()
    try:
        save_annotation(conn, dataset_uuid, stamped)
    finally:
        conn.close()
    return CommitResult(dataset_uuid, stamped)
