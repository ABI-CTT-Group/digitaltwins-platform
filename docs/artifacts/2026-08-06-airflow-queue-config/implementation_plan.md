# Configure Airflow Queue and Default Endpoint

This plan addresses the requirement to make the compute queue configurable for Airflow DAGs via an Airflow variable and to set a default fallback for the Airflow API endpoint. This enables offloading DAG execution to a remote compute node listening on a specific queue (e.g., "remote"), while seamlessly falling back to local processing.

## Proposed Changes

### Airflow DAGs

#### [MODIFY] [workflow_image_conversion.py](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/workflow_image_conversion.py)
- Import `Variable` from `airflow.models`.
- Add `COMPUTE_QUEUE = Variable.get("compute_queue", default_var="default")` at the top level of the file.
- Update the `@dag` decorator to include `default_args={"queue": COMPUTE_QUEUE}`. This ensures all tasks within the DAG are assigned to the configured queue by default.

### API Router

#### [MODIFY] [assay.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/assay.py)
- Modify line 32 to include a fallback default URL.
- Change `AIRFLOW_ENDPOINT = os.getenv("AIRFLOW_ENDPOINT")` to `AIRFLOW_ENDPOINT = os.getenv("AIRFLOW_ENDPOINT", "http://airflow-apiserver:8080/airflow")`. This allows the API to gracefully default to the internal Docker endpoint if the environment variable isn't explicitly set in the deployment.

## Verification Plan
1. Manually trigger the image conversion workflow.
2. Verify that the changes do not introduce any syntax errors in the DAG processing by Airflow.
3. Review the API container to ensure it correctly falls back to `http://airflow-apiserver:8080/airflow` when `AIRFLOW_ENDPOINT` is not provided.
