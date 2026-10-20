# The builder: the portal's tool/workflow builder (app/).
# It runs untrusted plugin builds next to the host Docker socket, so it is its own service
# with its own image and environment, apart from the platform API (services/api).
# docs/decisions/2026-10-21-builder-as-its-own-service.md

FROM python:3.11-slim

WORKDIR /app

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

COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
