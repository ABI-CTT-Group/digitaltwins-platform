FROM python:3.11-slim

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
# sudo docker build -t api .
# running container
# sudo docker run --rm -d -p 8010:8000 api

# print docker image folder strcutre
# sudo docker run --rm api ls -l /api
# sudo docker run --rm api ls -lR /api
