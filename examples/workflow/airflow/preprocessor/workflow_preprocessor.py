from datetime import timedelta

from airflow.models.dag import DAG

from preprocessor import initialise_dataset, download_data_pre

assay_seek_id = None
with DAG(
        dag_id="preprocessor",
        dag_display_name="Preprocessor",
        default_args={
            "retries": 1,
            "retry_delay": timedelta(minutes=5)
        },
        description="Preprocessor",
        schedule=None,  # Ensures the DAG only runs manually
        catchup=False,  # Avoids running past dates if backfilling is enabled
        tags=["Example"],
        params={
            "assay_seek_id": assay_seek_id,
          }
) as dag:

    t1 = initialise_dataset.get_task(dag)
    t2 = download_data_pre.get_task(dag)

    t1 >> t2

