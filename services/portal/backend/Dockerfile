FROM python:3.9-slim

# 基础依赖
RUN apt-get update && apt-get install -y \
    git \
    curl \
    gcc \
    libpq-dev \
    python3-dev \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && corepack enable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Add Docker official GPG
RUN curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker official software source (use VERSION_CODENAME from /etc/os-release)
RUN . /etc/os-release && echo \
  "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian ${VERSION_CODENAME} stable" \
  > /etc/apt/sources.list.d/docker.list

# Install docker CLI + compose plugin
RUN apt-get update && apt-get install -y \
    docker-ce-cli \
    docker-compose-plugin \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install uv from astral-sh
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy project
COPY . /app
WORKDIR /app

# Install dependencies with uv
RUN uv sync --frozen --no-cache

# Run FastAPI app
CMD ["uv", "run", "fastapi", "run", "app/main.py", "--port", "8000", "--host", "0.0.0.0"]
