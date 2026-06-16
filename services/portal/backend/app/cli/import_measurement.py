"""CLI: import a measurement dataset end-to-end (plan 11).

Runs inside the portal-backend container, driving the service layer directly:
  login (admin) -> validate dataset -> get/auto-build descriptions -> reset
  placeholder ids -> create row + annotation -> run approval (MinIO + hapi-fhir)
  -> delete the local copy.

The ``input`` is an **in-container** path (a folder or a .zip). The wrapper
scripts (scripts/import-dataset.*) copy the operator's host dataset into the
container first and pass that path here; you can also call it directly on any
in-container path.

Input handling:
  - .zip -> extracted (zip-slip / zip-bomb guards); a single wrapper folder is
    peeled by resolve_project_root.
  - with a root ``fhir.json`` (already annotated) -> validated then approved.
  - without ``fhir.json`` -> auto pre-annotated (no human edit) then approved.

Data-safety: on success NOTHING is left on local disk — the input (and any zip
extraction) is removed; the data lives only in MinIO + FHIR. On failure the input
is kept so the import can be retried.

Usage:
  python -m app.cli.import_measurement <FOLDER_OR_ZIP> [--name NAME]
                                       [--password] [--username U]

Exit codes: 0 success / 1 user error (auth, validation, name clash) / 2 pipeline failure.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

_DATASET_DIR = Path(os.getenv("DATASET_DIR_MEASUREMENT", "./datasets_measurement"))
_MAX_BYTES = int(os.getenv("MAX_UPLOAD_MB", "20480")) * 1024 * 1024


def _fail(message: str, code: int) -> None:
    print(f"\n  ✗ {message}", file=sys.stderr)
    sys.exit(code)


async def _import(inbox_item: Path, name: str | None, admin_user: str) -> None:
    # Lazy imports so --help / arg errors don't pull the heavy stack.
    from app.client.fhir import get_fhir_adapter, get_fhir_async_client
    from app.client.minio import get_minio_client
    from app.models.db_model import (
        Measurement,
        MeasurementAnnotation,
        MeasurementStatus,
        SessionLocal,
    )
    from app.services.measurement_approval import ApprovalError, run_measurement_approval
    from app.services.measurement_import import (
        DatasetMismatchError,
        build_descriptions_from_dataset,
        reset_placeholder_ids,
        validate_fhir_matches_dataset,
    )
    from app.utils.builder_utils import (
        extract_uploaded_archive,
        resolve_project_root,
        unique_name,
        validate_sparc_structure,
    )
    from app.utils.utils import force_rmtree

    _DATASET_DIR.mkdir(parents=True, exist_ok=True)
    is_zip = inbox_item.is_file() and inbox_item.suffix.lower() == ".zip"
    extract_tmp: Path | None = None
    db = None
    succeeded = False
    try:
        # 1. SPARC project root (extract zip; peel a wrapper folder). Process in
        #    place — no second copy (the input already sits on the fast volume).
        if is_zip:
            print("  Extracting .zip …")
            # Extract next to the input (the staging dir on the fast volume) so
            # the whole import stays in one place and is cleaned together.
            extract_tmp = Path(tempfile.mkdtemp(prefix="extract_", dir=str(inbox_item.parent)))
            try:
                staging = extract_uploaded_archive(extract_tmp, inbox_item, max_total_bytes=_MAX_BYTES)
            except Exception as e:
                _fail(f"Could not extract zip: {e}", 1)
            project_root = resolve_project_root(staging)
            default_name = inbox_item.stem
        else:
            if not inbox_item.is_dir():
                _fail(f"Not a folder or .zip: {inbox_item}", 1)
            project_root = resolve_project_root(inbox_item)
            default_name = inbox_item.name

        ok, message = validate_sparc_structure(project_root)
        if not ok:
            _fail(f"Not a valid SPARC measurements dataset: {message}", 1)
        name = name or default_name

        minio = get_minio_client("measurements")
        adapter = get_fhir_adapter()
        fhir_async_client = get_fhir_async_client()
        db = SessionLocal()

        if db.query(Measurement).filter(Measurement.name == name).first():
            _fail(f"A measurement named '{name}' already exists. Use --name to pick another.", 1)

        # 2. Descriptions: read+validate provided fhir.json, or auto pre-annotate.
        fhir_path = project_root / "fhir.json"
        if fhir_path.exists():
            print("  Found fhir.json — validating it matches the dataset…")
            with open(fhir_path, "r", encoding="utf-8") as f:
                descriptions = json.load(f)
            try:
                validate_fhir_matches_dataset(descriptions, project_root)
            except DatasetMismatchError as e:
                _fail(f"fhir.json does not match this dataset: {e}", 1)
            print("  ✓ fhir.json matches.")
        else:
            print("  No fhir.json — auto pre-annotating from the dataset…")
            descriptions = build_descriptions_from_dataset(project_root, name)

        descriptions = reset_placeholder_ids(descriptions, project_root)

        # 3. Register the row + annotation (dataset processed in place).
        expose = unique_name(name)
        row = Measurement(
            name=name,
            description=(descriptions.get("dataset", {}) or {}).get("description") or None,
            dataset_path=str(project_root),
            expose_name=expose,
            local_archive_path=str(project_root),
            status=MeasurementStatus.PENDING.value,
            uuid=(descriptions.get("dataset", {}) or {}).get("uuid"),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        ann = MeasurementAnnotation(
            measurement_id=row.id,
            annotation_id=str(uuid.uuid4()),
            descriptions=descriptions,
        )
        db.add(ann)
        db.commit()

        # 4. Approval (MinIO + hapi-fhir).
        row.status = MeasurementStatus.UPLOADING.value
        db.commit()
        print("  Running approval (upload to MinIO + push to FHIR)…")
        try:
            await run_measurement_approval(
                row, ann,
                db=db, minio=minio, adapter=adapter, fhir_async_client=fhir_async_client,
            )
        except ApprovalError as e:
            _fail(f"Approval failed at stage '{e.stage}': {e.message} "
                  f"(input kept at {inbox_item} for retry)", 2)

        # 5. Success. run_measurement_approval already deleted the working dir
        #    (dataset_path) + set it None; `finally` wipes the outer staging
        #    wrapper + any zip extraction so nothing local remains.
        succeeded = True

        patients = len(descriptions.get("patients", []) or [])
        print(
            f"\n  ✓ Imported '{name}' (expose={expose}, {patients} patient(s)) by {admin_user}. "
            f"Stored in MinIO + FHIR, visible in the portal as completed. "
            f"No local copy remains."
        )
    finally:
        # On success: wipe every local copy (the input + any zip extraction) so
        # nothing lingers. On failure: keep them for a retry.
        if succeeded:
            for path in (inbox_item, extract_tmp):
                if path is not None and path.exists():
                    try:
                        if path.is_dir():
                            from app.utils.utils import force_rmtree as _frm
                            _frm(path)
                        else:
                            path.unlink()
                    except Exception:
                        pass
        if db is not None:
            db.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="import_measurement",
        description="Import a measurement dataset (admin only). Accepts an in-container folder or .zip.",
    )
    parser.add_argument("input", help="In-container dataset folder or .zip path")
    parser.add_argument("--name", help="Dataset name (default: folder / zip name)")
    parser.add_argument("--password", action="store_true", help="Use password login instead of device flow")
    parser.add_argument("--username", help="Username for password login")
    args = parser.parse_args(argv)

    inbox_item = Path(args.input)
    if not inbox_item.exists():
        _fail(f"No such folder or .zip: {inbox_item}", 1)

    from app.cli.keycloak_login import login

    try:
        admin_user, _ = login(use_password=args.password, username=args.username)
    except PermissionError as e:
        _fail(str(e), 1)
    except Exception as e:  # noqa: BLE001 — surface any auth/transport error as a user error
        _fail(f"Login failed: {e}", 1)

    asyncio.run(_import(inbox_item, args.name, admin_user))


if __name__ == "__main__":
    main()
