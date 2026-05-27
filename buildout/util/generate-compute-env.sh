#!/bin/bash
# Generate a .env file for a remote Airflow compute worker.
#
# Usage:
#   bash generate-compute-env.sh <main_vm_ip> [platform_env]
#
# Example:
#   bash generate-compute-env.sh 10.2.0.170 > /tmp/compute.env
#   scp /tmp/compute.env ubuntu@10.2.0.190:~/digitaltwins-platform/.env
#
# main_vm_ip    — walled_garden IP of the platform VM (drai_mp: 10.2.0.170,
#                 drai_portal: 10.2.0.14)
# platform_env  — path to the platform .env (default: ~/digitaltwins-platform/.env)

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <main_vm_ip> [platform_env]" >&2
    exit 1
fi

MAIN_VM_IP=$1
PLATFORM_ENV=${2:-~/digitaltwins-platform/.env}

if [ ! -f "$PLATFORM_ENV" ]; then
    echo "ERROR: Platform .env not found at $PLATFORM_ENV" >&2
    exit 1
fi

set -a
# shellcheck disable=SC1090
source "$PLATFORM_ENV"
set +a

cat <<EOF
# .env for remote Airflow compute worker
# Generated from $PLATFORM_ENV on $(date)
# Do not commit this file — it contains secrets.

# This VM's walled_garden IP (used by compute nodes to reach the platform)
MAIN_VM_IP=${MAIN_VM_IP}
DIGITALTWINS_API_BASE_URL=http://${MAIN_VM_IP}

# Airflow UID — should match ownership of dags/logs/config/plugins/data
AIRFLOW_UID=${AIRFLOW_UID:-1001}

# Ports
AIRFLOW_PORT=${AIRFLOW_PORT}
AIRFLOW_POSTGRES_PORT=${AIRFLOW_POSTGRES_PORT}
REDIS_PORT=${REDIS_PORT}
MINIO_PORT=8011
DIGITALTWINS_API_PORT=${DIGITALTWINS_API_PORT}

# Secrets — must match the main platform .env exactly
AIRFLOW__CORE__FERNET_KEY=${AIRFLOW__CORE__FERNET_KEY}
AIRFLOW__API_AUTH__JWT_SECRET=${AIRFLOW__API_AUTH__JWT_SECRET}
AIRFLOW__API__SECRET_KEY=${AIRFLOW__API__SECRET_KEY}
AIRFLOW_POSTGRES_PASSWORD=${AIRFLOW_POSTGRES_PASSWORD}
REDIS_PASSWORD=${REDIS_PASSWORD}

# Airflow API credentials — must match _AIRFLOW_WWW_USER_USERNAME / AIRFLOW_PASSWORD on the platform
AIRFLOW_USERNAME=${_AIRFLOW_WWW_USER_USERNAME}
AIRFLOW_PASSWORD=${AIRFLOW_PASSWORD}

# MinIO credentials (MINIO_SERVER_ACCESS_KEY / MINIO_SERVER_SECRET_KEY on the platform)
MINIO_ACCESS_KEY=${MINIO_SERVER_ACCESS_KEY}
MINIO_SECRET_KEY=${MINIO_SERVER_SECRET_KEY}
EOF
