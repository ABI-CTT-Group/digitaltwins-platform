"""CLI: one-off purge of legacy portal measurements.

Measurement ingest moved to digitaltwins-api (datasets in platform Postgres,
MinIO ``measurements/<dataset_uuid>/``, FHIR identifiers = platform UUIDs). The
measurements the portal uploaded before that are discarded, not migrated. For
every row of ``portal.measurements`` this removes:
  - its MinIO objects under ``measurements/<expose_name>/``
  - its HAPI FHIR resources (see below)
  - its staged dataset dir (``dataset_path``) on the portal workspace volume
and then drops ``measurement_annotations`` and ``measurements``.

FHIR: digitaltwins-on-fhir tags only the Compositions with the dataset
identifier (the row's slug ``uuid``); Patients carry the patient uuid from the
annotation and the other resources derived identifiers. So the graph is
collected from those roots by following references and deleted referrers
first. (digitaltwins-api's ``delete_dataset_fhir_resources`` does the same.)

Reads the tables with raw SQL (the ORM models are gone). Safe to re-run: once
the tables are dropped it does nothing. Delete this CLI in the next release.

Usage:
  python -m app.cli.purge_legacy_measurements [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import requests
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

_TABLES = ("measurement_annotations", "measurements")  # child first
# Delete order: every type only references types after it.
_FHIR_TYPES = ("Composition", "ResearchSubject", "Consent", "Observation",
               "DocumentReference", "ImagingStudy", "Endpoint", "Patient")
_PATIENT_REFERRERS = (("ResearchSubject", "individual"), ("Consent", "patient"), ("ImagingStudy", "subject"),
                      ("Observation", "subject"), ("DocumentReference", "subject"))


class FhirRest:
    """search / read / delete over FHIR REST. Searches bypass HAPI's search cache."""

    _HEADERS = {"Cache-Control": "no-cache", "Accept": "application/fhir+json"}

    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")

    def search(self, resource_type: str, **params) -> list:
        url, query, found = f"{self.base}/{resource_type}", {**params, "_count": 200}, []
        while url:
            r = requests.get(url, params=query, headers=self._HEADERS, timeout=30)
            r.raise_for_status()
            bundle = r.json()
            found += [e["resource"] for e in bundle.get("entry", [])]
            url = next((l["url"] for l in bundle.get("link", []) if l.get("relation") == "next"), None)
            query = None
        return found

    def read(self, reference: str):
        r = requests.get(f"{self.base}/{reference}", headers=self._HEADERS, timeout=30)
        if r.status_code in (404, 410):
            return None
        r.raise_for_status()
        return r.json()

    def delete(self, reference: str) -> None:
        r = requests.delete(f"{self.base}/{reference}", timeout=30)
        if r.status_code not in (404, 410):
            r.raise_for_status()


def _references(obj):
    if isinstance(obj, dict):
        if isinstance(obj.get("reference"), str):
            yield "/".join(obj["reference"].split("/")[:2])
        for value in obj.values():
            yield from _references(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _references(value)


def _fhir_graph(fhir, identifier: str, patient_identifiers) -> list:
    """References of the dataset's FHIR resources, in delete order."""
    found, queue = {}, []

    def add(resources):
        for resource in resources:
            ref = f"{resource['resourceType']}/{resource['id']}"
            if ref not in found:
                found[ref] = resource
                queue.append(ref)

    add(fhir.search("Composition", identifier=identifier))
    for patient in patient_identifiers:
        add(fhir.search("Patient", identifier=patient))
    while queue:
        ref = queue.pop()
        if ref.startswith("Patient/"):
            for resource_type, param in _PATIENT_REFERRERS:
                add(fhir.search(resource_type, **{param: ref}))
        for target in _references(found[ref]):
            if target.split("/")[0] in _FHIR_TYPES and target not in found:
                resource = fhir.read(target)
                if resource:
                    add([resource])
    return [ref for t in _FHIR_TYPES for ref in found if ref.startswith(t + "/")]


def _patients(descriptions) -> list:
    if isinstance(descriptions, str):
        descriptions = json.loads(descriptions or "{}")
    return [p["uuid"] for p in (descriptions or {}).get("patients", []) if p.get("uuid")]


def purge(engine: Engine, minio, fhir, dry_run: bool = False) -> dict:
    """Purge legacy measurements; return what was (or, with ``dry_run``, would be) removed."""
    report = {"measurements": 0, "minio_objects": 0, "fhir_resources": 0, "staged_dirs": 0, "dropped_tables": []}
    if "measurements" not in inspect(engine).get_table_names():
        return report

    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT m.uuid, m.expose_name, m.dataset_path, a.descriptions FROM measurements m "
            "LEFT JOIN measurement_annotations a ON a.measurement_id = m.id")).all()
    report["measurements"] = len(rows)

    for uuid, expose_name, dataset_path, descriptions in rows:
        if expose_name:
            objects = minio.list_objects(prefix=f"{expose_name}/")
            report["minio_objects"] += len(objects)
            if not dry_run:
                # One by one: this MinIO rejects multi-object delete without
                # Content-MD5, which boto3 >= 1.36 no longer sends.
                for obj in objects:
                    minio.delete_object(obj["Key"])
        if uuid:
            graph = _fhir_graph(fhir, uuid, _patients(descriptions))
            report["fhir_resources"] += len(graph)
            if not dry_run:
                for ref in graph:
                    fhir.delete(ref)
        if dataset_path and Path(dataset_path).is_dir():
            report["staged_dirs"] += 1
            if not dry_run:
                shutil.rmtree(dataset_path, ignore_errors=True)

    if not dry_run:
        present = inspect(engine).get_table_names()
        with engine.begin() as conn:
            for table in _TABLES:
                if table in present:
                    conn.execute(text(f"DROP TABLE {table}"))
                    report["dropped_tables"].append(table)
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

    report = purge(engine, get_minio_client("measurements"), FhirRest(endpoint), args.dry_run)
    verb = "Would remove" if args.dry_run else "Removed"
    print(f"{verb}: {report['measurements']} measurement row(s), {report['minio_objects']} MinIO object(s), "
          f"{report['fhir_resources']} FHIR resource(s), {report['staged_dirs']} staged dir(s).")
    if report["dropped_tables"]:
        print(f"Dropped tables: {', '.join(report['dropped_tables'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
