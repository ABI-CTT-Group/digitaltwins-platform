from airflow import DAG
from airflow.operators.python import PythonOperator


def get_assay(assay_id, config_file):
    pass


def run(assay_seek_id, workspace):
    import time
    time.sleep(1)



def exec(**kwargs):
    assay_seek_id = kwargs['dag_run'].conf.get('assay_seek_id', kwargs['params'].get('assay_seek_id'))
    workspace = ""

    run(assay_seek_id=assay_seek_id, workspace=workspace)


def get_task(dag: DAG):
    task_id = "initialise_dataset"
    return PythonOperator(
        task_id=task_id,
        python_callable=exec,
        dag=dag
    )
