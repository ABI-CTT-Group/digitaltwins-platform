# Airflow Remote Logging to MinIO

## Overview

By default, Airflow writes task logs to the local filesystem of whichever worker ran the task. When workers run on a separate VM (compute2), these logs are not visible in the Airflow UI — it tries to fetch them directly from the worker by hostname and fails.

The fix is **remote logging to MinIO**: all workers write logs to the MinIO object store, and the Airflow UI reads them from there. Since both the main VM and compute2 can reach MinIO, logs are always visible regardless of which worker ran the task.

---

## What Was Done

### 1. Created the `airflow-logs` bucket in MinIO

Run once on the portal VM:

```bash
cd ~/digitaltwins-platform/services/airflow
docker compose exec minio mc alias set local http://localhost:9000 minioadmin minioadmin
docker compose exec minio mc mb local/airflow-logs
```

### 2. Added `apache-airflow-providers-amazon` to the Dockerfile

MinIO uses the S3-compatible API, which requires the Amazon provider package.

In `services/airflow/Dockerfile`:

```dockerfile
RUN pip install --no-cache-dir digitaltwins==2.0a3 apache-airflow-providers-amazon
```

### 3. Added remote logging env vars to main VM docker-compose

In `services/airflow/docker-compose.yml` (common env section):

```yaml
## Remote logging to MinIO (S3-compatible)
AIRFLOW__LOGGING__REMOTE_LOGGING: 'True'
AIRFLOW__LOGGING__REMOTE_LOG_CONN_ID: minio_logs
AIRFLOW__LOGGING__REMOTE_BASE_LOG_FOLDER: s3://airflow-logs
AIRFLOW__LOGGING__ENCRYPT_S3_LOGS: 'False'
AIRFLOW_CONN_MINIO_LOGS: "aws://minioadmin:minioadmin@?endpoint_url=http%3A%2F%2Fminio%3A9000"
```

Note: on the main VM, MinIO is referenced by Docker service name (`minio:9000`).

### 4. Added remote logging env vars to compute worker docker-compose

In `buildout/dev/compute/docker-compose.yml`:

```yaml
## Remote logging to MinIO (S3-compatible)
AIRFLOW__LOGGING__REMOTE_LOGGING: 'True'
AIRFLOW__LOGGING__REMOTE_LOG_CONN_ID: minio_logs
AIRFLOW__LOGGING__REMOTE_BASE_LOG_FOLDER: s3://airflow-logs
AIRFLOW__LOGGING__ENCRYPT_S3_LOGS: 'False'
AIRFLOW_CONN_MINIO_LOGS: "aws://minioadmin:minioadmin@?endpoint_url=http%3A%2F%2F${MAIN_VM_IP}%3A${MINIO_PORT}"
```

Note: on compute2, MinIO is referenced by private VLAN IP (`${MAIN_VM_IP}:${MINIO_PORT}`).

---

## Deploying Changes

### On the portal VM

```bash
cd ~/digitaltwins-platform/services/airflow
docker compose build
docker compose down && docker compose up -d
```

### On compute2

Build the updated image on the portal VM and copy it across:

```bash
# On portal VM
docker save digitaltwins-platform-airflow-worker:latest | gzip > airflow-worker.tar.gz
scp airflow-worker.tar.gz ubuntu@10.2.0.190:~

# On compute2
docker load < airflow-worker.tar.gz
docker compose down && docker compose up -d
```

---

## Verifying It Works

Trigger a DAG run and click on a task instance in the Airflow UI. You should see:

- Actual log content displayed
- Source shown as: `s3://airflow-logs/dag_id=.../run_id=.../task_id=.../attempt=1.log`

Instead of the previous error: `Error fetching logs. Try number 0 is invalid.`

---

## Known Warnings in Task Logs

When tasks use `ExternalPythonOperator` with a separate virtualenv (`cwl_venv`), two warnings appear:

### 1. `importlib.metadata.PackageNotFoundError: No package metadata was found for apache-airflow`

Airflow cannot find its own package metadata inside the venv. This is expected — Airflow is not installed in the venv. It is **harmless**.

### 2. `Airflow is not properly installed by /opt/airflow/venvs/cwl_venv/bin/python`

Same cause. The `ExternalPythonOperator` checks for Airflow in the venv and warns when it's missing.

**To suppress both warnings**, add `expect_airflow=False` to each `ExternalPythonOperator` in `workflow_image_conversion.py`:

```python
download_samples = ExternalPythonOperator(
    task_id="download_samples",
    python=VENV_PYTHON,
    python_callable=_run_download_samples,
    expect_airflow=False,   # suppress "Airflow not installed in venv" warning
    op_kwargs={...},
)
```

Apply the same to `dicom_to_nifti` and `dicom_to_nrrd` operators.

---

## MinIO UI

MinIO is proxied via nginx at `/minio/` — accessible at `https://${PLATFORM_DOMAIN}/minio/`.
Log in with `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD` from the platform `.env`.

To manage buckets from the CLI:

```bash
cd ~/digitaltwins-platform
docker compose exec minio sh -c \
  'mc alias set local http://localhost:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD \
   && mc ls --recursive local'
```
