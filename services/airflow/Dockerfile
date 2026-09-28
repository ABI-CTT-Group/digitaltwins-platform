FROM apache/airflow:3.0.6

# Install system dependencies
USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    vim \
    git \
    libpq-dev \
    build-essential \
    && apt-get autoremove -yqq --purge \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install user dependencies
USER airflow
RUN pip install --no-cache-dir digitaltwins==2.0a3
RUN pip uninstall -y asyncio

# ---------------------------------------------------------------------------
# Create an isolated virtual environment for ExternalPythonOperator tasks.
# The venv is placed at /opt/airflow/venvs/cwl_venv so that any task that
# runs via ExternalPythonOperator can reference:
#   python=/opt/airflow/venvs/cwl_venv/bin/python
# ---------------------------------------------------------------------------
USER root
RUN python3 -m venv /opt/airflow/venvs/cwl_venv \
    && /opt/airflow/venvs/cwl_venv/bin/pip install --no-cache-dir \
    boto3 \
    dicom2nifti \
    pydicom \
    SimpleITK \
    && chown -R airflow: /opt/airflow/venvs

# ---------------------------------------------------------------------------
# nnUNet inference venv – heavy ML stack, isolated from cwl_venv.
# OPTIONAL: skipped by default. To include, build with:
#   DOCKER_BUILDKIT=1 docker compose build \
#     --build-arg INSTALL_NNUNET=true \
#     --secret id=github_token,src=$HOME/.secrets/github_token
#
# Used by ExternalPythonOperator tasks via:
#   python=/opt/airflow/venvs/nnunet_venv/bin/python
#
# To update packages, replace the commit SHAs below and rebuild.
# ---------------------------------------------------------------------------
ARG INSTALL_NNUNET=false

RUN if [ "$INSTALL_NNUNET" = "true" ]; then \
    python3 -m venv /opt/airflow/venvs/nnunet_venv \
    && /opt/airflow/venvs/nnunet_venv/bin/pip install --no-cache-dir --upgrade pip; \
    fi

RUN if [ "$INSTALL_NNUNET" = "true" ]; then \
    /opt/airflow/venvs/nnunet_venv/bin/pip install --no-cache-dir \
        torch torchvision torchaudio \
        --extra-index-url https://download.pytorch.org/whl/cu130; \
    fi

RUN --mount=type=secret,id=github_token \
    if [ "$INSTALL_NNUNET" = "true" ]; then \
    GITHUB_TOKEN=$(cat /run/secrets/github_token) \
    && /opt/airflow/venvs/nnunet_venv/bin/pip install --no-cache-dir \
        "git+https://${GITHUB_TOKEN}@github.com/abi-breast-biomechanics-group/dynamic-network-architectures-active-learning.git@25c18686ffcecb8fc9ad4e37cc6700ad0a799b86" \
    && /opt/airflow/venvs/nnunet_venv/bin/pip install --no-cache-dir \
        "git+https://${GITHUB_TOKEN}@github.com/abi-breast-biomechanics-group/nnUNet-ranking-inference-extension.git@1cb0b4b1622b1727bf634bc67668acb2b482eab7" \
    && chown -R airflow: /opt/airflow/venvs/nnunet_venv; \
    fi

# boto3 — tool_inference.py reads its NIfTI input and model weights from MinIO
# and uploads the segmentations back, so the inference venv needs it too (the
# cwl_venv already has it). Kept in its own layer *after* the multi-GB torch and
# private-repo installs so adding or bumping it never invalidates their cache.
RUN if [ "$INSTALL_NNUNET" = "true" ]; then \
    /opt/airflow/venvs/nnunet_venv/bin/pip install --no-cache-dir boto3 \
    && chown -R airflow: /opt/airflow/venvs/nnunet_venv; \
    fi

USER airflow

