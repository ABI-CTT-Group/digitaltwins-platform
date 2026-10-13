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

When triggered by an assay run (digitaltwins-api ``POST /assays/{id}/run``), conf contains::

    {
        "bucket":        "airflow-workspace",
        "subject_id":    "sub-1",
        "dataset_uuid":  "cd77671c-33f7-11f1-b0c1-ce8482733eb4",
        "sample_type":   "ax dyn pre",
        "run_id":        "workflow_<seek_id>/run_0",
        "run_index":     0
    }

The ``run_id`` key is optional; when omitted the DAG run ID is used.

Deployment
----------
The platform deploys this folder (``code/``) to ``dags/workflow_<seek_id>/`` and
the DAG names itself after that folder, so this file never hardcodes an id.
Tools are imported from the same folder. MinIO credentials come from the
worker's environment (MINIO_ENDPOINT / MINIO_ACCESS_KEY / MINIO_SECRET_KEY),
never from task arguments, which Airflow shows in its UI.
See docs/workflow-dag-authoring.md in the platform repo.
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime
from typing import Any

from airflow.decorators import dag, task
from airflow.models import Variable
from airflow.providers.standard.operators.python import ExternalPythonOperator as _ExternalPythonOperator

# unset -> local; set the Variable to "remote" to offload this DAG to the remote node
COMPUTE_QUEUE = Variable.get("compute_queue", default_var="default")

# Path to the virtual environment that carries boto3 (and future conversion libs).
VENV_PYTHON: str = "/opt/airflow/venvs/cwl_venv/bin/python"

DEFAULT_BUCKET: str = "airflow-workspace"

# Deployed as dags/workflow_<seek_id>/: the folder name is the DAG id the platform triggers.
DAG_ID: str = Path(__file__).parent.name

# The tool modules ship next to this file. Task callables run in a separate
# interpreter (cwl_venv) where __file__ is unavailable, so pass this path in.
TOOL_DIR: str = str(Path(__file__).parent)


class ExternalPythonOperator(_ExternalPythonOperator):
    """Avoid probing Airflow/Pendulum in the external venv when not needed."""

    def _iter_serializable_context_keys(self):  # type: ignore[override]
        # Keep only base context keys to avoid noisy package-probe stderr output.
        yield from self.BASE_SERIALIZABLE_CONTEXT_KEYS


def _resolve_output_prefix(
    output_prefixes: dict[str, Any],
    output_name_by_sample_type: dict[str, str],
    *,
    target_sample_type: str,
    legacy_key: str,
) -> str:
    """Resolve output prefixes from assay metadata with legacy compatibility."""
    mapped_output_name = str(output_name_by_sample_type.get(target_sample_type, "")).strip()
    if mapped_output_name:
        mapped_prefix = output_prefixes.get(mapped_output_name, "")
        if isinstance(mapped_prefix, str) and mapped_prefix:
            return mapped_prefix

    legacy_prefix = output_prefixes.get(legacy_key, "")
    if isinstance(legacy_prefix, str) and legacy_prefix:
        return legacy_prefix

    # Last-resort compatibility if metadata mapping is unavailable.
    for output_name, prefix in output_prefixes.items():
        if target_sample_type in str(output_name).lower() and isinstance(prefix, str) and prefix:
            return prefix

    return ""


# ---------------------------------------------------------------------------
# Callables executed inside cwl_venv by ExternalPythonOperator
# (each callable receives only primitive-typed arguments via op_kwargs/op_args)
# ---------------------------------------------------------------------------

def _run_download_samples(
    bucket: str,
    dataset_uuid: str,
    subject_id: str,
    sample_id: str,
    sample_type: str,
    dag_id: str,
    run_index: int,
    tool_dir: str,
) -> str:
    """Entry-point for the download_samples ExternalPythonOperator task."""
    import sys

    sys.path.insert(0, tool_dir)

    from tool_download_samples import run  # type: ignore[import]

    return run(
        bucket=bucket,
        dataset_uuid=dataset_uuid,
        subject_id=subject_id,
        sample_id=sample_id,
        sample_type=sample_type,
        dag_id=dag_id,
        run_index=int(run_index),
    )


def _run_dicom_to_nifti(
    bucket: str,
    dicom_prefix: str,
    run_id: str,
    output_key_prefix: str,
    tool_dir: str,
) -> str:
    """Entry-point for the dicom_to_nifti ExternalPythonOperator task."""
    import sys

    sys.path.insert(0, tool_dir)

    from tool_dicom_to_nifti import run  # type: ignore[import]

    return run(bucket=bucket, dicom_prefix=dicom_prefix, run_id=run_id, output_key_prefix=output_key_prefix)


def _run_dicom_to_nrrd(
    bucket: str,
    dicom_prefix: str,
    run_id: str,
    output_key_prefix: str,
    tool_dir: str,
) -> str:
    """Entry-point for the dicom_to_nrrd ExternalPythonOperator task."""
    import sys

    sys.path.insert(0, tool_dir)

    from tool_dicom_to_nrrd import run  # type: ignore[import]

    return run(bucket=bucket, dicom_prefix=dicom_prefix, run_id=run_id, output_key_prefix=output_key_prefix)


