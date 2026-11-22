"""
workflow_breast_model.py
=============================
Airflow 3 DAG: placeholder breast model generation, for demos.

Stands in for generating a breast model from skin, outer rib and sternum segmentations.
Nothing is computed: each step waits about 10 seconds and passes.

    point_cloud_generation -> mesh_fitting

When an assay run triggers it, the last step writes a small placeholder text
file to each of the assay's outputs (``conf["output_prefixes"]``), so Submit
uploads a tiny dataset.

The platform deploys this folder (``code/``) to ``dags/workflow_<seek_id>/`` and
the DAG names itself after that folder, so this file never hardcodes an id.
MinIO credentials come from the worker's environment (MINIO_ENDPOINT /
MINIO_ACCESS_KEY / MINIO_SECRET_KEY), never from task arguments.
See docs/workflow-dag-authoring.md in the platform repo.
"""
from __future__ import annotations

import importlib
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from airflow.decorators import dag, task
from airflow.models import Variable

DAG_ID = Path(__file__).parent.name
TOOL_DIR = str(Path(__file__).parent)
COMPUTE_QUEUE = Variable.get("compute_queue", default_var="default")

STEPS = [
    "point_cloud_generation",
    "mesh_fitting",
]

log = logging.getLogger(__name__)


def _write_placeholders(conf: dict) -> list[str]:
    """Write one small text file to each assay output prefix; return the keys written."""
    prefixes = conf.get("output_prefixes") or {}
    if not prefixes:
        return []
    import boto3

    s3 = boto3.client(
        "s3",
        endpoint_url=os.environ["MINIO_ENDPOINT"],
        aws_access_key_id=os.environ["MINIO_ACCESS_KEY"],
        aws_secret_access_key=os.environ["MINIO_SECRET_KEY"],
    )
    bucket = conf.get("bucket", "airflow-workspace")
    written = []
    for name, prefix in prefixes.items():
        label = name.split("/")[-1]
        key = f"{prefix}/{label}_placeholder.txt"
        body = f"Placeholder for {label}; nothing was computed.\n"
        s3.put_object(Bucket=bucket, Key=key, Body=body.encode())
        written.append(key)
    return written


@task
def run_step(step: str, last: bool, **context) -> dict:
    if TOOL_DIR not in sys.path:
        sys.path.insert(0, TOOL_DIR)
    log.info(importlib.import_module(f"tool_{step}").run())
    written = _write_placeholders(context["dag_run"].conf or {}) if last else []
    for key in written:
        log.info("Wrote %s", key)
    return {"step": step, "written": written}


@dag(
    dag_id=DAG_ID,
    dag_display_name="Generate breast model",
    schedule=None,
    start_date=datetime(2026, 1, 1),
    catchup=False,
    default_args={"queue": COMPUTE_QUEUE},
    tags=["breast-pilot"],
)
def breast_model():
    previous = None
    for index, step in enumerate(STEPS):
        current = run_step.override(task_id=step)(step, last=index == len(STEPS) - 1)
        if previous is not None:
            previous >> current
        previous = current


breast_model()
