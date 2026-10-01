"""FHIR for workflow datasets: a PlanDefinition for the workflow, an ActivityDefinition per tool.

Clients send ``{"workflow": {...}, "workflow_tools": {<step id>: {...}}}``,
every part optional. ``workflow`` takes ``version``, ``description`` (defaults
to the CWL ``doc``), ``purpose``, ``usage``, ``author`` and ``action``:
``[{step, input: [{id, resource_type, code?, system?, unit?}], output: [...]}]``
annotating the ports of the tool a step runs. ``workflow_tools`` sections are
the tools' ``workflow_tool`` descriptions (see ``tools/fhir.py``), keyed by a
step that runs the tool. ``uuid``, ``name``, ``title`` (CWL ``label``),
``goal`` and one action per step (``title`` = step id, ``related_tool_uuid`` =
the tool's dataset UUID) are server-owned. The stored form (``title`` for
``step``, ``display`` for ``id``) is accepted too, so descriptions round-trip.

Built here rather than with fhir-cda's WorkflowAnnotator, which needs inline
step definitions (see docs/decisions/2026-10-02-workflow-dataset-ingest.md).
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..tools import fhir as tool_fhir
from .validation import WorkflowLayout, read_cwl

# The only data requirement types digitaltwins-on-fhir keeps on a PlanDefinition action.
RESOURCE_TYPES = ("ImagingStudy", "DocumentReference", "Observation")

_SERVER_FIELDS = ("uuid", "name", "title", "goal")
_CLIENT_FIELDS = ("version", "description", "purpose", "usage", "author", "action")
# ``description`` / ``related_tool_uuid`` are server-owned; accepted so stored actions round-trip.
_ACTION_FIELDS = ("step", "title", "description", "related_tool_uuid", "input", "output")
_PORT_FIELDS = ("id", "display", "resource_type", "code", "system", "unit")


def _port(entry: Any, known: List[str], where: str) -> Dict[str, Any]:
    if not isinstance(entry, dict):
        raise ValueError(f"{where} entries must be objects")
    unknown = sorted(set(entry) - set(_PORT_FIELDS))
    if unknown:
        raise ValueError(f"Unknown {where} field(s): {', '.join(unknown)}")
    port_id = entry.get("id") or entry.get("display")
    if port_id not in known:
        raise ValueError(f"{where} {port_id!r} is not a port of the step's tool (known: {', '.join(known) or 'none'})")
    if entry.get("resource_type") not in RESOURCE_TYPES:
        raise ValueError(f"{where} {port_id!r} has resource_type {entry.get('resource_type')!r}; "
                         f"use one of: {', '.join(RESOURCE_TYPES)}")
    port = {"display": port_id, "resource_type": entry["resource_type"]}
    port.update({k: entry[k] for k in ("code", "system", "unit") if entry.get(k) is not None})
    return port


def _actions(layout: WorkflowLayout, given: Any, tool_uuids: Dict[Path, str]) -> List[Dict[str, Any]]:
    if not isinstance(given, list):
        raise ValueError("workflow.action must be a list")
    steps = {step.step_id: step for step in layout.steps}
    by_step: Dict[str, Dict[str, Any]] = {}
    for entry in given:
        if not isinstance(entry, dict):
            raise ValueError("workflow.action entries must be objects")
        unknown = sorted(set(entry) - set(_ACTION_FIELDS))
        if unknown:
            raise ValueError(f"Unknown workflow.action field(s): {', '.join(unknown)}")
        step_id = entry.get("step") or entry.get("title")
        if step_id not in steps:
            raise ValueError(f"workflow.action names {step_id!r}, which is not a step of the workflow")
        if step_id in by_step:
            raise ValueError(f"workflow.action names step {step_id!r} more than once")
        by_step[step_id] = entry

    actions = []
    for step in layout.steps:
        entry = by_step.get(step.step_id, {})
        ports = tool_fhir.cwl_ports(step.tool_cwl)
        sides = {}
        for side, section in (("input", "inputs"), ("output", "outputs")):
            if not isinstance(entry.get(side, []), list):
                raise ValueError(f"workflow.action {side} must be a list")
            known = [p["id"] for p in ports[section]]
            sides[side] = [_port(p, known, f"Step {step.step_id!r} {side}") for p in entry.get(side, [])]
        actions.append({
            "title": step.step_id,
            "description": read_cwl(step.tool_cwl).get("label") or step.step_id,
            "related_tool_uuid": tool_uuids.get(step.tool_cwl, ""),
            **sides,
        })
    return actions


def _tool_clients(layout: WorkflowLayout, given: Any) -> Dict[Path, Dict[str, Any]]:
    """Each tool's ``workflow_tool`` section, from the step(s) that run it."""
    if not isinstance(given, dict):
        raise ValueError("workflow_tools must be an object keyed by step id")
    steps = {step.step_id: step for step in layout.steps}
    out: Dict[Path, Dict[str, Any]] = {}
    for step_id, section in given.items():
        if step_id not in steps:
            raise ValueError(f"workflow_tools names {step_id!r}, which is not a step of the workflow")
        cwl = steps[step_id].tool_cwl
        if cwl in out and out[cwl] != section:
            raise ValueError(f"Steps that run the same tool ({cwl.name}) must give it the same workflow_tools section")
        out[cwl] = section
    return out


