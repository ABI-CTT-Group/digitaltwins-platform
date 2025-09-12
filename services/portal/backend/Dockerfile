FROM python:3.9-slim

MAINTAINER LinkunGao<gaolinkun123@gmail.com>

WORKDIR /clinical_dashboard_backend

RUN apt-get update && apt-get install -y libpq-dev gcc

COPY backend/requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY configs.ini ./


EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]