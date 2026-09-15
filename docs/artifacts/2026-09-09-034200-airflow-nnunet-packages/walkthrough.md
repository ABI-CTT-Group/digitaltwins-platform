# Walkthrough: Private nnUNet Packages in Airflow Image

## Changes Made

### [Dockerfile](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/Dockerfile)

Two modifications:

1. **Added `git` to system dependencies** (line 8) — required for `pip install git+https://...`

2. **Added `nnunet_venv` block** (lines 35–61) — a dedicated venv at `/opt/airflow/venvs/nnunet_venv` containing:
   - PyTorch with CUDA 13.0 (`cu130`)
   - `dynamic_network_architectures` fork @ `25c18686ffce`
   - `nnunetv2` fork @ `2405c743af0d`

The GitHub PAT is passed via BuildKit `--mount=type=secret` and never persisted in image layers.

## How to Build

1. **Create a GitHub PAT** (classic) with `repo` scope
2. **Save it** to a file:
   ```bash
   mkdir -p ~/.secrets
   echo "ghp_your_token_here" > ~/.secrets/github_token
   chmod 600 ~/.secrets/github_token
   ```
3. **Build**:
   ```bash
   cd services/airflow
   DOCKER_BUILDKIT=1 docker compose build \
     --secret id=github_token,src=$HOME/.secrets/github_token
   ```

## How to Use in DAGs

Reference the venv in `ExternalPythonOperator` tasks:

```python
ExternalPythonOperator(
    task_id="run_nnunet_inference",
    python="/opt/airflow/venvs/nnunet_venv/bin/python",
    python_callable=your_inference_function,
)
```

## Validation

- `docker build --check` passed with **no warnings**
- Full build verification deferred until GitHub PAT is created
