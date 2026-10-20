# Two images from one codebase (docs/decisions/2026-10-20-merge-portal-backend-into-api-codebase.md):
#   api      the platform REST API (app/ + src/); no build tooling
#   builder  the tool/workflow builder (builder/); git, Node and the Docker CLI for plugin builds.
#            It runs untrusted plugin builds next to the host Docker socket, so it must not derive
#            from the api stage or contain its code (tests/test_service_separation.py).
# Build one with: docker build --target api|builder .

FROM python:3.11-slim AS api

WORKDIR /api

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# copy files
COPY pyproject.toml .
COPY requirements-prod.txt .

# install python dependencies
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements-prod.txt

# copy application code
COPY src ./src
COPY app ./app

RUN pip install --no-cache-dir -e .

# Expose API port
EXPOSE 8000

# Run the app
#WORKDIR /api
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# building image
# sudo docker build --target api -t api .
# running container
# sudo docker run --rm -d -p 8010:8000 api

# print docker image folder strcutre
# sudo docker run --rm api ls -l /api
# sudo docker run --rm api ls -lR /api


FROM python:3.11-slim AS builder

WORKDIR /api

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    gcc \
    gnupg \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Node.js and yarn for plugin frontend builds (Volta)
ENV VOLTA_HOME="/root/.volta"
ENV PATH="$VOLTA_HOME/bin:$PATH"
RUN curl https://get.volta.sh | bash \
    && volta install node@22 yarn@1.22.22

# Docker CLI + compose plugin, for plugin deploys against the mounted host socket
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg \
    && . /etc/os-release && echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list \
    && apt-get update && apt-get install -y --no-install-recommends \
    docker-ce-cli \
    docker-compose-plugin \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-prod.txt requirements-builder.txt ./
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements-builder.txt

COPY builder ./builder

EXPOSE 8000

CMD ["uvicorn", "builder.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
