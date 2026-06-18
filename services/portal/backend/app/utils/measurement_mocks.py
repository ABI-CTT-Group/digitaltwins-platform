"""Deterministic placeholder identifiers for the measurements pipeline.

Until the digitaltwins-api integration lands, every resource gets a placeholder
UUID derived from its **folder name**, so the real platform-issued UUID returned
by digitaltwins-api can be mapped back by sub/sam folder. These are business
identifier *values* (free-form strings), not FHIR logical ids.

Scheme::

    dataset   -> <slug(name)>                       e.g. "dataset-sparc"
    patient   -> <slug(sub-folder)>                  e.g. "sub-001"
    resource  -> <slug(patient)>/<slug(sample)>      e.g. "sub-001/sam-001"
    endpoint  -> <resource>:endpoint                 e.g. "sub-001/sam-001:endpoint"

``resource`` is qualified by patient so sample names that repeat across patients
(``sub-001/sam-001`` vs ``sub-002/sam-001``) don't collide.

If hapi-fhir ever rejects ``/`` or ``:`` in an identifier value, swap the
separators below — callers are unaffected.
"""
from __future__ import annotations

import re

_SLUG_RE = re.compile(r"[^A-Za-z0-9]+")
_RESOURCE_SEP = "/"
_ENDPOINT_SUFFIX = ":endpoint"


def _slug(value: str) -> str:
    """Sanitise a folder name to safe characters (keeps it readable for mapping)."""
    cleaned = _SLUG_RE.sub("-", (value or "").strip()).strip("-")
    return cleaned or "x"


def folder_dataset_uuid(dataset_name: str) -> str:
    """Placeholder dataset UUID = slug of the dataset name."""
    return _slug(dataset_name)


def folder_patient_uuid(patient: str) -> str:
    """Placeholder patient UUID = slug of the sub-XXX folder name."""
    return _slug(patient)


def folder_resource_uuid(patient: str, sample: str) -> str:
    """Placeholder Observation / ImagingStudy / DocumentReference UUID,
    qualified by patient so sample names repeating across patients don't clash."""
    return f"{_slug(patient)}{_RESOURCE_SEP}{_slug(sample)}"


def folder_endpoint_uuid(patient: str, sample: str) -> str:
    """Placeholder endpoint UUID for an ImagingStudy series (distinct from the
    study's own resource UUID)."""
    return f"{folder_resource_uuid(patient, sample)}{_ENDPOINT_SUFFIX}"
