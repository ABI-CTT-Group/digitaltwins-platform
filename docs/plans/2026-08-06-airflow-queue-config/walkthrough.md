# Configuration Updates Walkthrough

The execution of the plan to make the compute queue configurable and provide a default fallback for the Airflow API endpoint is complete.

## Changes Made

### 1. Airflow DAG Queue Configuration
**File:** [workflow_image_conversion.py](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/workflow_image_conversion.py)

We imported the Airflow `Variable` model and defined a `COMPUTE_QUEUE` that attempts to retrieve the `compute_queue` variable, defaulting to `"default"`.
```python
from airflow.models import Variable

# unset -> local; set the Variable to "remote" to offload this DAG to the remote node
COMPUTE_QUEUE = Variable.get("compute_queue", default_var="default")
```

We then applied this to the DAG definition:
```python
@dag(
    # ...
    default_args={"queue": COMPUTE_QUEUE},
    # ...
)
```
This enables you to offload processing to a remote compute node simply by setting the `compute_queue` Airflow Variable to `"remote"`.

### 2. API Airflow Endpoint Fallback
**File:** [assay.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/assay.py)

We updated the way the API retrieves the Airflow endpoint to provide a local default:
```python
AIRFLOW_ENDPOINT = os.getenv("AIRFLOW_ENDPOINT", "http://airflow-apiserver:8080/airflow")
```
This allows local execution to seamlessly connect to the internal Docker endpoint if the environmental variable isn't explicitly set.

> [!TIP]
> To configure the DAG queue, log into the Airflow UI, go to **Admin -> Variables**, and add a new variable with Key: `compute_queue` and Value: `remote` (or whatever your remote queue name is).
