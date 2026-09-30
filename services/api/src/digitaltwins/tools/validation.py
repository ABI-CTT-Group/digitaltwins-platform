"""Structural check for a tool dataset: exactly one ``primary/tool_*.cwl``."""
from pathlib import Path

from ..measurements.validation import resolve_project_root


def find_tool_cwl(staging: Path) -> Path:
    """The tool's CWL file (``primary/tool_*.cwl``, top level) under the dataset root.

    Raises ValueError, with a message fit for a 400 response, unless there is exactly one.
    """
    primary = resolve_project_root(Path(staging)) / "primary"
    if not primary.is_dir():
        raise ValueError("Missing primary/ subdirectory at the dataset root.")
    cwls = sorted(p for p in primary.glob("tool_*.cwl") if p.is_file())
    if len(cwls) != 1:
        found = ", ".join(p.name for p in cwls) or "none"
        raise ValueError(f"primary/ must contain exactly one tool_*.cwl file (found: {found}).")
    return cwls[0]
