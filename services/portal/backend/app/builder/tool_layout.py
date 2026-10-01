"""Where a tool upload keeps its source and its CWL.

A tool arrives either as source code (one ``.cwl`` at the root) or as an
already-packaged SDS dataset (``dataset_description.xlsx`` at the root, the
source in ``code/`` and the CWL as ``primary/tool_*.cwl`` — the same rule as
digitaltwins-api's ``find_tool_cwl``).
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from app.utils.builder_utils import (
    _ARCHIVE_BLACKLIST_NAMES,
    inspect_uploaded_source,
    read_root_cwl,
    resolve_project_root,
)

SDS_MARKER = "dataset_description.xlsx"


@dataclass(frozen=True)
class ToolLayout:
    root: Path
    source_dir: Path
    cwl: Path
    is_sds: bool


def root_cwl(project_dir: Path) -> Path:
    """The source's single top-level ``.cwl``: it describes the tool for SEEK and for workflows."""
    cwls = sorted(p for p in Path(project_dir).glob("*.cwl") if p.is_file())
    if len(cwls) != 1:
        found = ", ".join(p.name for p in cwls) or "none"
        raise RuntimeError(
            f"The tool source must have exactly one .cwl file at its root (found: {found}), "
            f"or be an SDS package with {SDS_MARKER} and exactly one primary/tool_*.cwl"
        )
    return cwls[0]


def sds_tool_cwl(root: Path) -> Path:
    cwls = sorted(p for p in (root / "primary").glob("tool_*.cwl") if p.is_file())
    if len(cwls) != 1:
        found = ", ".join(p.name for p in cwls) or "none"
        raise RuntimeError(f"An SDS package must have exactly one primary/tool_*.cwl (found: {found})")
    return cwls[0]


def detect_tool_layout(project_dir: Path) -> ToolLayout:
    root = resolve_project_root(Path(project_dir))
    if (root / SDS_MARKER).is_file():
        return ToolLayout(root=root, source_dir=root / "code", cwl=sds_tool_cwl(root), is_sds=True)
    return ToolLayout(root=root, source_dir=root, cwl=root_cwl(root), is_sds=False)


def inspect_tool_source(staging_dir: Path, *, want_cwl: bool) -> Dict[str, Any]:
    """``inspect_uploaded_source`` for tools: an SDS package reports its code/ folders and primary/ CWL."""
    meta = inspect_uploaded_source(staging_dir, want_npm=True, want_cwl=want_cwl)
    root = Path(meta["root"])
    meta["is_sds"] = (root / SDS_MARKER).is_file()
    if meta["is_sds"]:
        code = root / "code"
        meta["folders_in_root"] = [
            c.name for c in code.iterdir() if c.is_dir() and c.name not in _ARCHIVE_BLACKLIST_NAMES
        ] if code.is_dir() else []
        meta["has_cwl"] = read_tool_cwl(root) is not None
    return meta


def read_tool_cwl(project_dir: Path) -> Optional[Dict[str, str]]:
    """``read_root_cwl`` for tools: an SDS package's CWL is its primary/tool_*.cwl."""
    root = resolve_project_root(Path(project_dir))
    if not (root / SDS_MARKER).is_file():
        return read_root_cwl(root)
    try:
        cwl = sds_tool_cwl(root)
    except RuntimeError:
        return None
    return {"cwl_file": cwl.name, "content": cwl.read_text(encoding="utf-8")}
