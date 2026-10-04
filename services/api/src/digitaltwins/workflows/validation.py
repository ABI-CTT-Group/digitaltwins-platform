"""Structural check for a workflow dataset, and which files in ``code/`` belong to each tool.

A workflow dataset has exactly one ``primary/workflow_*.cwl`` (``class: Workflow``)
whose steps each ``run`` a ``primary/tool_*.cwl`` (``class: CommandLineTool``).
A tool's code is ``code/<tool stem>/`` when that folder exists; otherwise a
script tool's is its top-level ``code/<tool stem>.*`` files, and the single
tool of a notebook or gui workflow gets all of ``code/``.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

from ..measurements.validation import resolve_project_root
from . import WORKFLOW_TYPES

_SINGLE_STEP_TYPES = ("notebook", "gui")


@dataclass(frozen=True)
class Step:
    step_id: str
    tool_cwl: Path


@dataclass(frozen=True)
class WorkflowLayout:
    root: Path
    workflow_cwl: Path
    steps: List[Step]
    # Tool CWL -> its code: each path is a file copied into the tool's code/,
    # or a folder whose contents are. Ordered by first use.
    tool_code: Dict[Path, Tuple[Path, ...]]


def read_cwl(path: Path) -> Dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text())
    except yaml.YAMLError as exc:
        raise ValueError(f"{path.name} is not valid CWL/YAML: {exc}") from exc
    return data if isinstance(data, dict) else {}


def _steps(cwl: Dict[str, Any]) -> List[Tuple[str, Any]]:
    """CWL steps in either the map or the list form, as ``[(step_id, run)]``."""
    steps = cwl.get("steps")
    if isinstance(steps, dict):
        return [(key, (value or {}).get("run")) for key, value in steps.items()]
    return [(str(s.get("id", "")).lstrip("#"), s.get("run")) for s in steps or [] if isinstance(s, dict)]


def _tool_code(root: Path, tool_cwl: Path, workflow_type: str) -> Tuple[Path, ...]:
    code = root / "code"
    stem = tool_cwl.stem
    if (code / stem).is_dir():
        return (code / stem,)
    if workflow_type in _SINGLE_STEP_TYPES:
        return (code,) if code.is_dir() else ()
    files = tuple(sorted(p for p in code.glob(f"{stem}.*") if p.is_file())) if code.is_dir() else ()
    if not files:
        raise ValueError(f"No code for script tool {tool_cwl.name}: expected code/{stem}/ or code/{stem}.*")
    return files


def load_workflow(staging: Path, workflow_type: str) -> WorkflowLayout:
    """The workflow's steps and the code of each of its tools.

    Raises ValueError, with a message fit for a 400 response, if the layout is invalid.
    """
    if workflow_type not in WORKFLOW_TYPES:
        raise ValueError(f"Unknown workflow type {workflow_type!r}; use one of: {', '.join(WORKFLOW_TYPES)}")
    root = resolve_project_root(Path(staging))
    primary = root / "primary"
    if not primary.is_dir():
        raise ValueError("Missing primary/ subdirectory at the dataset root.")
    cwls = sorted(p for p in primary.glob("workflow_*.cwl") if p.is_file())
    if len(cwls) != 1:
        found = ", ".join(p.name for p in cwls) or "none"
        raise ValueError(f"primary/ must contain exactly one workflow_*.cwl file (found: {found}).")
    workflow_cwl = cwls[0]
    cwl = read_cwl(workflow_cwl)
    if cwl.get("class") != "Workflow":
        raise ValueError(f"{workflow_cwl.name} must be a CWL 'class: Workflow'.")

    steps = []
    for step_id, run in _steps(cwl):
        if not isinstance(run, str):
            raise ValueError(f"Step {step_id!r} must 'run' a primary/tool_*.cwl file, not an inline definition.")
        tool_cwl = primary / Path(run).name
        if not Path(run).name.startswith("tool_") or Path(run).suffix != ".cwl":
            raise ValueError(f"Step {step_id!r} runs {run!r}; it must run a primary/tool_*.cwl file.")
        if not tool_cwl.is_file():
            raise ValueError(f"Step {step_id!r} runs {run!r}, which is not in primary/.")
        steps.append(Step(step_id, tool_cwl))
    if not steps:
        raise ValueError(f"{workflow_cwl.name} has no steps.")
    if workflow_type in _SINGLE_STEP_TYPES and len(steps) != 1:
        raise ValueError(f"A {workflow_type} workflow must have exactly one step (found {len(steps)}).")

    used = list(dict.fromkeys(step.tool_cwl for step in steps))
    unused = sorted(p.name for p in primary.glob("tool_*.cwl") if p.is_file() and p not in used)
    if unused:
        raise ValueError(f"primary/ has tool CWL(s) that no step runs: {', '.join(unused)}")
    for tool_cwl in used:
        if read_cwl(tool_cwl).get("class") != "CommandLineTool":
            raise ValueError(f"{tool_cwl.name} must be a CWL 'class: CommandLineTool'.")

    return WorkflowLayout(
        root=root,
        workflow_cwl=workflow_cwl,
        steps=steps,
        tool_code={tool_cwl: _tool_code(root, tool_cwl, workflow_type) for tool_cwl in used},
    )
