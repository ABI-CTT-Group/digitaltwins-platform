from airflow import DAG
from airflow.operators.python import PythonOperator


def add_to_dataset(assay_seek_id, workspace, platform_config_file):
    import time
    time.sleep(3)


def exec(**kwargs):
    assay_seek_id = None
    workspace = None
    platform_config_file = None

    add_to_dataset(assay_seek_id=assay_seek_id, workspace=workspace, platform_config_file=platform_config_file)


def get_task(dag: DAG):
    task_id = "add_to_dataset"
    return PythonOperator(
        task_id=task_id,
        python_callable=exec,
        dag=dag
    )