def build_descriptions(
    layout: WorkflowLayout,
    dataset_uuid: str,
    dataset_name: str,
    tool_uuids: Optional[Dict[Path, str]] = None,
    client: Optional[Dict[str, Any]] = None,
) -> Tuple[Dict[str, Any], Dict[Path, Dict[str, Any]]]:
    """The workflow's ``{"workflow": {...}}`` and each tool's ``{"workflow_tool": {...}}`` (by tool CWL).

    ``tool_uuids`` maps each tool CWL to its dataset UUID (empty when only
    validating). Raises ValueError for a malformed ``client``, an unknown
    field, or a step / port id that is not in the CWLs.
    """
    tool_uuids = tool_uuids or {}
    client = {} if client is None else client
    if not isinstance(client, dict) or set(client) - {"workflow", "workflow_tools"}:
        raise ValueError('Workflow FHIR descriptions must be {"workflow": {...}, "workflow_tools": {...}}')
    given = client.get("workflow", {})
    if not isinstance(given, dict):
        raise ValueError("workflow must be an object")
    unknown = sorted(set(given) - set(_SERVER_FIELDS) - set(_CLIENT_FIELDS))
    if unknown:
        raise ValueError(f"Unknown workflow field(s): {', '.join(unknown)}")

    tool_clients = _tool_clients(layout, client.get("workflow_tools", {}))
    tools = {
        cwl: tool_fhir.build_cwl_descriptions(cwl, tool_uuids.get(cwl, ""), cwl.stem,
                                              {"workflow_tool": tool_clients.get(cwl, {})})
        for cwl in layout.tool_code
    }
    cwl = read_cwl(layout.workflow_cwl)
    workflow = {
        "uuid": dataset_uuid,
        "name": dataset_name,
        "title": cwl.get("label") or dataset_name,
        "version": given.get("version") or "",
        "description": given.get("description") or cwl.get("doc") or "",
        "purpose": given.get("purpose") or "",
        "usage": given.get("usage") or "",
        "author": given.get("author") or "",
        "goal": [],  # digitaltwins-on-fhir iterates it, so it must be present
        "action": _actions(layout, given.get("action", []), tool_uuids),
    }
    return {"workflow": workflow}, tools


async def push(descriptions: Dict[str, Any], adapter) -> None:
    """Create the workflow's PlanDefinition; its tools' ActivityDefinitions must already exist."""
    client = adapter.digital_twin().workflow().add_workflow_description(descriptions)
    await client.generate_resources()


def delete(dataset_uuid: str, fhir) -> int:
    """Delete the workflow's PlanDefinition(s); return how many were removed."""
    found = fhir.search("PlanDefinition", identifier=dataset_uuid)
    for resource in found:
        fhir.delete(f"PlanDefinition/{resource['id']}")
    return len(found)
