"""Mock UUID generators for the measurements upload flow.

TODO: replace when the digitaltwins-api integration lands. Every callsite
that currently uses these helpers should switch to a real API call that
returns the platform-issued UUID for the dataset / patient / resource.

To find all callsites: ``grep -rn "MOCK-" backend/app/`` — any literal
``MOCK-`` prefix in the codebase outside this module is a bug.
"""
from __future__ import annotations

import re
from uuid import uuid4

_MOCK_PREFIX = "MOCK"
_SLUG_RE = re.compile(r"[^A-Za-z0-9]+")


def _slug(value: str) -> str:
    """Sanitise an arbitrary string so it can sit inside a mock UUID without
    introducing characters that downstream consumers (hapi-fhir identifier,
    URL path segments) may choke on."""
    cleaned = _SLUG_RE.sub("-", (value or "").strip()).strip("-")
    return cleaned or "x"


def _short() -> str:
    """Twelve hex chars from a fresh uuid4 — plenty unique for our mock scope
    (a few dozen measurements per dataset, max)."""
    return uuid4().hex[:12]


def mock_dataset_uuid() -> str:
    """One mock UUID per measurement dataset."""
    return f"{_MOCK_PREFIX}-dataset-{_short()}"


def mock_patient_uuid(patient_name: str) -> str:
    """One mock UUID per patient folder (sub-XXX). Slug is informational —
    digitaltwins-api will not preserve it, but it makes log inspection easier
    while we're still in mock-land."""
    return f"{_MOCK_PREFIX}-pat-{_slug(patient_name)}-{_short()}"


def mock_resource_uuid(prefix: str) -> str:
    """Generic mock UUID for Observation / ImagingStudy / DocumentReference /
    Endpoint / etc. ``prefix`` is the resource hint (e.g. ``"obs"``, ``"img"``,
    ``"doc"``, ``"endpoint"``)."""
    return f"{_MOCK_PREFIX}-{_slug(prefix)}-{_short()}"
