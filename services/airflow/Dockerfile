FROM apache/airflow:3.0.6

# Install system dependencies
USER root

RUN apt-get update && apt-get install -y --no-install-recommends \
    vim \
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
    && chown -R airflow: /opt/airflow/venvs
USER airflow
