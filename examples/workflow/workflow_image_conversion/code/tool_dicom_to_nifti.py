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

def _convert_dicom_to_nifti(dicom_dir: Path) -> Path:
    """Run DICOM → RAI NIfTI conversion."""
    import dicom2nifti
    import dicom2nifti.settings as settings
    import dicom2nifti.common as common
    import pydicom
    import re

    # Disable strict validation checks that often fail on clinical/messy data
    settings.disable_validate_orientation()
    settings.disable_validate_orthogonal()
    settings.disable_validate_slice_increment()
    settings.disable_validate_slicecount()

    # Monkeypatch common validation functions to bypass a known bug in dicom2nifti 
    # where convert_siemens.py ignores the settings flags and calls them unconditionally.
    common.validate_orientation = lambda *args, **kwargs: None
    common.validate_orthogonal = lambda *args, **kwargs: None
    common.validate_slice_increment = lambda *args, **kwargs: None
    common.validate_slicecount = lambda *args, **kwargs: None

    log.info("Step 1: Creating RAI NIfTI from DICOM directory: %s", dicom_dir)

    import SimpleITK as sitk
    import shutil

    # NOTE: We use SimpleITK to scan and group the DICOM files by series ID.
    # dicom2nifti's `dicom_series_to_nifti` function will crash with a broadcast shape error
    # if it tries to convert a directory containing images of different sizes (e.g., when 
    # scout/localizer images are mixed with the main sequence). By finding the series 
    # with the largest number of files, we isolate the main volume and avoid this error.
    reader = sitk.ImageSeriesReader()
    best_series_names = []

    for root, _, files in os.walk(dicom_dir):
        if files:
            ids = reader.GetGDCMSeriesIDs(root)
            for series_id in ids:
                series_files = reader.GetGDCMSeriesFileNames(root, series_id)
                if len(series_files) > len(best_series_names):
                    best_series_names = series_files

    if not best_series_names:
        raise RuntimeError(f"No DICOM series found in {dicom_dir}")

    series_desc = "image"
    try:
        ds = pydicom.dcmread(best_series_names[0], stop_before_pixels=True)
        if 'SeriesDescription' in ds:
            series_desc = ds.SeriesDescription
    except Exception:
        pass

    clean_desc = re.sub(r'[^\w\-_]', '_', series_desc.strip())
    output_file = dicom_dir.parent / f"{clean_desc}.nii.gz"

    clean_dicom_dir = dicom_dir.parent / "clean_dicom_input"
    clean_dicom_dir.mkdir(exist_ok=True, parents=True)
    for idx, f in enumerate(best_series_names):
        dst = clean_dicom_dir / f"slice_{idx:04d}.dcm"
        if not dst.exists():
            shutil.copy2(f, dst)

    log.info("Converting DICOM to %s from %d files...", output_file, len(best_series_names))
    dicom2nifti.dicom_series_to_nifti(str(clean_dicom_dir), str(output_file), reorient_nifti=True)
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

        # 1. Download inputs
        _download_prefix(s3, bucket, dicom_prefix, dicom_dir)

        # 2. Convert
        output_file = _convert_dicom_to_nifti(dicom_dir)

        # 3. Upload output
        prefix = output_key_prefix or f"{run_id}/outputs"
        output_key = f"{prefix}/{output_file.name}"
        uploaded_key = _upload_file(s3, output_file, bucket, output_key)

    return uploaded_key


# ---------------------------------------------------------------------------
# Stand-alone CLI (mirrors original dicom_to_nifti.py interface)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DICOM → NIfTI (Airflow tool)")
    parser.add_argument("--input", required=True, help="Path to DICOM directory")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    _convert_dicom_to_nifti(Path(args.input))
