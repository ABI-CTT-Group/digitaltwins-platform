"""Where a workflow upload keeps its CWL.

A workflow arrives either as source (a ``.cwl`` at the root, whose steps the
Annotation step maps onto portal tools) or as an SDS package
(``dataset_description.xlsx`` at the root, one ``primary/workflow_*.cwl`` and the
``primary/tool_*.cwl`` its steps run), which digitaltwins-api ingests as a
workflow dataset (see docs/decisions/2026-10-02-portal-sds-workflow-approval.md).
The API's ``load_workflow`` checks the rest of the package at finalize.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from app.builder.tool_layout import SDS_MARKER
from app.utils.builder_utils import (
    _ARCHIVE_BLACKLIST_NAMES,
    inspect_uploaded_source,
    read_root_cwl,
    resolve_project_root,
)


@dataclass(frozen=True)
class WorkflowLayout:
    root: Path
    is_sds: bool


def sds_workflow_cwl(root: Path) -> Path:
    cwls = sorted(p for p in (root / "primary").glob("workflow_*.cwl") if p.is_file())
    if len(cwls) != 1:
        found = ", ".join(p.name for p in cwls) or "none"
        raise RuntimeError(f"An SDS workflow package must have exactly one primary/workflow_*.cwl (found: {found})")
    return cwls[0]


def detect_workflow_layout(project_dir: Path) -> WorkflowLayout:
    root = resolve_project_root(Path(project_dir))
    is_sds = (root / SDS_MARKER).is_file()
    if is_sds:
        sds_workflow_cwl(root)
    return WorkflowLayout(root=root, is_sds=is_sds)


def inspect_workflow_source(staging_dir: Path, *, want_cwl: bool, want_npm: bool = False) -> Dict[str, Any]:
    """``inspect_uploaded_source`` for workflows: an SDS package's CWL is its primary/workflow_*.cwl."""
    meta = inspect_uploaded_source(staging_dir, want_npm=want_npm, want_cwl=want_cwl)
    root = Path(meta["root"])
    meta["is_sds"] = (root / SDS_MARKER).is_file()
    if meta["is_sds"]:
        # Mirror inspect_tool_source: list code/ subfolders, not root folders.
        code = root / "code"
        meta["folders_in_root"] = [
            c.name for c in code.iterdir() if c.is_dir() and c.name not in _ARCHIVE_BLACKLIST_NAMES
        ] if code.is_dir() else []
        meta["has_cwl"] = read_workflow_cwl(root) is not None
    return meta


def read_workflow_cwl(project_dir: Path) -> Optional[Dict[str, Any]]:
    """``read_root_cwl`` for workflows; an SDS package also returns its tool CWLs (a list: see the frontend's camelCasing)."""
    root = resolve_project_root(Path(project_dir))
    if not (root / SDS_MARKER).is_file():
        return read_root_cwl(root)
    try:
        cwl = sds_workflow_cwl(root)
    except RuntimeError:
        return None
    tools = sorted(p for p in (root / "primary").glob("tool_*.cwl") if p.is_file())
    return {
        "cwl_file": cwl.name,
        "content": cwl.read_text(encoding="utf-8"),
        "tool_cwls": [{"cwl_file": p.name, "content": p.read_text(encoding="utf-8")} for p in tools],
    }
