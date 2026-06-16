"""CLI: import a measurement dataset end-to-end (plan 11).

Runs inside the portal-backend container, driving the service layer directly:
  login (admin) -> validate dataset -> get/auto-build descriptions -> reset
  placeholder ids -> create row + annotation -> run approval (MinIO + hapi-fhir)
  -> delete every local copy (staging + the inbox source).

Input (one dataset per run), dropped into the import inbox:
  - a folder, or a .zip (extracted with zip-slip / zip-bomb guards; a single
    wrapper folder inside is peeled by resolve_project_root).
  - with a root ``fhir.json`` (already annotated) -> validated then approved.
  - without ``fhir.json`` -> auto pre-annotated (no human edit) then approved.

Data-safety: on success NOTHING is left on local disk — both the working copy
under /portal_workspace and the inbox source are removed; the data lives only in
MinIO. On failure the working copy is kept so the import can be retried.

Usage:
  python -m app.cli.import_measurement [FOLDER_OR_ZIP] [--name NAME]
                                       [--password] [--username U]

Exit codes: 0 success / 1 user error (auth, validation, name clash) / 2 pipeline failure.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import sys
import tempfile
import uuid
from pathlib import Path

_INBOX = Path(os.getenv("IMPORT_INBOX", "/measurement-import"))
_DATASET_DIR = Path(os.getenv("DATASET_DIR_MEASUREMENT", "./datasets_measurement"))
_MAX_BYTES = int(os.getenv("MAX_UPLOAD_MB", "20480")) * 1024 * 1024


def _fail(message: str, code: int) -> None:
    print(f"\n  ✗ {message}", file=sys.stderr)
    sys.exit(code)


def _delete_inbox_source(item: Path) -> None:
    """Remove the dropped dataset (folder or .zip) from the inbox."""
    if item.is_dir():
        from app.utils.utils import force_rmtree
        force_rmtree(item)
    elif item.exists():
        item.unlink()


def _resolve_inbox_item(arg: str | None) -> Path:
    """Pick the dataset to import: the CLI arg if given, else interactively from
    the import inbox. Accepts a folder or a .zip."""
    if arg:
        p = Path(arg)
        if not p.exists():
            _fail(f"No such folder or .zip: {p}", 1)
        return p

    if not _INBOX.is_dir():
        _fail(f"No input given and inbox {_INBOX} does not exist.", 1)
    candidates = sorted(
        c for c in _INBOX.iterdir()
        if c.is_dir() or c.suffix.lower() == ".zip"
    )
    if not candidates:
        _fail(f"Nothing to import in {_INBOX}. Drop a dataset folder or .zip there first.", 1)
    if len(candidates) == 1:
        return candidates[0]
    print(f"\n  In {_INBOX}:")
    for i, c in enumerate(candidates, 1):
        print(f"    [{i}] {c.name}")
    if not sys.stdin.isatty():
        _fail("Multiple inputs found; pass the folder/.zip explicitly (non-interactive).", 1)
    choice = input("  Choose a number: ").strip()
    try:
        return candidates[int(choice) - 1]
    except (ValueError, IndexError):
        _fail("Invalid choice.", 1)


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
    target: Path | None = None
    db = None
    try:
        # 1. Get the SPARC project root (extract zip; peel wrapper folders).
        if is_zip:
            print("  Extracting .zip …")
            extract_tmp = Path(tempfile.mkdtemp(prefix="mimport_", dir=str(_DATASET_DIR)))
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

        # 3. Copy into the canonical working dir on the fast volume.
        expose = unique_name(name)
        target = (_DATASET_DIR / expose).resolve()
        if target.exists():
            _fail(f"working dir {target} already exists; retry.", 2)
        print(f"  Copying dataset → {target} …")
        shutil.copytree(project_root, target)

        row = Measurement(
            name=name,
            description=(descriptions.get("dataset", {}) or {}).get("description") or None,
            dataset_path=str(target),
            expose_name=expose,
            local_archive_path=str(target),
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
                  f"(working copy kept at {target} for retry)", 2)

        # 5. Success → wipe EVERY local copy. The data lives only in MinIO now.
        force_rmtree(target)
        row.dataset_path = None
        db.commit()
        _delete_inbox_source(inbox_item)

        patients = len(descriptions.get("patients", []) or [])
        print(
            f"\n  ✓ Imported '{name}' (expose={expose}, {patients} patient(s)) by {admin_user}. "
            f"Stored in MinIO + FHIR, visible in the portal as completed. "
            f"No local copy remains."
        )
    finally:
        # The zip extraction is transient (we copied to `target`); always clean it.
        if extract_tmp is not None and extract_tmp.exists():
            try:
                force_rmtree(extract_tmp)
            except Exception:
                pass
        if db is not None:
            db.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="import_measurement",
        description="Import a measurement dataset (admin only). Accepts a folder or a .zip.",
    )
    parser.add_argument("input", nargs="?", help="Dataset folder or .zip (default: pick from the inbox)")
    parser.add_argument("--name", help="Dataset name (default: folder / zip name)")
    parser.add_argument("--password", action="store_true", help="Use password login instead of device flow")
    parser.add_argument("--username", help="Username for password login")
    args = parser.parse_args(argv)

    inbox_item = _resolve_inbox_item(args.input)

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
