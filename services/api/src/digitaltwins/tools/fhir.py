"""FHIR for tool datasets: one ActivityDefinition per tool, identified by its dataset UUID.

Descriptions follow fhir-cda's ``workflow_tool`` shape. ``uuid``, ``name`` and
``title`` are server-owned (dataset UUID, dataset name, CWL ``label``); clients
may set ``version``, ``description`` (defaults to the CWL ``doc``), ``model`` /
``software`` (lists of UUIDs) and ``input`` / ``output`` (annotations of the
CWL's ports, each naming its port by ``id``). The port annotations are not part
of the ActivityDefinition; they are kept for annotating workflows that use the
tool (see docs/decisions/2026-10-01-unified-tool-dataset-ingest.md).
"""
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from .validation import find_tool_cwl

_SERVER_FIELDS = ("uuid", "name", "title")
_CLIENT_FIELDS = ("version", "description", "model", "software", "input", "output")


def _cwl(cwl_path: Path) -> Dict[str, Any]:
    return yaml.safe_load(Path(cwl_path).read_text()) or {}


def _port_list(section) -> List[Dict[str, Any]]:
    """CWL inputs/outputs in either the map or the list form, as ``[{id, type, doc}]``."""
    if isinstance(section, dict):
        items = [{"id": key, **(value if isinstance(value, dict) else {"type": value})}
                 for key, value in section.items()]
    else:
        items = [p for p in section or [] if isinstance(p, dict)]
    return [{"id": p.get("id"), "type": p.get("type"), "doc": p.get("doc")} for p in items]


def cwl_ports(cwl_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    cwl = _cwl(cwl_path)
    return {"inputs": _port_list(cwl.get("inputs")), "outputs": _port_list(cwl.get("outputs"))}


def ports(root: Path) -> Dict[str, List[Dict[str, Any]]]:
    return cwl_ports(find_tool_cwl(root))


def build_descriptions(root: Path, dataset_uuid: str, dataset_name: str,
                       client: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validated ``{"workflow_tool": {...}}`` for the tool dataset at ``root`` (see build_cwl_descriptions)."""
    return build_cwl_descriptions(find_tool_cwl(root), dataset_uuid, dataset_name, client)


def build_cwl_descriptions(cwl_path: Path, dataset_uuid: str, dataset_name: str,
                           client: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Validated ``{"workflow_tool": {...}}`` with the server-owned fields stamped.

    Raises ValueError for a malformed ``client``, an unknown field, or a port
    annotation that names no port of the tool's CWL (``cwl_path``).
    """
    if client is None:
        client = {"workflow_tool": {}}
    if not isinstance(client, dict) or set(client) != {"workflow_tool"} or not isinstance(client["workflow_tool"], dict):
        raise ValueError("Tool FHIR descriptions must be {\"workflow_tool\": {...}}")
    given = client["workflow_tool"]
    unknown = sorted(set(given) - set(_SERVER_FIELDS) - set(_CLIENT_FIELDS))
    if unknown:
        raise ValueError(f"Unknown workflow_tool field(s): {', '.join(unknown)}")
    for field in ("model", "software", "input", "output"):
        if not isinstance(given.get(field, []), list):
            raise ValueError(f"workflow_tool.{field} must be a list")

    cwl = _cwl(cwl_path)
    for field, section in (("input", "inputs"), ("output", "outputs")):
        known = {p["id"] for p in _port_list(cwl.get(section))}
        for entry in given.get(field, []):
            if not isinstance(entry, dict) or not entry.get("id"):
                raise ValueError(f"Every workflow_tool.{field} entry needs the id of a CWL {section[:-1]}")
            if entry["id"] not in known:
                raise ValueError(f"workflow_tool.{field} {entry['id']!r} is not a CWL {section[:-1]} of this tool")

    return {"workflow_tool": {
        "uuid": dataset_uuid,
        "name": dataset_name,
        "title": cwl.get("label") or dataset_name,
        "version": given.get("version") or "",
        "description": given.get("description") or cwl.get("doc") or "",
        "model": list(given.get("model", [])),
        "software": list(given.get("software", [])),
        "input": list(given.get("input", [])),
        "output": list(given.get("output", [])),
    }}


async def push(descriptions: Dict[str, Any], adapter) -> None:
    """Create the tool's ActivityDefinition through digitaltwins-on-fhir."""
    client = adapter.digital_twin().workflow_tool().add_workflow_tool_description(descriptions)
    await client.generate_resources()


def delete(dataset_uuid: str, fhir) -> int:
    """Delete the tool's ActivityDefinition(s); return how many were removed."""
    found = fhir.search("ActivityDefinition", identifier=dataset_uuid)
    for resource in found:
        fhir.delete(f"ActivityDefinition/{resource['id']}")
    return len(found)
