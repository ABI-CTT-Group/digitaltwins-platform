#!/bin/bash
# Creates the portal-backend role and the `portal` schema it owns in the main platform
# database. The role gets no other privileges: it cannot create schemas or touch the
# API's tables in `public`.
#
# Mounted as 05_portal.sh in docker-entrypoint-initdb.d/, so it runs automatically on
# first initialisation (empty postgres_data volume). It is idempotent, and re-running it
# resets the role's password to PORTAL_DB_PASSWORD. On an EXISTING volume, run it once by hand:
#
#   docker compose exec database bash /docker-entrypoint-initdb.d/05_portal.sh
set -euo pipefail
: "${PORTAL_DB_PASSWORD:?PORTAL_DB_PASSWORD must be set}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v portal_password="$PORTAL_DB_PASSWORD" <<'SQL'
SELECT 'CREATE ROLE portal LOGIN'
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'portal')\gexec
ALTER ROLE portal WITH LOGIN PASSWORD :'portal_password';
CREATE SCHEMA IF NOT EXISTS portal AUTHORIZATION portal;
SQL
