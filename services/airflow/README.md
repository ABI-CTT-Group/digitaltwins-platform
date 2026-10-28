# Airflow

Runs script workflows as DAGs: Airflow 3.0.6 with the Celery executor, served at `/airflow`.

## Purpose

When an assay that uses a script workflow is launched, the API triggers that workflow's DAG,
`workflow_<seek_id>`, once per input sample. Workers run the tasks, read and write files in MinIO,
and ship their logs to MinIO. A remote compute node can run tasks too, through the `remote` queue.

## Status

Active. The root `docker-compose.yml` includes `docker-compose.yml` and `network-override.yml` from
this folder. `gpu.override.yml` and `remote-compute.override.yml` are added only when `util/gen-env.sh`
puts them in `COMPOSE_FILE`.

## Code map

The docker-compose.yaml file was fetched from https://airflow.apache.org/docs/apache-airflow/3.0.6/docker-compose.yaml (version: 3.0.6)

References:

- [Official Airflow installation](https://airflow.apache.org/docs/apache-airflow/stable/installation/index.html#installation-of-airflow)
- [Running Airflow in Docker](https://airflow.apache.org/docs/apache-airflow/stable/howto/docker-compose/index.html)

| Path | What it is |
|---|---|
| `docker-compose.yml` | The stack, adapted from that file: `redis`, `airflow-apiserver`, `-scheduler`, `-dag-processor`, `-worker`, `-triggerer`, `-init`, `-cli`, `flower`, and `minio-logs-init` (creates the `airflow-logs` bucket) |
| `network-override.yml` | Joins the services to the platform network |
| `gpu.override.yml` | Gives `airflow-worker` the host's NVIDIA GPU. Added when `AIRFLOW_WORKER_GPU` resolves to true |
| `remote-compute.override.yml` | Publishes the Redis broker port for a remote worker. Added when `REMOTE_COMPUTE=true` |
| `Dockerfile` | `apache/airflow:3.0.6`, plus the `digitaltwins` package from PyPI and a task venv at `/opt/airflow/venvs/cwl_venv` (boto3, dicom2nifti, pydicom, SimpleITK) |
| `config/airflow.cfg` | Airflow's configuration file |
| `config/webserver_config.py` | Keycloak sign-in for the UI; maps the realm roles `airflow_admin`, `airflow_op`, `airflow_user` and `airflow_viewer` to Airflow roles |
| `dags/` | The DAG folder. Git-ignored except for the two DAGs below |
| `dags/cpu_burn_primes.py` | A standalone test DAG, triggered from the Airflow UI |
| `dags/workflow_9000.py` | The "CPU Burn Assay" demo workflow, which runs on the `remote` queue |
| `logs/`, `plugins/` | Mounted into every Airflow container. `logs/` is git-ignored |
| `compute-worker/` | A remote compute node: one Celery worker that joins this stack over the network (see [util/compute-node-README.md](../../util/compute-node-README.md)) |

## DAG folders managed by the platform

`dags/workflow_<seek_id>/` folders are written by the platform API when an admin
registers or approves a script workflow, or deploys it
(`POST /workflows/{dataset_uuid}/deploy`), and removed
when the workflow is deleted. Don't edit them by hand: redeploy instead. See
[docs/workflow-dag-authoring.md](../../docs/workflow-dag-authoring.md).

## Connects to

| Peer | How |
|---|---|
| Postgres | The `airflow` database, for metadata and Celery results: `AIRFLOW_DB_USER`, `AIRFLOW_DB_PASSWORD`, `AIRFLOW_DB_NAME` |
| Redis | The stack's own `redis`, the Celery broker, password `REDIS_PASSWORD` |
| api | The API bind-mounts `dags/` at `/airflow-dags` and writes DAG folders there. It calls Airflow's REST API (`AIRFLOW_ENDPOINT`, `AIRFLOW_API_URL`) as the local user `AIRFLOW_USERNAME`, which `airflow-init` creates with `AIRFLOW_PASSWORD` |
| MinIO | Tasks get `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY` (from `MINIO_SERVER_*`). Task logs go to the `airflow-logs` bucket through `AIRFLOW_CONN_MINIO_LOGS` |
| Keycloak | UI sign-in through the `airflow` client (`AIRFLOW_KEYCLOAK_CLIENT_SECRET`). Tasks get `KEYCLOAK_*` for the `api` client's client-credentials grant |
| gateway | `/airflow/` → `airflow-apiserver:8080`; Airflow knows its prefix from `AIRFLOW__API__BASE_URL` |
| Remote compute node | Its worker reaches Redis, Postgres, MinIO and the execution API on the host's published ports; its `.env` comes from `util/generate-compute-env.sh` |

## Configuration

Set in the root `.env` (rendered from `.env.template`); the secrets come from `secrets.env`.

| Variable | Use |
|---|---|
| `AIRFLOW_UID` | Host user that owns the mounted files; `gen-env.sh` sets it to yours |
| `AIRFLOW_PORT` | Host port of the API server (8002) |
| `AIRFLOW__API__BASE_URL` | Public URL, `<protocol>://<domain>/airflow` |
| `AIRFLOW_DB_USER`, `AIRFLOW_DB_PASSWORD`, `AIRFLOW_DB_NAME` | Database login |
| `AIRFLOW__CORE__FERNET_KEY`, `REDIS_PASSWORD` | Required secrets |
| `AIRFLOW_KEYCLOAK_CLIENT_SECRET` | Required; the `airflow` client |
| `AIRFLOW_USERNAME`, `AIRFLOW_PASSWORD` | The local Airflow user the API signs in as (the platform admin) |
| `AIRFLOW_VAR_COMPUTE_QUEUE` | Becomes the Airflow Variable `compute_queue`: `default` for the local worker, `remote` for the compute node |
| `REMOTE_COMPUTE`, `AIRFLOW_WORKER_GPU` | In `env`, read by `util/gen-env.sh` to choose the override files |

## Run & test

First start: `docker compose up airflow-init` migrates the database and creates the admin user (see
[docs/deployment.md §4](../../docs/deployment.md#4-initialise-airflow)).

There are no tests of Airflow or of the DAGs, and `make lint` doesn't check `dags/`. Related checks
live elsewhere:

- The API's static DAG checks (`services/api/src/digitaltwins/workflows/dag.py`) are tested by
  `make test-api` (`tests/test_workflow_dag.py`).
- `make test-util` checks that the base compose file has no GPU reservation, and which override files
  `gen-env.sh` merges.

Debugging recipes are in [docs/diagnostics.md](../../docs/diagnostics.md).

## Gotchas

- **The image installs `digitaltwins` from PyPI** (a pinned release), not the code in `services/api`.
- **New DAGs start paused.** The platform's deploy unpauses them. The dag-processor rescans `dags/`
  every 30 seconds.
- **The API's Airflow login is not Keycloak.** It is a local user; if it is missing, assay launches
  fail with "invalid credentials" (see [REALM.md](../keycloak/REALM.md#operational-gotchas-learned-the-hard-way)).
- **Remote nodes don't see new DAG folders.** Run `util/sync-compute-dags.sh` after deploying a
  workflow that runs on the `remote` queue.
- **`dags/` is outside the repo's control.** `util/sync-runtime.sh` skips it; `util/sync-dags.sh`
  copies DAGs between hosts.
- The build declares a `github_token` secret, from `GITHUB_TOKEN`, for the nnUNet steps that are
  commented out in the `Dockerfile`.

## Related ADRs

- [Deploy script workflow DAGs from the platform](../../docs/decisions/2026-10-13-deploy-script-workflow-dags.md)
- [Airflow worker GPU is opt-in, detected automatically](../../docs/decisions/2026-10-23-airflow-worker-gpu-opt-in.md)
