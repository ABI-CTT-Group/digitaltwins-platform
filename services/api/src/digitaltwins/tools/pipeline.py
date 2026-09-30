"""Commit a tool dataset: Postgres + MinIO, then its SEEK Workflow, as one unit."""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .. import tools
from ..core.connection import Connection
from ..core.deleter import Deleter
from ..core.uploader import Uploader
from ..seek.writer import Writer
from .validation import find_tool_cwl

logger = logging.getLogger(__name__)


class SeekRegistrationError(RuntimeError):
    """SEEK registration failed; the dataset stored before it has been removed again."""


def _set_seek_id(dataset_uuid: str, seek_id: int) -> None:
    conn, _ = Connection().connect()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE dataset SET seek_id = %s WHERE dataset_uuid = %s", (str(seek_id), dataset_uuid))
        conn.commit()
    finally:
        conn.close()


def commit_tool(
    dataset_root: Path,
    tool_type: str,
    seek_project_id: int,
    api_token: str,
    dataset_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Store the tool dataset, register it in SEEK as the caller, link the two.

    Postgres + MinIO go first (``Uploader`` commits them together); if SEEK
    registration or the link then fails, the dataset (and any SEEK workflow
    already created) is removed and ``SeekRegistrationError`` raised.
    """
    cwl_path = find_tool_cwl(dataset_root)
    dataset_uuid = Uploader().upload_dataset(str(dataset_root), category=tools.CATEGORY, dataset_name=dataset_name)
    seek_id = None
    try:
        writer = Writer(api_token=api_token)
        seek_id = writer.register_tool(cwl_path, tool_type, seek_project_id)
        _set_seek_id(dataset_uuid, seek_id)
    except Exception as exc:
        logger.exception("SEEK registration failed for tool dataset %s; rolling back", dataset_uuid)
        if seek_id is not None:
            try:
                writer.delete_workflow(seek_id)
            except Exception:
                logger.warning("Could not remove SEEK workflow %s after a failed link", seek_id)
        Deleter().delete_dataset(dataset_uuid)
        raise SeekRegistrationError(f"SEEK registration failed; nothing was stored: {exc}") from exc
    return {"dataset_uuid": dataset_uuid, "seek_id": seek_id}
