"""CLI: one-off purge of portal tool data from before the platform handoff.

Approving a tool now hands its build to digitaltwins-api: platform Postgres,
MinIO ``tools/<dataset_uuid>/``, SEEK, and an ActivityDefinition identified by
that UUID (docs/decisions/2026-10-01-unified-tool-dataset-ingest.md). What the
portal wrote before that is removed:
  - MinIO objects in the ``tools`` bucket whose top-level prefix is not a
    dataset UUID (the old ``<expose_name>/`` builds)
  - ActivityDefinitions of the placeholder ``sparc-tool-`` uuids on plugin rows
  - those placeholder uuids themselves (the plugin rows stay; re-approving a
    tool migrates it into the platform)

Safe to re-run. Delete this CLI in the next release.

Usage:
  python -m app.cli.purge_legacy_tools [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sys
import uuid

from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.cli.purge_legacy_measurements import FhirRest

_PLACEHOLDER = "sparc-tool-%"


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True


def purge(engine: Engine, minio, fhir, dry_run: bool = False) -> dict:
    """Purge legacy tool data; return what was (or, with ``dry_run``, would be) removed."""
    report = {"minio_objects": 0, "fhir_resources": 0, "placeholder_uuids": 0}

    legacy = [obj["Key"] for obj in minio.list_objects() if not _is_uuid(obj["Key"].split("/", 1)[0])]
    report["minio_objects"] = len(legacy)
    if not dry_run:
        # One by one: this MinIO rejects multi-object delete without Content-MD5.
        for key in legacy:
            minio.delete_object(key)

    with engine.connect() as conn:
        placeholders = conn.execute(text("SELECT uuid FROM plugins WHERE uuid LIKE :p"), {"p": _PLACEHOLDER}).scalars().all()
    report["placeholder_uuids"] = len(placeholders)
    for placeholder in placeholders:
        resources = fhir.search("ActivityDefinition", identifier=placeholder)
        report["fhir_resources"] += len(resources)
        if not dry_run:
            for resource in resources:
                fhir.delete(f"ActivityDefinition/{resource['id']}")

    if not dry_run and placeholders:
        with engine.begin() as conn:
            conn.execute(text("UPDATE plugins SET uuid = NULL WHERE uuid LIKE :p"), {"p": _PLACEHOLDER})
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="report what would be removed; change nothing")
    args = parser.parse_args(argv)

    from app.client.minio import get_minio_client
    from app.models.db_model import engine

    endpoint = os.getenv("FHIR_ENDPOINT", "localhost:8080/fhir").strip()
    if not endpoint.startswith(("http://", "https://")):
        endpoint = f"http://{endpoint}"

    report = purge(engine, get_minio_client("tools"), FhirRest(endpoint), args.dry_run)
    verb = "Would remove" if args.dry_run else "Removed"
    print(f"{verb}: {report['minio_objects']} legacy MinIO object(s), {report['fhir_resources']} "
          f"ActivityDefinition(s), {report['placeholder_uuids']} placeholder uuid(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
