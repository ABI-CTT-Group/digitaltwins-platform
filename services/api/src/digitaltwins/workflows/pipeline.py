"""Commit a workflow dataset: each of its tools as a tool dataset, then the workflow, as one unit."""
import logging
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .. import tools, workflows
from ..core.connection import Connection
from ..core.deleter import Deleter
from ..core.uploader import Uploader
from ..measurements.staging import staging_root
from ..seek.writer import Writer
from ..tools.pipeline import SeekRegistrationError, link_tool
from .validation import WorkflowLayout, load_workflow

logger = logging.getLogger(__name__)


def _assemble_tool(layout: WorkflowLayout, tool_cwl: Path, parent: Path) -> Path:
    """A tool dataset folder: the workflow's root metadata files, the tool's CWL and its code."""
    root = parent / tool_cwl.stem
    (root / "primary").mkdir(parents=True)
    (root / "code").mkdir()
    for path in layout.root.iterdir():
        if path.is_file():
            shutil.copy2(path, root / path.name)
    shutil.copy2(tool_cwl, root / "primary" / tool_cwl.name)
    for path in layout.tool_code[tool_cwl]:
        if path.is_dir():
            shutil.copytree(path, root / "code", dirs_exist_ok=True)
        else:
            shutil.copy2(path, root / "code" / path.name)
    return root


def _link_workflow(dataset_uuid: str, seek_id: int, workflow_type: str, steps: List[Tuple[str, str]]) -> None:
    """Record the workflow's SEEK id and type, and the tool dataset each step runs."""
    conn, _ = Connection().connect()
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE dataset SET seek_id = %s, workflow_type = %s WHERE dataset_uuid = %s",
                        (str(seek_id), workflow_type, dataset_uuid))
            cur.executemany(
                "INSERT INTO workflow_tool (workflow_dataset_uuid, step_id, tool_dataset_uuid) VALUES (%s, %s, %s)",
                [(dataset_uuid, step_id, tool_uuid) for step_id, tool_uuid in steps],
            )
        conn.commit()
    finally:
        conn.close()


def _undo(writer: Writer, seek_ids: List[int], dataset_uuids: List[str]) -> None:
    """Best-effort rollback, newest first (the workflow before the tools it links to).

    A failure here is logged, never raised over the original error.
    """
    for dataset_uuid in reversed(dataset_uuids):
        try:
            Deleter().delete_dataset(dataset_uuid, delete_tools=False)  # the tools are in dataset_uuids too
        except Exception:
            logger.warning("Could not remove dataset %s after a failed workflow commit", dataset_uuid)
    for seek_id in reversed(seek_ids):
        try:
            writer.delete_workflow(seek_id)
        except Exception:
            logger.warning("Could not remove SEEK workflow %s after a failed workflow commit", seek_id)


