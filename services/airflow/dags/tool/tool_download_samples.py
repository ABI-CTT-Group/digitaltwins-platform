"""
tool_download_samples.py
========================
Callable executed by ExternalPythonOperator inside cwl_venv.

Downloads sample data from a measurement dataset bucket in MinIO and
stages it into the ``airflow-workspace`` bucket under the DAG's run
directory.

MinIO flow
----------
1. List objects in the source bucket matching
   ``{dataset_uuid}/primary/{subject_id}/``.
2. Download matching objects to a local temp directory.
3. Upload them to ``airflow-workspace/{dag_id}/run_{index}/inputs/``.
4. Return the staged input prefix (passed back via XCom).
"""
from __future__ import annotations

import os
import logging
import tempfile
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# MinIO helpers
# ---------------------------------------------------------------------------

def _get_s3_client() -> Any:
    """Return a boto3 S3 client configured for the local MinIO instance."""
    import boto3

    endpoint = os.environ.get("MINIO_ENDPOINT", "http://minio:9000")
    access_key = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
    secret_key = os.environ.get("MINIO_SECRET_KEY", "minioadmin")

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )


def _find_source_bucket(s3_client: Any, dataset_uuid: str) -> str | None:
    """Find which bucket contains objects for *dataset_uuid*."""
    buckets = s3_client.list_buckets().get("Buckets", [])
    prefix = f"{dataset_uuid}/"
    for bucket in buckets:
        bucket_name = bucket["Name"]
        resp = s3_client.list_objects_v2(
            Bucket=bucket_name, Prefix=prefix, MaxKeys=1,
        )
        if resp.get("KeyCount", 0) > 0:
            return bucket_name
    return None


def _download_prefix(
    s3_client: Any,
    bucket: str,
    prefix: str,
    local_dir: Path,
) -> int:
    """Download every object under *prefix* into *local_dir*."""
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

    return downloaded


def _upload_directory(
    s3_client: Any,
    local_dir: Path,
    target_bucket: str,
    target_prefix: str,
) -> int:
    """Upload all files under *local_dir* to *target_bucket*/*target_prefix*/."""
    uploaded = 0
    for local_path in local_dir.rglob("*"):
        if not local_path.is_file():
            continue
        relative = local_path.relative_to(local_dir)
        key = f"{target_prefix}/{relative}"
        log.info("Uploading %s → s3://%s/%s", local_path, target_bucket, key)
        s3_client.upload_file(str(local_path), target_bucket, key)
        uploaded += 1
    return uploaded


# ---------------------------------------------------------------------------
# Main entry-point called by ExternalPythonOperator
# ---------------------------------------------------------------------------

def run(
    *,
    bucket: str,
    dataset_uuid: str,
    subject_id: str,
    sample_type: str,
    dag_id: str,
    run_index: int,
) -> str:
    """Download sample data and stage into the workspace bucket.

    Parameters
    ----------
    bucket:
        Target MinIO bucket (e.g. ``"airflow-workspace"``).
    dataset_uuid:
        UUID of the measurement dataset containing the samples.
    subject_id:
        Subject identifier (e.g. ``"sub-1"``).
    sample_type:
        Sample type filter (e.g. ``"ax dyn pre"``).
    dag_id:
        The DAG identifier (e.g. ``"workflow_1"``).
    run_index:
        Run index for namespacing (e.g. ``0``).

    Returns
    -------
    str
        MinIO prefix where the staged inputs were uploaded.
    """
    s3 = _get_s3_client()

    # Locate the source bucket containing the dataset
    source_bucket = _find_source_bucket(s3, dataset_uuid)
    if not source_bucket:
        raise FileNotFoundError(
            f"No bucket found containing dataset '{dataset_uuid}'."
        )

    # Build the source prefix: {dataset_uuid}/primary/{subject_id}/
    source_prefix = f"{dataset_uuid}/primary/{subject_id}/"
    log.info(
        "Downloading samples from s3://%s/%s (sample_type=%s)",
        source_bucket, source_prefix, sample_type,
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        download_dir = tmp / "samples"
        download_dir.mkdir()

        # 1. Download from the source bucket
        count = _download_prefix(s3, source_bucket, source_prefix, download_dir)
        if count == 0:
            log.warning(
                "No objects found under s3://%s/%s",
                source_bucket, source_prefix,
            )

        # 2. Stage to workspace bucket
        target_prefix = f"{dag_id}/run_{run_index}/inputs"
        uploaded = _upload_directory(s3, download_dir, bucket, target_prefix)
        log.info(
            "Staged %d file(s) to s3://%s/%s", uploaded, bucket, target_prefix,
        )

    return f"{target_prefix}/"


# ---------------------------------------------------------------------------
# Stand-alone CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download & stage samples")
    parser.add_argument("--dataset-uuid", required=True)
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--sample-type", default="")
    parser.add_argument("--bucket", default="airflow-workspace")
    parser.add_argument("--dag-id", default="workflow_1")
    parser.add_argument("--run-index", type=int, default=0)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    result = run(
        bucket=args.bucket,
        dataset_uuid=args.dataset_uuid,
        subject_id=args.subject_id,
        sample_type=args.sample_type,
        dag_id=args.dag_id,
        run_index=args.run_index,
    )
    print(f"Staged inputs at: {result}")
