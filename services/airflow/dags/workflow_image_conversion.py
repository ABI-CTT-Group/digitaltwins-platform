"""
workflow_image_conversion.py
============================
Airflow 3 DAG — Image Conversion Workflow

Maps to: workflow_image_conversion.cwl
  Three steps:
    1. download_samples → fetch sample data from measurement dataset in MinIO
    2. dicom_to_nifti  → breast_mri_rai.nii.gz
    3. dicom_to_nrrd   → image.nrrd

Usage
-----
Trigger via the Airflow UI or REST API with JSON conf, for example::

    {
        "bucket":        "airflow-workspace",
        "dicom_prefix":  "test_run/inputs/dicom/",
        "run_id":        "test_run"
    }

When triggered by the preprocessor DAG, conf will contain::

    {
        "bucket":        "airflow-workspace",
        "subject_id":    "sub-1",
        "dataset_uuid":  "cd77671c-33f7-11f1-b0c1-ce8482733eb4",
        "sample_type":   "ax dyn pre",
        "run_id":        "workflow_1/run_0",
        "run_index":     0
    }

The ``run_id`` key is optional; when omitted the DAG run ID is used.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any

from airflow.decorators import dag, task
from airflow.operators.python import ExternalPythonOperator

# Path to the virtual environment that carries boto3 (and future conversion libs).
VENV_PYTHON: str = "/opt/airflow/venvs/cwl_venv/bin/python"

# Default MinIO configuration — overridable via environment variables or DAG conf.
DEFAULT_BUCKET: str = "airflow-workspace"
DEFAULT_MINIO_ENDPOINT: str = os.environ.get("MINIO_ENDPOINT", "http://minio:9000")
DEFAULT_MINIO_ACCESS_KEY: str = os.environ.get("MINIO_ACCESS_KEY", "minioadmin")
DEFAULT_MINIO_SECRET_KEY: str = os.environ.get("MINIO_SECRET_KEY", "minioadmin")

# The tool modules live alongside the DAG under /opt/airflow/dags/tool/ inside
# the container (volume-mounted from services/airflow/dags/tool/).
TOOL_DIR: str = "/opt/airflow/dags"


# ---------------------------------------------------------------------------
# Callables executed inside cwl_venv by ExternalPythonOperator
# (each callable receives only primitive-typed arguments via op_kwargs/op_args)
# ---------------------------------------------------------------------------

def _run_download_samples(
    bucket: str,
    dataset_uuid: str,
    subject_id: str,
    sample_type: str,
    dag_id: str,
    run_index: int,
    minio_endpoint: str,
    minio_access_key: str,
    minio_secret_key: str,
    tool_dir: str,
) -> str:
    """Entry-point for the download_samples ExternalPythonOperator task."""
    import os
    import sys

    sys.path.insert(0, tool_dir)
    os.environ.setdefault("MINIO_ENDPOINT", minio_endpoint)
    os.environ.setdefault("MINIO_ACCESS_KEY", minio_access_key)
    os.environ.setdefault("MINIO_SECRET_KEY", minio_secret_key)

    from tool.tool_download_samples import run  # type: ignore[import]

    return run(
        bucket=bucket,
        dataset_uuid=dataset_uuid,
        subject_id=subject_id,
        sample_type=sample_type,
        dag_id=dag_id,
        run_index=run_index,
    )


def _run_dicom_to_nifti(
    bucket: str,
    dicom_prefix: str,
    run_id: str,
    minio_endpoint: str,
    minio_access_key: str,
    minio_secret_key: str,
    tool_dir: str,
) -> str:
    """Entry-point for the dicom_to_nifti ExternalPythonOperator task."""
    import os
    import sys

    sys.path.insert(0, tool_dir)
    os.environ.setdefault("MINIO_ENDPOINT", minio_endpoint)
    os.environ.setdefault("MINIO_ACCESS_KEY", minio_access_key)
    os.environ.setdefault("MINIO_SECRET_KEY", minio_secret_key)

    from tool.tool_dicom_to_nifti import run  # type: ignore[import]

    return run(bucket=bucket, dicom_prefix=dicom_prefix, run_id=run_id)


def _run_dicom_to_nrrd(
    bucket: str,
    dicom_prefix: str,
    run_id: str,
    minio_endpoint: str,
    minio_access_key: str,
    minio_secret_key: str,
    tool_dir: str,
) -> str:
    """Entry-point for the dicom_to_nrrd ExternalPythonOperator task."""
    import os
    import sys

    sys.path.insert(0, tool_dir)
    os.environ.setdefault("MINIO_ENDPOINT", minio_endpoint)
    os.environ.setdefault("MINIO_ACCESS_KEY", minio_access_key)
    os.environ.setdefault("MINIO_SECRET_KEY", minio_secret_key)

    from tool.tool_dicom_to_nrrd import run  # type: ignore[import]

    return run(bucket=bucket, dicom_prefix=dicom_prefix, run_id=run_id)


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

@dag(
    dag_id="workflow_23",
    dag_display_name="workflow_image_conversion",
    description=(
        "Convert a DICOM directory to NIfTI and NRRD formats. "
        "Inputs are fetched from MinIO (airflow-workspace bucket); "
        "outputs are uploaded back to the same bucket. "
        "When triggered by the preprocessor, sample data is first "
        "downloaded from the measurement dataset."
    ),
    schedule=None,          # manual trigger only
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["image-conversion", "dicom", "minio", "cwl"],
    doc_md=__doc__,
)
def workflow_image_conversion() -> None:
    """Declare the image-conversion workflow DAG."""

    # ------------------------------------------------------------------
    # Resolve runtime configuration from dag_run.conf with safe defaults
    # ------------------------------------------------------------------
    @task()
    def resolve_conf(**context: Any) -> dict[str, str]:
        """Extract and validate DAG run configuration."""
        conf: dict[str, Any] = context["dag_run"].conf or {}
        dag_run_id: str = context["run_id"]

        return {
            "bucket": str(conf.get("bucket", DEFAULT_BUCKET)),
            "dicom_prefix": str(conf.get("dicom_prefix", "")),
            "run_id": str(conf.get("run_id", dag_run_id)),
            # Preprocessor-injected keys (empty when triggered manually)
            "subject_id": str(conf.get("subject_id", "")),
            "dataset_uuid": str(conf.get("dataset_uuid", "")),
            "sample_type": str(conf.get("sample_type", "")),
            "input_name": str(conf.get("input_name", "input")),
            "run_index": str(conf.get("run_index", "0")),
        }

    conf = resolve_conf()

    # ------------------------------------------------------------------
    # Step 0: Download samples (runs only when triggered by preprocessor)
    # Downloads sample data from the measurement dataset bucket and
    # stages it into airflow-workspace/{dag_id}/run_{index}/inputs/
    # ------------------------------------------------------------------
    download_samples = ExternalPythonOperator(
        task_id="download_samples",
        python=VENV_PYTHON,
        python_callable=_run_download_samples,
        op_kwargs={
            "bucket": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['bucket'] }}",
            "dataset_uuid": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['dataset_uuid'] }}",
            "subject_id": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['subject_id'] }}",
            "sample_type": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['sample_type'] }}",
            "dag_id": "workflow_1",
            "run_index": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['run_index'] | int }}",
            "minio_endpoint": DEFAULT_MINIO_ENDPOINT,
            "minio_access_key": DEFAULT_MINIO_ACCESS_KEY,
            "minio_secret_key": DEFAULT_MINIO_SECRET_KEY,
            "tool_dir": TOOL_DIR,
        },
        do_xcom_push=True,  # pushes the staged input prefix
    )

    # ------------------------------------------------------------------
    # Step 1: DICOM → NIfTI  (maps to tool_dicom_to_nifti.cwl)
    # Uses the staged input prefix from download_samples as dicom_prefix
    # ------------------------------------------------------------------
    dicom_to_nifti = ExternalPythonOperator(
        task_id="dicom_to_nifti",
        python=VENV_PYTHON,
        python_callable=_run_dicom_to_nifti,
        op_kwargs={
            "bucket": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['bucket'] }}",
            "dicom_prefix": "{{ task_instance.xcom_pull(task_ids='download_samples') or task_instance.xcom_pull(task_ids='resolve_conf')['dicom_prefix'] }}",
            "run_id": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['run_id'] }}",
            "minio_endpoint": DEFAULT_MINIO_ENDPOINT,
            "minio_access_key": DEFAULT_MINIO_ACCESS_KEY,
            "minio_secret_key": DEFAULT_MINIO_SECRET_KEY,
            "tool_dir": TOOL_DIR,
        },
        do_xcom_push=True,  # pushes the returned MinIO key
    )

    # ------------------------------------------------------------------
    # Step 2: DICOM → NRRD  (maps to tool_dicom_to_nrrd.cwl)
    # Runs in PARALLEL with Step 1 — both read the same DICOM input.
    # ------------------------------------------------------------------
    dicom_to_nrrd = ExternalPythonOperator(
        task_id="dicom_to_nrrd",
        python=VENV_PYTHON,
        python_callable=_run_dicom_to_nrrd,
        op_kwargs={
            "bucket": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['bucket'] }}",
            "dicom_prefix": "{{ task_instance.xcom_pull(task_ids='download_samples') or task_instance.xcom_pull(task_ids='resolve_conf')['dicom_prefix'] }}",
            "run_id": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['run_id'] }}",
            "minio_endpoint": DEFAULT_MINIO_ENDPOINT,
            "minio_access_key": DEFAULT_MINIO_ACCESS_KEY,
            "minio_secret_key": DEFAULT_MINIO_SECRET_KEY,
            "tool_dir": TOOL_DIR,
        },
        do_xcom_push=True,
    )

    # Dependency chain:
    # resolve_conf → download_samples → [dicom_to_nifti, dicom_to_nrrd]
    conf >> download_samples >> [dicom_to_nifti, dicom_to_nrrd]  # type: ignore[operator]


# Instantiate the DAG (Airflow 3 TaskFlow API requires the call).
workflow_image_conversion()