def commit_workflow(
    dataset_root: Path,
    workflow_type: str,
    seek_project_id: int,
    api_token: str,
    dataset_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Register the workflow and its tools in SEEK as the caller, store them, link them.

    Each distinct tool CWL becomes a tool dataset (``tool_type`` = the workflow
    type); the workflow dataset is stored as uploaded. All SEEK registrations
    come first because the caller's token is short-lived and the uploads may
    not be. If anything fails, everything created so far is removed again.
    Subject/sample spreadsheets are kept as files but not loaded.
    """
    layout = load_workflow(dataset_root, workflow_type)
    staging_root().mkdir(parents=True, exist_ok=True)
    seek_ids: List[int] = []
    stored: List[str] = []
    with tempfile.TemporaryDirectory(dir=staging_root()) as tmp:
        tool_roots = {cwl: _assemble_tool(layout, cwl, Path(tmp)) for cwl in layout.tool_code}
        try:
            writer = Writer(api_token=api_token)
            tool_seek_ids = {}
            for cwl, root in tool_roots.items():
                tool_seek_ids[cwl] = writer.register_tool(root / "primary" / cwl.name, workflow_type, seek_project_id)
                seek_ids.append(tool_seek_ids[cwl])
            seek_id = writer.register_workflow(layout.workflow_cwl, list(layout.tool_code), workflow_type,
                                               seek_project_id)
            seek_ids.append(seek_id)
        except Exception as exc:
            logger.exception("SEEK registration failed for workflow dataset %s", dataset_root)
            if seek_ids:
                _undo(writer, seek_ids, [])
            raise SeekRegistrationError(f"SEEK registration failed; nothing was stored: {exc}") from exc

        try:
            tool_uuids = {}
            for cwl, root in tool_roots.items():
                tool_uuids[cwl] = Uploader().upload_dataset(
                    str(root), category=tools.CATEGORY, dataset_name=cwl.stem, skip_tables=("subject", "sample"),
                )
                stored.append(tool_uuids[cwl])
                link_tool(tool_uuids[cwl], tool_seek_ids[cwl], workflow_type)
            dataset_uuid = Uploader().upload_dataset(
                str(layout.root), category=workflows.CATEGORY, dataset_name=dataset_name,
                skip_tables=("subject", "sample"),
            )
            stored.append(dataset_uuid)
            _link_workflow(dataset_uuid, seek_id, workflow_type,
                           [(step.step_id, tool_uuids[step.tool_cwl]) for step in layout.steps])
        except Exception:
            logger.exception("Workflow commit failed after SEEK registration (workflow %s); rolling back", seek_id)
            _undo(writer, seek_ids, stored)
            raise

    return {
        "dataset_uuid": dataset_uuid,
        "seek_id": seek_id,
        "tools": [{"step_id": step.step_id, "dataset_uuid": tool_uuids[step.tool_cwl],
                   "seek_id": tool_seek_ids[step.tool_cwl]} for step in layout.steps],
    }


def linked_tools(conn, workflow_uuid: str) -> List[Dict[str, Any]]:
    """The tool datasets a workflow's steps run: ``[{dataset_uuid, dataset_name, seek_id, step_ids}]``."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT wt.tool_dataset_uuid::text, d.dataset_name, d.seek_id, array_agg(wt.step_id ORDER BY wt.step_id) "
            "FROM workflow_tool wt JOIN dataset d ON d.dataset_uuid = wt.tool_dataset_uuid "
            "WHERE wt.workflow_dataset_uuid = %s GROUP BY 1, 2, 3 ORDER BY min(wt.step_id)",
            (workflow_uuid,),
        )
        rows = cur.fetchall()
    conn.commit()
    return [{"dataset_uuid": u, "dataset_name": n, "seek_id": s, "step_ids": list(steps)} for u, n, s, steps in rows]


def tool_uuids(conn, layout: WorkflowLayout, workflow_uuid: str) -> Dict[Path, str]:
    """Each of the workflow's tool CWLs -> the dataset UUID of the tool stored for it."""
    by_step = {step: tool["dataset_uuid"] for tool in linked_tools(conn, workflow_uuid) for step in tool["step_ids"]}
    return {step.tool_cwl: by_step[step.step_id] for step in layout.steps}


def annotate_workflow(conn, dataset_root: Path, workflow_type: str, dataset_uuid: str,
                      client: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Build the committed workflow's FHIR descriptions (``client`` or auto) and store them.

    Each tool's ``workflow_tool`` descriptions are stored on its own dataset, the
    workflow's ``{"workflow": ...}`` on the workflow's; that is returned.
    """
    from ..measurements.pipeline import get_dataset_row, save_annotation
    from . import fhir as workflow_fhir

    layout = load_workflow(dataset_root, workflow_type)
    uuids = tool_uuids(conn, layout, dataset_uuid)
    name = get_dataset_row(conn, dataset_uuid)["dataset_name"] or ""
    descriptions, tool_descriptions = workflow_fhir.build_descriptions(layout, dataset_uuid, name, uuids, client)
    for cwl, tool_d in tool_descriptions.items():
        save_annotation(conn, uuids[cwl], tool_d)
    save_annotation(conn, dataset_uuid, descriptions)
    return descriptions
