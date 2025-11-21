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
