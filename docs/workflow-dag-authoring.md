# Writing and deploying a script workflow DAG

A *script* workflow runs in Airflow. You ship its DAG inside the workflow
dataset; after you register the workflow, an admin deploys the DAG, and assay
runs then trigger it.

A complete, working example is
[`examples/workflow/workflow_image_conversion/`](../examples/workflow/workflow_image_conversion/).

## The one rule: don't choose a DAG id

An assay run triggers the DAG `workflow_<seek_id>`, where `seek_id` is the SEEK
id your workflow gets **when it is registered**. You can't know it while
writing the DAG, and it changes if the workflow is registered again.

So the platform deploys your `code/` folder to `dags/workflow_<seek_id>/`, and
your DAG names itself after that folder:

```python
from pathlib import Path

DAG_ID = Path(__file__).parent.name      # "workflow_<seek_id>" once deployed
TOOL_DIR = str(Path(__file__).parent)    # your tools ship next to this file

@dag(dag_id=DAG_ID, dag_display_name="Image conversion", schedule=None, ...)
def image_conversion():
    ...

image_conversion()
```

Use `dag_display_name` for the human-readable name shown in the Airflow UI.

The deploy step checks this statically, without running your code, and rejects
the DAG when:

- `dag_id` is anything other than `Path(__file__).parent.name`, written inline
  or through a module-level name such as `DAG_ID`. A literal like
  `"workflow_89"`, an f-string, or `Path(__file__).stem` is rejected.
- `dag_id` is missing. With `@dag()` or bare `@dag`, Airflow would silently use
  the function name.
- `code/` has no DAG, or more than one.
- The DAG file is in a subfolder of `code/`. It must sit directly in `code/`.
- The DAG file doesn't parse on Python 3.11. The check runs in the API
  container, which uses Python 3.11; Airflow uses 3.12.

To test locally, put the folder anywhere. The DAG takes that folder's name.

## Dataset layout

```
workflow_<name>/
  dataset_description.xlsx, manifest.xlsx, README.md, ...
  primary/
    workflow_<name>.cwl        # exactly one; steps run primary/tool_*.cwl
    tool_<step>.cwl
  code/
    workflow_<name>.py         # the DAG, directly in code/
    tool_<step>.py             # one per CWL tool (code/<stem>.* or code/<stem>/)
    any helper modules         # e.g. tool_download_samples.py
```

The whole `code/` folder is deployed. Airflow sees only the DAG file: the
platform writes an `.airflowignore` that hides every other `.py` file in the
folder, and replaces any `.airflowignore` you ship.

## Tasks and tools

- **Run tools in the task venv.** Run tool code with `ExternalPythonOperator`
  and `python="/opt/airflow/venvs/cwl_venv/bin/python"`. That venv has boto3,
  dicom2nifti, pydicom, SimpleITK, nibabel and numpy.
- **Pass the tool folder in.** The callable runs in a separate interpreter
  without `__file__`. Pass `TOOL_DIR` in `op_kwargs`, then import your tool by
  module name:

  ```python
  def _run_convert(tool_dir: str, ...):
      import sys
      sys.path.insert(0, tool_dir)
      from tool_convert import run
      return run(...)
  ```

  Each task gets its own interpreter, so tool modules with the same name in
  two workflows don't clash.
- **Stage under your DAG's id.** Use `DAG_ID` for staging prefixes, such as
  `airflow-workspace/<dag_id>/run_<n>/...`. Never hardcode an id.
- **Keep credentials out of the code.** Read MinIO credentials from the
  worker's environment: `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY` and
  `MINIO_SECRET_KEY`, which tasks inherit. Never pass them in `op_kwargs`,
  because Airflow shows task arguments in its UI. Never write a default value
  for a key in code.
- **Route to a queue.** Set `default_args={"queue": Variable.get("compute_queue", default_var="default")}`.
  That lets the platform route tasks to the remote compute node. See
  [diagnostics](diagnostics.md).

### What an assay run sends

An assay run starts one DAG run per input sample, with `dag_run.conf`:

| Key | Meaning |
|---|---|
| `bucket` | `airflow-workspace` |
| `subject_id`, `sample_id`, `sample_type`, `input_name` | the input sample |
| `dataset_uuid` | the measurement dataset it comes from |
| `run_id`, `run_index` | `workflow_<seek_id>/run_<n>` and `n` |
| `output_prefixes`, `output_name_by_sample_type` | where each output goes |

## Register, then deploy

1. **Register the workflow.** Use the portal's *Upload workflow* page, which
   needs approval, or call
   `POST /digitaltwins-api/datasets?category=workflows&workflow_type=script&seek_project_id=<id>`.
   The Workflow Hub card then shows `deploy · pending`.
2. **An admin deploys it.** Use *Deploy DAG* on the card, or call
   `POST /digitaltwins-api/workflows/{dataset_uuid}/deploy` with an admin token.
   The platform:
   1. checks the DAG and writes `dags/workflow_<seek_id>/`,
   2. waits for Airflow to load it (default 120 s,
      `AIRFLOW_DAG_DEPLOY_TIMEOUT`),
   3. unpauses it.
3. **Read the result.** The card shows one of these:
   - `deploy · deployed`: ready. Link the workflow to an assay and run it.
   - `deploy · failed`: hover over the chip for the reason. It is either the
     static-check message or Airflow's import error. Fix the code, register
     again, and deploy. A timeout says "deploy again to re-check": Airflow may
     simply be slow, and deploying again picks up a DAG that has since loaded.

Deploying is admin-only because DAG code runs inside Airflow with Airflow's
credentials. Deploying again replaces the folder. Deleting the workflow removes
it. Airflow keeps the old run history as a stale DAG.

Remote compute nodes don't see new DAG folders on their own. Run
`util/sync-compute-dags.sh` after deploying a workflow that runs on the remote
queue.

Background: [ADR 2026-10-13](decisions/2026-10-13-deploy-script-workflow-dags.md).
