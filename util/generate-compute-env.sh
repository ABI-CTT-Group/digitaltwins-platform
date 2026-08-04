#!/usr/bin/env bash
# Generate the .env for a remote Airflow compute node FROM the running platform's
# .env, so the node's shared secrets (Fernet, DB, Redis, MinIO) match the portal
# automatically. Run this ON THE PORTAL.
#
#   util/generate-compute-env.sh <portal_vlan_ip> [platform_env] > compute.env
#     e.g.  util/generate-compute-env.sh 10.2.0.14 > /tmp/compute.env
#
# platform_env defaults to the runtime ~/digitaltwins-platform/.env. Copy the
# output to the compute node as ~/digitaltwins-compute/.env, then set WORKER_QUEUES
# there (e.g. gpu) if this node should serve a non-default queue.
#
# Ports below are the portal's PUBLISHED host ports (see compute-node-README.md):
#   postgres 8003 · redis 8005 · airflow apiserver/execution 8002 · minio 8011 ·
#   digitaltwins-api 8010.  Redis (8005) is only reachable once the portal's Redis
#   is published + password-protected — see the README "portal side" step.
set -euo pipefail

MAIN_VM_IP="${1:?usage: generate-compute-env.sh <portal_vlan_ip> [platform_env]}"
PLATFORM_ENV="${2:-$HOME/digitaltwins-platform/.env}"
[ -f "$PLATFORM_ENV" ] || { echo "generate-compute-env: platform .env not found: $PLATFORM_ENV" >&2; exit 1; }

set -a
# shellcheck disable=SC1090
. "$PLATFORM_ENV"
set +a

# Fail loudly if a secret the worker must share with the portal is missing.
: "${AIRFLOW__CORE__FERNET_KEY:?not set in $PLATFORM_ENV}"
: "${AIRFLOW_DB_PASSWORD:?not set in $PLATFORM_ENV}"
: "${REDIS_PASSWORD:?not set in $PLATFORM_ENV — harden/publish Redis on the portal first}"
: "${MINIO_SERVER_ACCESS_KEY:?not set in $PLATFORM_ENV}"
: "${MINIO_SERVER_SECRET_KEY:?not set in $PLATFORM_ENV}"
: "${PLATFORM_DOMAIN:?not set in $PLATFORM_ENV}"
: "${KEYCLOAK_CLIENT_SECRET:?not set in $PLATFORM_ENV}"

cat <<EOF
# Remote Airflow compute node .env — generated from $PLATFORM_ENV on $(date -u +%FT%TZ)
# DO NOT COMMIT — contains secrets.

# Portal VLAN address + public domain (the domain is used for the gateway-routed
# HTTP services — execution API + Keycloak — and must resolve to MAIN_VM_IP on the
# node, e.g. via /etc/hosts). Set WORKER_QUEUES to the queue this node serves (gpu).
MAIN_VM_IP=${MAIN_VM_IP}
PLATFORM_DOMAIN=${PLATFORM_DOMAIN}
PLATFORM_PROTOCOL=${PLATFORM_PROTOCOL:-https}
WORKER_QUEUES=${WORKER_QUEUES:-default}
AIRFLOW_UID=${AIRFLOW_UID:-50000}

# Portal published host ports.
AIRFLOW_PORT=${AIRFLOW_PORT:-8002}
AIRFLOW_POSTGRES_PORT=8003
REDIS_PORT=8005
MINIO_PORT=8011
# Hardcoded like the other published ports above — do NOT inherit the platform's
# DIGITALTWINS_API_PORT (that's the API's INTERNAL 8000; over the VLAN it's 8010).
DIGITALTWINS_API_PORT=8010

# Airflow metadata DB (shared postgres on the portal) — must match the platform.
AIRFLOW_DB_USER=${AIRFLOW_DB_USER:-airflow}
AIRFLOW_DB_NAME=${AIRFLOW_DB_NAME:-airflow}
AIRFLOW_DB_PASSWORD=${AIRFLOW_DB_PASSWORD}

# Shared secrets — MUST equal the platform's.
AIRFLOW__CORE__FERNET_KEY=${AIRFLOW__CORE__FERNET_KEY}
REDIS_PASSWORD=${REDIS_PASSWORD}
MINIO_SERVER_ACCESS_KEY=${MINIO_SERVER_ACCESS_KEY}
MINIO_SERVER_SECRET_KEY=${MINIO_SERVER_SECRET_KEY}

# Keycloak (token issuer for DAG -> platform-API auth) — public gateway URL, so the
# node reaches a resolvable, canonical issuer (not the internal 'keycloak' host).
KEYCLOAK_INTERNAL_URL=${PLATFORM_PROTOCOL:-https}://${PLATFORM_DOMAIN}/auth
KEYCLOAK_REALM=${KEYCLOAK_REALM:-digitaltwins}
KEYCLOAK_CLIENT_ID=${KEYCLOAK_CLIENT_ID:-api}
KEYCLOAK_CLIENT_SECRET=${KEYCLOAK_CLIENT_SECRET}
EOF
