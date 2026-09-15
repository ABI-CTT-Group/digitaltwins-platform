# Install Private nnUNet Packages into Airflow Docker Image

## Background

Two private GitHub packages need to be installed into the Airflow Docker image for ML inference tasks:

| Package | GitHub Repo | Commit SHA |
|---------|------------|------------|
| `nnunetv2` (fork) | `abi-breast-biomechanics-group/nnUNet-ranking-inference-extension` | `2405c743af0d` |
| `dynamic_network_architectures` (fork) | `abi-breast-biomechanics-group/dynamic-network-architectures-active-learning` | `25c18686ffce` |

`nnunetv2` depends on `dynamic-network-architectures>=0.2`. Since we're using a custom fork of `dynamic_network_architectures`, we install the fork first, then install the nnUNet fork.

## Design Decisions (from interview)

- **Install target**: New dedicated venv at `/opt/airflow/venvs/nnunet_venv` (isolates heavy ML deps from the lightweight `cwl_venv`)
- **Auth mechanism**: Docker BuildKit `--mount=type=secret` (token never persisted in image layers)
- **Version pinning**: Specific commit SHAs for reproducible builds
- **PyTorch**: Full CUDA 13.0 build (`cu130`) via `--extra-index-url https://download.pytorch.org/whl/cu130`

## Open Questions

> [!IMPORTANT]
> **GitHub PAT**: You will need a GitHub Personal Access Token (classic) with `repo` scope that can read both private repos. Do you already have one, or do you need to create one?

## Proposed Changes

### Airflow Service

#### [MODIFY] [Dockerfile](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/Dockerfile)

Add a new build stage after the existing `cwl_venv` block that:

1. Creates `/opt/airflow/venvs/nnunet_venv`
2. Installs PyTorch with CUDA 13.0 first (pinned via `--extra-index-url`)
3. Uses `--mount=type=secret,id=github_token` to read the PAT at build time
4. Installs `dynamic-network-architectures-active-learning` from the private repo (commit `25c18686ffce`)
5. Installs `nnUNet-ranking-inference-extension` from the private repo (commit `2405c743af0d`)
6. `chown`s the venv to the `airflow` user

```dockerfile
# ---------------------------------------------------------------------------
# nnUNet inference venv – heavy ML stack, isolated from cwl_venv.
# Requires BuildKit secret "github_token" containing a GitHub PAT with repo scope.
#   docker compose build --build-arg DOCKER_BUILDKIT=1 \
#     --secret id=github_token,src=$HOME/.secrets/github_token
# ---------------------------------------------------------------------------
RUN python3 -m venv /opt/airflow/venvs/nnunet_venv \
    && /opt/airflow/venvs/nnunet_venv/bin/pip install --no-cache-dir --upgrade pip

# Install PyTorch with CUDA 13.0 first so nnunet picks it up
RUN /opt/airflow/venvs/nnunet_venv/bin/pip install --no-cache-dir \
    torch torchvision torchaudio \
    --extra-index-url https://download.pytorch.org/whl/cu130

# Install private packages using BuildKit secret
RUN --mount=type=secret,id=github_token \
    GITHUB_TOKEN=$(cat /run/secrets/github_token) \
    && /opt/airflow/venvs/nnunet_venv/bin/pip install --no-cache-dir \
        "git+https://${GITHUB_TOKEN}@github.com/abi-breast-biomechanics-group/dynamic-network-architectures-active-learning.git@25c18686ffcecb8fc9ad4e37cc6700ad0a799b86" \
    && /opt/airflow/venvs/nnunet_venv/bin/pip install --no-cache-dir \
        "git+https://${GITHUB_TOKEN}@github.com/abi-breast-biomechanics-group/nnUNet-ranking-inference-extension.git@2405c743af0d095fddb7659632568e6b60e2068e"

RUN chown -R airflow: /opt/airflow/venvs/nnunet_venv
```

> [!NOTE]
> The `dynamic_network_architectures` fork is installed first. When `nnunetv2` installs and resolves `dynamic-network-architectures>=0.2`, pip sees that `dynamic_network_architectures==0.4.4b0` is already installed and satisfies the constraint, so it won't re-install the upstream package.

#### [MODIFY] [docker-compose.yml](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/docker-compose.yml)

No changes to docker-compose.yml itself. The secret is passed at build time via the CLI:

```bash
DOCKER_BUILDKIT=1 docker compose build \
  --secret id=github_token,src=$HOME/.secrets/github_token
```

---

### Documentation / Developer Notes

I'll add a comment block in the Dockerfile explaining:
- How to pass the secret at build time
- How to update commit SHAs when new versions are pushed
- How to use the venv in `ExternalPythonOperator` tasks: `python=/opt/airflow/venvs/nnunet_venv/bin/python`

## Verification Plan

### Manual Verification

1. **Build the image** with the secret:
   ```bash
   cd services/airflow
   DOCKER_BUILDKIT=1 docker compose build \
     --secret id=github_token,src=$HOME/.secrets/github_token
   ```
2. **Verify packages are installed**:
   ```bash
   docker run --rm <image> /opt/airflow/venvs/nnunet_venv/bin/pip list | grep -E "nnunetv2|dynamic"
   ```
3. **Verify the secret is NOT in image layers**:
   ```bash
   docker history <image>  # Should not contain the token
   ```
4. **Verify import works**:
   ```bash
   docker run --rm <image> /opt/airflow/venvs/nnunet_venv/bin/python -c "import nnunetv2; import dynamic_network_architectures; print('OK')"
   ```
