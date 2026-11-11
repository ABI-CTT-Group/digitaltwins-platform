#!/usr/bin/env bash
# gen-new-secrets.sh — write install_src/data/{env,secrets.env} for the demo
# deployment with ALL-NEW secret values. Never prints a secret to stdout.
#
# Exceptions (documented in DEPLOYMENT.md):
#   AIRFLOW_DB_PASSWORD=airflow / KEYCLOAK_DB_PASSWORD=keycloak — hardcoded in
#   services/postgres/{airflow,keycloak}_init.sql; new values break a fresh
#   install. Both are reachable only on the internal docker network.
set -euo pipefail

DATA_DIR="${1:?usage: gen-new-secrets.sh <install_src/data dir>}"
mkdir -p "$DATA_DIR"
umask 077

rand() { openssl rand -hex 32; }

cat > "$DATA_DIR/env" <<EOF
# demo deployment — http/localhost (browse on the server or via SSH tunnel)
export PLATFORM_PROTOCOL=http
export PLATFORM_DOMAIN=localhost
export KC_HOSTNAME_STRICT=false
export KC_HOSTNAME_STRICT_HTTPS=false

REMOTE_COMPUTE=false
AIRFLOW_VAR_COMPUTE_QUEUE=default

export PLATFORM_ADMIN_USERNAME=admin1
export PLATFORM_ADMIN_EMAIL=admin@localhost.local
EOF

# Human-typable admin password (new, replaces the old one everywhere)
ADMIN_PW="$(openssl rand -base64 15 | tr '+/' '-_')"

# MinIO: every platform S3 client (airflow, portal, api, mc jobs) authenticates
# as MINIO_ROOT_USER with MINIO_SERVER_SECRET_KEY, and MinIO itself only honors
# MINIO_ROOT_PASSWORD — the two MUST be the same value or all S3 access 403s.
MINIO_PW="$(rand)"

FERNET="$(python3 - <<'PY'
import base64, os
print(base64.urlsafe_b64encode(os.urandom(32)).decode())
PY
)"

cat > "$DATA_DIR/secrets.env" <<EOF
KC_BOOTSTRAP_ADMIN_PASSWORD=$(rand)
POSTGRES_PASSWORD=$(rand)
PORTAL_DB_PASSWORD=$(rand)
PGADMIN_DEFAULT_PASSWORD=$(rand)
MINIO_ROOT_PASSWORD=${MINIO_PW}
MINIO_SERVER_SECRET_KEY=${MINIO_PW}
PLATFORM_ADMIN_PASSWORD=${ADMIN_PW}
AIRFLOW_DB_PASSWORD=airflow
JUPYTERHUB_CLIENT_SECRET=$(rand)
JUPYTERHUB_CRYPT_KEY=$(rand)
JUPYTERHUB_API_TOKEN=$(rand)
ORTHANC_AUTH_SERVICE_PASSWORD=$(rand)
ORTHANC_AUTH_SECRET_KEY=$(rand)
ORTHANC_KEYCLOAK_CLIENT_SECRET=$(rand)
KEYCLOAK_CLIENT_SECRET=$(rand)
MYSQL_ROOT_PASSWORD=$(rand)
MYSQL_PASSWORD=$(rand)
KEYCLOAK_DB_PASSWORD=keycloak
AIRFLOW__CORE__FERNET_KEY=${FERNET}
AIRFLOW__API_AUTH__JWT_SECRET=$(rand)
AIRFLOW__API__SECRET_KEY=$(rand)
AIRFLOW_KEYCLOAK_CLIENT_SECRET=$(rand)
MINIO_KEYCLOAK_CLIENT_SECRET=$(rand)
REDIS_PASSWORD=$(rand)
MIMIR_MINIO_ROOT_USER=mimir
MIMIR_MINIO_SECRET_KEY=$(rand)
GRAFANA_ADMIN_PASSWORD=$(rand)
GRAFANA_OAUTH_SECRET=$(rand)
SEEK_KEYCLOAK_CLIENT_SECRET=$(rand)
EOF

chmod 600 "$DATA_DIR/secrets.env"
echo "wrote $DATA_DIR/env and $DATA_DIR/secrets.env (600). Admin password is in secrets.env (PLATFORM_ADMIN_PASSWORD) — not printed."
# sanity: every key non-empty
awk -F= 'NF<2 || $2=="" {print "EMPTY: "$1; bad=1} END{exit bad}' "$DATA_DIR/secrets.env" && echo "all keys non-empty"
# sanity: no value reused from the CURRENT deployment's secrets
OLD=/home/clin864/Projects/digitaltwins-platform/secrets.env
if [ -f "$OLD" ]; then
  dup=$(grep -oP '(?<==).+' "$OLD" | sort -u | grep -Fxf - <(grep -oP '(?<==).+' "$DATA_DIR/secrets.env" | grep -vx 'airflow\|keycloak\|mimir') || true)
  [ -z "$dup" ] && echo "no old secret values reused (except documented airflow/keycloak defaults)" || { echo "ERROR: a value matches the old secrets.env"; exit 1; }
fi
