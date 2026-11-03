"""Where a tool upload keeps its source and its CWL.

A tool arrives either as source code (one ``.cwl`` at the root) or as an
already-packaged SDS dataset (``dataset_description.xlsx`` at the root, the
source in ``code/`` and the CWL as ``primary/tool_*.cwl`` — the same rule as
the platform API's ``find_tool_cwl``).
"""
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from app.utils.builder_utils import (
    _ARCHIVE_BLACKLIST_NAMES,
    inspect_uploaded_source,
    read_root_cwl,
    resolve_project_root,
)

SDS_MARKER = "dataset_description.xlsx"

logger = logging.getLogger(__name__)


class _StrictLoader(yaml.SafeLoader):
    """SafeLoader that rejects a repeated mapping key, as the portal's js-yaml does (PyYAML keeps the last)."""

    def construct_mapping(self, node, deep=False):
        seen = set()
        for key_node, _ in node.value:
            key = self.construct_object(key_node, deep=deep)
            if key in seen:
                raise yaml.constructor.ConstructorError(None, None, f"duplicate key {key!r}", key_node.start_mark)
            seen.add(key)
        return super().construct_mapping(node, deep)


def cwl_parse_error(text: str) -> Optional[str]:
    """Why ``text`` is not valid YAML (on one line), or ``None`` when it parses."""
    try:
        yaml.load(text, Loader=_StrictLoader)
    except Exception as exc:
        return " ".join(str(exc).split())
    return None


def log_invalid_cwl(cwl: Optional[Dict[str, Any]], log: logging.Logger = logger) -> None:
    """Warn when a read CWL (``{"cwl_file", "content"}``) will not parse; reading it still succeeds."""
    error = cwl_parse_error(cwl["content"]) if cwl else None
    if error:
        log.warning("Invalid CWL %s: %s", cwl["cwl_file"], error)


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
        result = read_root_cwl(root)
    else:
        try:
            cwl = sds_tool_cwl(root)
        except RuntimeError:
            return None
        result = {"cwl_file": cwl.name, "content": cwl.read_text(encoding="utf-8")}
    log_invalid_cwl(result)
    return result
