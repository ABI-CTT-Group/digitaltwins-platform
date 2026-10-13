"""
tool_dicom_to_nrrd.py
=====================
Callable executed by ExternalPythonOperator inside cwl_venv.

Maps to: tool_dicom_to_nrrd.cwl
  baseCommand: [python, dicom_to_nrrd.py]
  input:  dicom_input  (Directory)  --input <path>
  output: image.nrrd               (File, glob)

MinIO flow
----------
1. Download all objects under ``dicom_prefix`` into a local temp dir.
2. Run DICOM → NRRD conversion logic (currently a stub).
3. Upload ``image.nrrd`` to ``<run_id>/outputs/image.nrrd``.
4. Return the uploaded MinIO key (passed back via XCom).
"""
from __future__ import annotations

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
    access_key = os.environ.get("MINIO_ACCESS_KEY")
    secret_key = os.environ.get("MINIO_SECRET_KEY")

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
            relative = key[len(prefix):].lstrip("/")
            if not relative:
                continue
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
# Conversion logic (stub — replace with real SimpleITK / plastimatch call)
# ---------------------------------------------------------------------------

def _convert_dicom_to_nrrd(dicom_dir: Path) -> Path:
    """Run DICOM → NRRD conversion."""
    import SimpleITK as sitk
    import re
    import os

    log.info("Step 2: Creating NRRD from DICOM directory: %s", dicom_dir)

    reader = sitk.ImageSeriesReader()
    
    series_ids = ()
    target_dir = dicom_dir
    
    # Recursively find the first directory containing a DICOM series
    for root, _, files in os.walk(dicom_dir):
        if files:
            ids = reader.GetGDCMSeriesIDs(root)
            if ids:
                series_ids = ids
                target_dir = Path(root)
                break
    
    if not series_ids:
        log.error("No DICOM series found in any subdirectory of %s", dicom_dir)
        raise RuntimeError(f"No DICOM series found in {dicom_dir}")
        
    dicom_names = reader.GetGDCMSeriesFileNames(str(target_dir), series_ids[0])
    reader.SetFileNames(dicom_names)
    reader.MetaDataDictionaryArrayUpdateOn()
    reader.LoadPrivateTagsOn()
    
    try:
        image = reader.Execute()
    except Exception as e:
        log.error("Failed to read DICOM series: %s", e)
        raise RuntimeError(f"Failed to read DICOM series: {e}")

    try:
        series_desc = reader.GetMetaData(0, "0008|103e")
        clean_desc = re.sub(r'[^\w\-_]', '_', series_desc.strip())
        output_file = dicom_dir.parent / f"{clean_desc}.nrrd"
    except Exception:
        output_file = dicom_dir.parent / "image.nrrd"

    log.info("Converting DICOM to %s ...", output_file)
    sitk.WriteImage(image, str(output_file))
    log.info("Created %s", output_file)

    return output_file


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
    """Download DICOM input, convert to NRRD, upload result to MinIO.

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
        MinIO key of the uploaded NRRD file — returned via XCom.
    """
    s3 = _get_s3_client()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        dicom_dir = tmp / "dicom_input"
        dicom_dir.mkdir()

        # 1. Download inputs
        _download_prefix(s3, bucket, dicom_prefix, dicom_dir)

        # 2. Convert
        output_file = _convert_dicom_to_nrrd(dicom_dir)

        # 3. Upload output
        prefix = output_key_prefix or f"{run_id}/outputs"
        output_key = f"{prefix}/{output_file.name}"
        uploaded_key = _upload_file(s3, output_file, bucket, output_key)

    return uploaded_key


# ---------------------------------------------------------------------------
# Stand-alone CLI (mirrors original dicom_to_nrrd.py interface)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DICOM → NRRD (Airflow tool)")
    parser.add_argument("--input", required=True, help="Path to DICOM directory")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    _convert_dicom_to_nrrd(Path(args.input))
