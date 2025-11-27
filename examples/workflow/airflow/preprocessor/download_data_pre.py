import json
import os

import requests
from requests.auth import HTTPBasicAuth

from airflow import DAG
from airflow.operators.python import PythonOperator


def download(remote_sample_path, assay_input_dir, sample_id):
    pass


def run(assay_seek_id, workspace):
    import time
    time.sleep(1)


def exec(**kwargs):
    assay_seek_id = kwargs['dag_run'].conf.get('assay_seek_id', kwargs['params'].get('assay_seek_id'))
    workspace = ""

    run(assay_seek_id=assay_seek_id, workspace=workspace)


def get_task(dag: DAG):
    task_id = "download_data_pre"
    return PythonOperator(
        task_id=task_id,
        python_callable=exec,
        dag=dag
    )