# ---------------------------------------------------------------------------
# DAG definition
# ---------------------------------------------------------------------------

@dag(
    dag_id=DAG_ID,
    dag_display_name="workflow_image_conversion",
    description=(
        "Convert a DICOM directory to NIfTI and NRRD formats. "
        "Inputs are fetched from MinIO (airflow-workspace bucket); "
        "outputs are uploaded back to the same bucket. "
        "When triggered by an assay run, sample data is first "
        "downloaded from the measurement dataset."
    ),
    schedule=None,          # manual trigger only
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["image-conversion", "dicom", "minio", "cwl"],
    default_args={"queue": COMPUTE_QUEUE},
    doc_md=__doc__,
)
def workflow_image_conversion() -> None:
    """Declare the image-conversion workflow DAG."""

    # ------------------------------------------------------------------
    # Resolve runtime configuration from dag_run.conf with safe defaults
    # ------------------------------------------------------------------
    @task()
    def resolve_conf(**context: Any) -> dict[str, Any]:
        """Extract and validate DAG run configuration."""
        conf: dict[str, Any] = context["dag_run"].conf or {}
        dag_run_id: str = context["run_id"]
        output_prefixes: dict[str, Any] = conf.get("output_prefixes", {})
        if not isinstance(output_prefixes, dict):
            output_prefixes = {}

        output_name_by_sample_type: dict[str, str] = conf.get("output_name_by_sample_type", {})
        if not isinstance(output_name_by_sample_type, dict):
            output_name_by_sample_type = {}

        return {
            "bucket": str(conf.get("bucket", DEFAULT_BUCKET)),
            "dicom_prefix": str(conf.get("dicom_prefix", "")),
            "run_id": str(conf.get("run_id", dag_run_id)),
            # Preprocessor-injected keys (empty when triggered manually)
            "subject_id": str(conf.get("subject_id", "")),
            "sample_id": str(conf.get("sample_id", "")),
            "dataset_uuid": str(conf.get("dataset_uuid", "")),
            "sample_type": str(conf.get("sample_type", "")),
            "input_name": str(conf.get("input_name", "input")),
            "run_index": str(conf.get("run_index", "0")),
            "output_prefixes": output_prefixes,
            "output_name_by_sample_type": output_name_by_sample_type,
            "nifti_output_prefix": _resolve_output_prefix(
                output_prefixes,
                output_name_by_sample_type,
                target_sample_type="nifti",
                legacy_key="nifti_output",
            ),
            "nrrd_output_prefix": _resolve_output_prefix(
                output_prefixes,
                output_name_by_sample_type,
                target_sample_type="nrrd",
                legacy_key="nrrd_output",
            ),
        }

    conf = resolve_conf()

    # ------------------------------------------------------------------
    # Step 0: Download samples (runs only when triggered by an assay run)
    # Downloads sample data from the measurement dataset bucket and
    # stages it into airflow-workspace/{dag_id}/run_{index}/inputs/
    # ------------------------------------------------------------------
    download_samples = ExternalPythonOperator(
        task_id="download_samples",
        python=VENV_PYTHON,
        expect_airflow=False,
        python_callable=_run_download_samples,
        op_kwargs={
            "bucket": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['bucket'] }}",
            "dataset_uuid": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['dataset_uuid'] }}",
            "subject_id": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['subject_id'] }}",
            "sample_id": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['sample_id'] }}",
            "sample_type": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['sample_type'] }}",
            "dag_id": DAG_ID,
            "run_index": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['run_index'] | int }}",
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
        expect_airflow=False,
        python_callable=_run_dicom_to_nifti,
        op_kwargs={
            "bucket": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['bucket'] }}",
            "dicom_prefix": "{{ task_instance.xcom_pull(task_ids='download_samples') or task_instance.xcom_pull(task_ids='resolve_conf')['dicom_prefix'] }}",
            "run_id": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['run_id'] }}",
            "output_key_prefix": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['nifti_output_prefix'] }}",
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
        expect_airflow=False,
        python_callable=_run_dicom_to_nrrd,
        op_kwargs={
            "bucket": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['bucket'] }}",
            "dicom_prefix": "{{ task_instance.xcom_pull(task_ids='download_samples') or task_instance.xcom_pull(task_ids='resolve_conf')['dicom_prefix'] }}",
            "run_id": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['run_id'] }}",
            "output_key_prefix": "{{ task_instance.xcom_pull(task_ids='resolve_conf')['nrrd_output_prefix'] }}",
            "tool_dir": TOOL_DIR,
        },
        do_xcom_push=True,
    )

    # Dependency chain:
    # resolve_conf → download_samples → [dicom_to_nifti, dicom_to_nrrd]
    conf >> download_samples >> [dicom_to_nifti, dicom_to_nrrd]  # type: ignore[operator]


# Instantiate the DAG (Airflow 3 TaskFlow API requires the call).
workflow_image_conversion()
