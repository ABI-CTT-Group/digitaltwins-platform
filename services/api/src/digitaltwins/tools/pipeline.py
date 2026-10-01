"""Commit a tool dataset: its SEEK Workflow, then Postgres + MinIO, as one unit."""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from .. import tools
from ..core.connection import Connection
from ..core.deleter import Deleter
from ..core.uploader import Uploader
from ..seek.writer import Writer
from . import fhir as tool_fhir
from .validation import find_tool_cwl

logger = logging.getLogger(__name__)


class SeekRegistrationError(RuntimeError):
    """SEEK registration or linking failed; anything created for the tool has been removed again."""


def _link(dataset_uuid: str, seek_id: int, tool_type: str) -> None:
    conn, _ = Connection().connect()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE dataset SET seek_id = %s, tool_type = %s WHERE dataset_uuid = %s",
                        (str(seek_id), tool_type, dataset_uuid))
        conn.commit()
    finally:
        conn.close()


def _undo(writer: Writer, seek_id: int, dataset_uuid: Optional[str]) -> None:
    """Best-effort rollback; a failure here is logged, never raised over the original error."""
    try:
        writer.delete_workflow(seek_id)
    except Exception:
        logger.warning("Could not remove SEEK workflow %s after a failed tool commit", seek_id)
    if dataset_uuid is not None:
        try:
            Deleter().delete_dataset(dataset_uuid)
        except Exception:
            logger.warning("Could not remove tool dataset %s after a failed tool commit", dataset_uuid)


def commit_tool(
    dataset_root: Path,
    tool_type: str,
    seek_project_id: int,
    api_token: str,
    dataset_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Register the tool in SEEK as the caller, store the dataset, link the two.

    SEEK goes first because the caller's token is short-lived and the MinIO
    upload may not be. If storing or linking then fails, the SEEK workflow (and
    any dataset already stored) is removed again. Subject/sample spreadsheets
    are kept as files but not loaded: tools have no subjects or samples.
    """
    cwl_path = find_tool_cwl(dataset_root)
    try:
        writer = Writer(api_token=api_token)
        seek_id = writer.register_tool(cwl_path, tool_type, seek_project_id)
    except Exception as exc:
        logger.exception("SEEK registration failed for tool dataset %s", dataset_root)
        raise SeekRegistrationError(f"SEEK registration failed; nothing was stored: {exc}") from exc
    dataset_uuid = None
    try:
        dataset_uuid = Uploader().upload_dataset(
            str(dataset_root), category=tools.CATEGORY, dataset_name=dataset_name,
            skip_tables=("subject", "sample"),
        )
        _link(dataset_uuid, seek_id, tool_type)
    except Exception as exc:
        logger.exception("Tool commit failed after SEEK registration (workflow %s); rolling back", seek_id)
        _undo(writer, seek_id, dataset_uuid)
        if dataset_uuid is None:
            raise
        raise SeekRegistrationError(f"Linking the SEEK workflow failed; the upload was rolled back: {exc}") from exc
    return {"dataset_uuid": dataset_uuid, "seek_id": seek_id}


def annotate_tool(conn, dataset_root: Path, dataset_uuid: str,
                  client: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build the committed tool's FHIR descriptions (``client`` or auto) and store them."""
    from ..measurements.pipeline import get_dataset_row, save_annotation

    name = get_dataset_row(conn, dataset_uuid)["dataset_name"] or ""
    descriptions = tool_fhir.build_descriptions(dataset_root, dataset_uuid, name, client)
    save_annotation(conn, dataset_uuid, descriptions)
    return descriptions
