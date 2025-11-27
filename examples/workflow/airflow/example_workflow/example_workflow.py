from datetime import timedelta

from airflow.models.dag import DAG

from example_workflow import download_data, create_nifti, segment, create_point_cloud, create_mesh, add_to_dataset

with DAG(
        dag_id="example_workflow", # note: this id must match the workflow dataset id
        dag_display_name="Example workflow",
        default_args={
            "retries": 1,
            "retry_delay": timedelta(minutes=5)
        },
        description="Example workflow",
        schedule=None,
        catchup=False,
        tags=["Example"],
        params={

        }
) as dag:
    t1 = download_data.get_task(dag)
    t2 = create_nifti.get_task(dag)
    t3 = segment.get_task(dag)
    t4 = create_point_cloud.get_task(dag)
    t5 = create_mesh.get_task(dag)
    t6 = add_to_dataset.get_task(dag)


    t1 >> t2 >> t3 >> t4 >> t5 >> t6
