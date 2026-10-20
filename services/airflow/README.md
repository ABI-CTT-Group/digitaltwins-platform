The docker-compose.yaml file was fetched from https://airflow.apache.org/docs/apache-airflow/3.0.6/docker-compose.yaml (version: 3.0.6)

References:

- [Official Airflow installation](https://airflow.apache.org/docs/apache-airflow/stable/installation/index.html#installation-of-airflow)
- [Running Airflow in Docker](https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose/index.html)

## DAG folders managed by the platform

`dags/workflow_<seek_id>/` folders are written by the platform API when an admin
registers or approves a script workflow, or deploys it
(`POST /workflows/{dataset_uuid}/deploy`), and removed
when the workflow is deleted. Don't edit them by hand: redeploy instead. See
[docs/workflow-dag-authoring.md](../../docs/workflow-dag-authoring.md).
