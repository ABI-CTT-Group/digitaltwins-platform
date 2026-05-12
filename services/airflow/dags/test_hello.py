from datetime import datetime
from airflow.sdk import DAG, task

with DAG(dag_id="test_hello", start_date=datetime(2024, 1, 1), schedule=None, tags=["test"]) as dag:
    @task
    def hello():
        print("Hello from Airflow!")
        return "done"
    hello()
