# Agent notes: services/airflow

Read the root AGENTS.md first; this file adds only what's specific to this service.

Layout, connections and configuration are in [README.md](README.md).

## Who owns what in `dags/`

| Path | Owner | Rule |
|---|---|---|
| `dags/workflow_<seek_id>/` | The platform API's deploy step (`services/api/src/digitaltwins/workflows/deploy.py`) | Never create, edit or delete these by hand or in a PR. Fix the workflow dataset and redeploy (portal *Deploy DAG*, or `POST /api/workflows/{dataset_uuid}/deploy`). The folder name is the DAG id; the API writes an `.airflowignore` that shows Airflow only the DAG file |
| `dags/cpu_burn_primes.py`, `dags/workflow_9000.py` | This repository (tracked despite the `.gitignore`) | Test and demo DAGs. `workflow_9000`'s id must match the SEEK id in `util/populate-cpu-burn-assay.sh` |
| Anything else in `dags/` | The host | Git-ignored and managed outside the repo, with `util/sync-dags.sh` |

`util/sync-runtime.sh` skips `dags/` entirely, so a change to the two tracked DAGs doesn't reach a
running host through it.

## Writing or changing a workflow DAG

- The contract with DAG authors is [docs/workflow-dag-authoring.md](../../docs/workflow-dag-authoring.md):
  `dag_id = Path(__file__).parent.name`, tools run through `ExternalPythonOperator` in
  `/opt/airflow/venvs/cwl_venv`, the queue comes from the `compute_queue` Variable, and MinIO
  credentials come from the worker's environment, never `op_kwargs`.
- The API checks a DAG statically before deploying it (`services/api/src/digitaltwins/workflows/dag.py`),
  on Python 3.11. Airflow itself runs Python 3.12.
- A package that task code needs goes into the `cwl_venv` step of the `Dockerfile`. All Airflow
  services build from that one image, so rebuild them together; a remote compute node needs the new
  worker image too.
- New DAG folders reach a remote compute node only through `util/sync-compute-dags.sh`.

## Compose files

- `docker-compose.yml` is Airflow's upstream file, adapted. Environment in the `x-airflow-common`
  block reaches every Airflow container, including the workers that run DAG code, so anything added
  there is readable by every workflow.
- Every service in `docker-compose.yml` has an entry in `network-override.yml`, which puts it on the
  platform network. A new service needs one too.
- The GPU reservation lives only in `gpu.override.yml`. `make test-util` fails if the base file gains
  one, because Docker won't start a container whose GPU it can't provide.
- There are no tests for the DAGs or this stack, and `make lint` doesn't cover `dags/`.
