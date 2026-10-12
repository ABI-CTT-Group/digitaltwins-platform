"""FHIR for model datasets: one Device per model, identified by its dataset UUID.

Neither fhir-cda nor digitaltwins-on-fhir has a model resource, so the Device
is built here and pushed through the plain REST client (see
docs/decisions/2026-10-12-model-fhir-device.md). Descriptions are
``{"model": {...}}``: ``uuid`` and ``name`` are server-owned (dataset UUID and
name); clients may set ``description`` and ``version``.
"""
from typing import Any, Dict, Optional

# digitaltwins-on-fhir's DIGITALTWIN_ON_FHIR_SYSTEM: tool ActivityDefinitions
# cite models under this system, so a model's Device uses it too.
IDENTIFIER_SYSTEM = "https://www.auckland.ac.nz/en/abi.html"

_SERVER_FIELDS = ("uuid", "name")
_CLIENT_FIELDS = ("description", "version")


def build_descriptions(dataset_uuid: str, dataset_name: str, client: Optional[Dict[str, Any]] = None,
                       default_description: str = "") -> Dict[str, Any]:
    """Validated ``{"model": {...}}`` with the server-owned fields stamped.

    Raises ValueError for a malformed ``client`` or an unknown field.
    """
    if client is None:
        client = {"model": {}}
    if not isinstance(client, dict) or set(client) != {"model"} or not isinstance(client["model"], dict):
        raise ValueError('Model FHIR descriptions must be {"model": {...}}')
    given = client["model"]
    unknown = sorted(set(given) - set(_SERVER_FIELDS) - set(_CLIENT_FIELDS))
    if unknown:
        raise ValueError(f"Unknown model field(s): {', '.join(unknown)}")
    for field in _CLIENT_FIELDS:
        if given.get(field) is not None and not isinstance(given[field], str):
            raise ValueError(f"model.{field} must be a string")
    return {"model": {
        "uuid": dataset_uuid,
        "name": dataset_name,
        "description": given.get("description") or default_description or "",
        "version": given.get("version") or "",
    }}


def to_device(descriptions: Dict[str, Any]) -> Dict[str, Any]:
    """The FHIR R4 Device for validated model descriptions."""
    model = descriptions["model"]
    device = {
        "resourceType": "Device",
        "identifier": [{"system": IDENTIFIER_SYSTEM, "value": model["uuid"]}],
        "status": "active",
        "deviceName": [{"name": model["name"], "type": "user-friendly-name"}],
        "type": {"text": "model"},
    }
    if model.get("version"):
        device["version"] = [{"value": model["version"]}]
    if model.get("description"):
        device["note"] = [{"text": model["description"]}]
    return device


def delete(dataset_uuid: str, fhir) -> int:
    """Delete the model's Device(s); return how many were removed."""
    found = fhir.search("Device", identifier=dataset_uuid)
    for resource in found:
        fhir.delete(f"Device/{resource['id']}")
    return len(found)


def push(descriptions: Dict[str, Any], fhir) -> Dict[str, Any]:
    """Replace the model's Device: delete any with its identifier, then create it."""
    delete(descriptions["model"]["uuid"], fhir)
    return fhir.create(to_device(descriptions))
