"""CLI: import a measurement dataset end-to-end (plan 11).

Runs inside the portal-backend container, driving the service layer directly:
  login (admin) -> validate dataset -> get/auto-build descriptions -> reset
  placeholder ids -> create row + annotation -> run approval (MinIO + hapi-fhir)
  -> delete local staging.

Two input shapes (one dataset per run):
  - folder WITH a root ``fhir.json`` (already annotated): validated against the
    dataset, then approved directly.
  - folder WITHOUT ``fhir.json``: auto pre-annotated (no human edit), then approved.

Usage:
  python -m app.cli.import_measurement [FOLDER] [--name NAME] [--consume]
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
import uuid
from pathlib import Path

_INBOX = Path(os.getenv("IMPORT_INBOX", "/measurement-import"))
_DATASET_DIR = Path(os.getenv("DATASET_DIR_MEASUREMENT", "./datasets_measurement"))


def _fail(message: str, code: int) -> None:
    print(f"\n  ✗ {message}", file=sys.stderr)
    sys.exit(code)


def _resolve_folder(arg_folder: str | None) -> Path:
    """Pick the dataset folder: the CLI arg if given, else interactively from the
    import inbox."""
    if arg_folder:
        p = Path(arg_folder)
        if not p.is_dir():
            _fail(f"Not a folder: {p}", 1)
        return p

    if not _INBOX.is_dir():
        _fail(f"No folder given and inbox {_INBOX} does not exist.", 1)
    candidates = sorted(d for d in _INBOX.iterdir() if d.is_dir())
    if not candidates:
        _fail(f"No dataset folders found in {_INBOX}. Drop a dataset folder there first.", 1)
    if len(candidates) == 1:
        return candidates[0]
    print(f"\n  Datasets in {_INBOX}:")
    for i, c in enumerate(candidates, 1):
        print(f"    [{i}] {c.name}")
    if not sys.stdin.isatty():
        _fail("Multiple datasets found; pass the folder explicitly (non-interactive).", 1)
    choice = input("  Choose a dataset number: ").strip()
    try:
        return candidates[int(choice) - 1]
    except (ValueError, IndexError):
        _fail("Invalid choice.", 1)


async def _import(folder: Path, name: str | None, consume: bool, admin_user: str) -> None:
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
        resolve_project_root,
        unique_name,
        validate_sparc_structure,
    )
    from app.utils.utils import force_rmtree

    ok, message = validate_sparc_structure(folder)
    if not ok:
        _fail(f"Not a valid SPARC measurements dataset: {message}", 1)
    project_root = resolve_project_root(folder)
    name = name or folder.name

    minio = get_minio_client("measurements")
    adapter = get_fhir_adapter()
    fhir_async_client = get_fhir_async_client()
    db = SessionLocal()
    target: Path | None = None
    try:
        if db.query(Measurement).filter(Measurement.name == name).first():
            _fail(f"A measurement named '{name}' already exists. Use --name to pick another.", 1)

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

        # Copy into the canonical dataset dir (mirrors the GUI finalize/create).
        expose = unique_name(name)
        target = (_DATASET_DIR / expose).resolve()
        if target.exists():
            _fail(f"expose dir {target} already exists; retry.", 2)
        target.parent.mkdir(parents=True, exist_ok=True)
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
                  f"(dataset kept at {target} for retry)", 2)

        # Success → drop the local staging copy (data lives in MinIO now).
        force_rmtree(target)
        row.dataset_path = None
        db.commit()
        if consume:
            force_rmtree(folder)

        patients = len(descriptions.get("patients", []) or [])
        print(
            f"\n  ✓ Imported '{name}' (expose={expose}, {patients} patient(s)) by {admin_user}. "
            f"Visible in the portal as completed."
            + ("" if not consume else f"\n    Removed source folder {folder}.")
        )
    finally:
        db.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="import_measurement",
        description="Import a measurement dataset (admin only).",
    )
    parser.add_argument("folder", nargs="?", help="Dataset folder (default: pick from the import inbox)")
    parser.add_argument("--name", help="Dataset name (default: folder name)")
    parser.add_argument("--consume", action="store_true", help="Delete the source folder after success")
    parser.add_argument("--password", action="store_true", help="Use password login instead of device flow")
    parser.add_argument("--username", help="Username for password login")
    args = parser.parse_args(argv)

    folder = _resolve_folder(args.folder)

    from app.cli.keycloak_login import login

    try:
        admin_user, _ = login(use_password=args.password, username=args.username)
    except PermissionError as e:
        _fail(str(e), 1)
    except Exception as e:  # noqa: BLE001 — surface any auth/transport error as a user error
        _fail(f"Login failed: {e}", 1)

    asyncio.run(_import(folder, args.name, args.consume, admin_user))


if __name__ == "__main__":
    main()
