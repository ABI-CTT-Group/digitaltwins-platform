"""
tool_dicom_to_nifti.py
======================
Callable executed by ExternalPythonOperator inside cwl_venv.

Maps to: tool_dicom_to_nifti.cwl
  baseCommand: [python, dicom_to_nifti.py]
  input:  dicom_input  (Directory)  --input <path>
  output: breast_mri_rai.nii.gz     (File, glob)

MinIO flow
----------
1. Download all objects under ``dicom_prefix`` into a local temp dir.
2. Run DICOM → NIfTI conversion logic (currently a stub).
3. Upload ``breast_mri_rai.nii.gz`` to ``<run_id>/outputs/breast_mri_rai.nii.gz``.
4. Return the uploaded MinIO key (passed back via XCom).
"""
from __future__ import annotations

import gzip
import os
import sys
import time
import tempfile
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MinIO helpers
# ---------------------------------------------------------------------------

def _get_s3_client() -> Any:
    """Return a boto3 S3 client configured for the local MinIO instance."""
    import boto3  # noqa: PLC0415 – imported inside venv task

    endpoint = os.environ.get("MINIO_ENDPOINT", "http://minio:9000")
    access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def _download_prefix(
    s3_client: Any,
    bucket: str,
    prefix: str,
    local_dir: Path,
) -> None:
    """Download every object under *prefix* in *bucket* into *local_dir*."""
    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=prefix)

    downloaded = 0
    for page in pages:
        for obj in page.get("Contents", []):
            key: str = obj["Key"]
            # Preserve relative path structure beneath the prefix.
            relative = key[len(prefix):].lstrip("/")
            if not relative:
                continue  # skip the "folder" key itself
            dest = local_dir / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            log.info("Downloading s3://%s/%s → %s", bucket, key, dest)
            s3_client.download_file(bucket, key, str(dest))
            downloaded += 1

    if downloaded == 0:
        log.warning(
            "No objects found under s3://%s/%s – conversion will run on empty input.",
            bucket,
            prefix,
        )


def _upload_file(
    s3_client: Any,
    local_path: Path,
    bucket: str,
    key: str,
) -> str:
    """Upload *local_path* to *bucket*/*key* and return the full key."""
    log.info("Uploading %s → s3://%s/%s", local_path, bucket, key)
    s3_client.upload_file(str(local_path), bucket, key)
    return key


# ---------------------------------------------------------------------------
# Conversion logic (stub — replace with real dicom2nifti call)
# ---------------------------------------------------------------------------

def _convert_dicom_to_nifti(dicom_dir: Path, output_file: Path) -> None:
    """Simulate DICOM → RAI NIfTI conversion (stub implementation).

    Replace the body of this function with a real call such as::

        import dicom2nifti
        dicom2nifti.convert_directory(str(dicom_dir), str(output_file.parent))

    The output file must be written to *output_file*.
    """
    log.info("Step 1: Creating RAI NIfTI from DICOM directory: %s", dicom_dir)
    log.info("Simulating dicom2nifti conversion …")
    time.sleep(3)

    with gzip.open(output_file, "wb") as fh:
        fh.write(b"Mock NIFTI data")

    log.info("Created %s", output_file)


# ---------------------------------------------------------------------------
# Main entry-point called by ExternalPythonOperator
# ---------------------------------------------------------------------------

def run(
    *,
    bucket: str,
    dicom_prefix: str,
    run_id: str,
    output_key_prefix: str | None = None,
) -> str:
    """Download DICOM input, convert to NIfTI, upload result to MinIO.

    Parameters
    ----------
    bucket:
        MinIO bucket name (e.g. ``"airflow-workspace"``).
    dicom_prefix:
        Object-key prefix for the DICOM source directory in the bucket
        (e.g. ``"test_run/inputs/dicom/"``).
    run_id:
        Identifier used to namespace outputs
        (e.g. ``"test_run"``).
    output_key_prefix:
        Override the output key prefix (defaults to ``"<run_id>/outputs"``).

    Returns
    -------
    str
        MinIO key of the uploaded NIfTI file — returned via XCom.
    """
    s3 = _get_s3_client()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        dicom_dir = tmp / "dicom_input"
        dicom_dir.mkdir()
        output_file = tmp / "breast_mri_rai.nii.gz"

        # 1. Download inputs
        _download_prefix(s3, bucket, dicom_prefix, dicom_dir)

        # 2. Convert
        _convert_dicom_to_nifti(dicom_dir, output_file)

        # 3. Upload output
        prefix = output_key_prefix or f"{run_id}/outputs"
        output_key = f"{prefix}/breast_mri_rai.nii.gz"
        uploaded_key = _upload_file(s3, output_file, bucket, output_key)

    return uploaded_key


# ---------------------------------------------------------------------------
# Stand-alone CLI (mirrors original dicom_to_nifti.py interface)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DICOM → NIfTI (Airflow tool)")
    parser.add_argument("--input", required=True, help="Path to DICOM directory")
    parser.add_argument("--output", default="breast_mri_rai.nii.gz")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    _convert_dicom_to_nifti(Path(args.input), Path(args.output))
