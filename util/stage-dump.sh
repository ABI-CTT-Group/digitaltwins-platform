#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# stage-dump.sh — READ-ONLY dump of a DigitalTWINS instance for migration.
#
# Run this ON THE SOURCE box. It mutates nothing on the source (no compose
# down, volumes mounted read-only) and writes all archives under OUT
# (default /tmp/dtwins-migrate). Pair it with portal-restore.sh on the target.
#
# Covers:  digitaltwins DB, HAPI FHIR DB, SEEK (mysql + filestore), MinIO
#          buckets, portal plugin registry, gateway plugin route configs,
#          JupyterHub per-user volumes, Orthanc DICOM volumes.
# Does NOT cover:  Keycloak (H2 here vs Postgres on the portal — migrate via a
#          realm export/import instead), Airflow metadata (runtime state), and
#          Airflow DAGs (managed outside the repo — use sync-dags.sh).
#
# Credentials are read from the containers' own env, so this works regardless
# of how each box names things in .env.
#
#   util/stage-dump.sh [OUT_DIR]
#
# Container/volume names default to the `digitaltwins-platform` compose project;
# override via the PROJECT / *_C / *_VOLS env vars if yours differ.
# ---------------------------------------------------------------------------
set -euo pipefail

OUT="${1:-/tmp/dtwins-migrate}"
PROJECT="${PROJECT:-digitaltwins-platform}"
NETWORK="${NETWORK:-$PROJECT}"
DB_C="${DB_C:-${PROJECT}-database-1}"          # shared Postgres (digitaltwins, ...)
SEEKDB_C="${SEEKDB_C:-${PROJECT}-db-1}"        # SEEK MySQL
SEEK_C="${SEEK_C:-${PROJECT}-seek-1}"
PORTAL_BE_C="${PORTAL_BE_C:-${PROJECT}-portal-backend-1}"
MINIO_C="${MINIO_C:-${PROJECT}-minio-1}"
HAPI_PG_C="${HAPI_PG_C:-hapi-fhir-postgres}"   # separate pg on some layouts; "" to skip
ORTHANC_VOLS="${ORTHANC_VOLS:-${PROJECT}_orthanc_1_data ${PROJECT}_orthanc_2_data}"
MC_IMAGE="${MC_IMAGE:-quay.io/minio/mc:latest}"
PLUGIN_CONF_VOL="${PLUGIN_CONF_VOL:-${PROJECT}_nginx_plugin_configs}"   # gateway plugin route configs
JUSER_VOL_PREFIX="${JUSER_VOL_PREFIX:-${PROJECT}_jupyterhub_user_}"     # per-user notebook volumes

mkdir -p "$OUT"
OUT="$(cd "$OUT" && pwd)"   # absolutise: the docker -v bind mounts below require absolute paths
echo "stage-dump: source project '$PROJECT' -> $OUT"

# Guard against the silent trap this tool exists to avoid: a dump that "succeeds"
# (exit 0) but captured an empty or wrong database — e.g. pg_dump of a container
# whose POSTGRES_DB isn't the data DB emits a header-only file. Shipping that
# empty .sql makes portal-restore no-op silently and lose the data. Fail loudly.
assert_sql_has_data() {  # $1=file  $2=label
  [ -s "$1" ] || { echo "FATAL: $2 dump '$1' is empty — wrong or unreachable source DB?" >&2; exit 1; }
  grep -qiE 'CREATE TABLE|INSERT INTO|^COPY ' "$1" || {
    echo "FATAL: $2 dump '$1' has no schema/data (no CREATE TABLE/COPY/INSERT) — likely an empty or wrong database." >&2
    exit 1
  }
}

# 1. Platform Postgres DB (digitaltwins) --------------------------------------
echo "== digitaltwins DB =="
docker exec "$DB_C" sh -c \
  'pg_dump -U "$POSTGRES_USER" --clean --if-exists "${POSTGRES_DB:-digitaltwins}"' \
  > "$OUT/digitaltwins.sql"
assert_sql_has_data "$OUT/digitaltwins.sql" "digitaltwins"

# 2. HAPI FHIR DB (its own Postgres on staging; folded into shared pg on portal)
if [ -n "$HAPI_PG_C" ] && docker ps --format '{{.Names}}' | grep -qx "$HAPI_PG_C"; then
  echo "== hapi DB (from $HAPI_PG_C) =="
  docker exec "$HAPI_PG_C" sh -c \
    'pg_dump -U "$POSTGRES_USER" --clean --if-exists "${POSTGRES_DB:-hapi}"' \
    > "$OUT/hapi.sql"
  assert_sql_has_data "$OUT/hapi.sql" "hapi"
else
  echo "== hapi: no container '$HAPI_PG_C'; skipping (set HAPI_PG_C to override) =="
fi

# 3. SEEK MySQL ---------------------------------------------------------------
echo "== seek mysql =="
docker exec "$SEEKDB_C" sh -c 'unset MYSQL_HOST; exec mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" seek' \
  > "$OUT/seek_mysql.sql"
assert_sql_has_data "$OUT/seek_mysql.sql" "seek mysql"

# 4. SEEK filestore -----------------------------------------------------------
echo "== seek filestore =="
rm -rf "$OUT/seek_filestore"; mkdir -p "$OUT/seek_filestore"
docker cp "$SEEK_C:/seek/filestore/." "$OUT/seek_filestore/"

# 5. Portal plugin registry (SQLite) ------------------------------------------
echo "== plugin registry =="
docker cp "$PORTAL_BE_C:/data/plugin_registry.db" "$OUT/plugin_registry.db"

# 6. MinIO buckets ------------------------------------------------------------
# The minio/mc image is minimal (no awk/sed/ls), so enumerate buckets on the
# HOST side of the pipe and run mc per bucket in the container.
echo "== minio =="
rm -rf "$OUT/minio"; mkdir -p "$OUT/minio"
MINIO_USER=$(docker exec "$MINIO_C" printenv MINIO_ROOT_USER)
MINIO_PASS=$(docker exec "$MINIO_C" printenv MINIO_ROOT_PASSWORD)
mc_run() {  # run an mc command in the container with src aliased + /backup mounted
  docker run --rm --network "$NETWORK" -v "$OUT/minio":/backup \
    -e A="$MINIO_USER" -e B="$MINIO_PASS" --entrypoint /bin/sh "$MC_IMAGE" \
    -c "mc alias set src http://minio:9000 \"\$A\" \"\$B\" >/dev/null && $1"
}
buckets=$(mc_run 'mc ls src' | awk '{print $NF}' | tr -d '/')
for b in $buckets; do
  [ "$b" = "airflow-logs" ] && { echo "  skip $b"; continue; }
  echo "  mirror $b"
  # No '|| true' — a mirror failure aborts the whole dump via set -e, so we never
  # produce a silent partial.
  mc_run "mc mirror src/$b /backup/$b"
done

# 7. Orthanc DICOM volumes (read-only tar) ------------------------------------
echo "== orthanc dicom =="
for v in $ORTHANC_VOLS; do
  if ! docker volume inspect "$v" >/dev/null 2>&1; then echo "  no volume $v; skip"; continue; fi
  echo "  tar $v"
  docker run --rm -v "$v":/v:ro -v "$OUT":/backup alpine tar -C /v -cf "/backup/${v}.tar" .
done

# 8. Gateway plugin route configs (nginx_plugin_configs volume) ---------------
echo "== plugin nginx configs =="
if docker volume inspect "$PLUGIN_CONF_VOL" >/dev/null 2>&1; then
  docker run --rm -v "$PLUGIN_CONF_VOL":/v:ro -v "$OUT":/backup alpine \
    tar -C /v -cf "/backup/nginx_plugin_configs.tar" .
else
  echo "  no volume $PLUGIN_CONF_VOL; skip"
fi

# 9. JupyterHub per-user volumes (dynamic — one per user that has logged in) ---
echo "== jupyterhub user volumes =="
rm -rf "$OUT/jupyter_user_vols"; mkdir -p "$OUT/jupyter_user_vols"
for v in $(docker volume ls --format '{{.Name}}' | grep -E "^${JUSER_VOL_PREFIX}" || true); do
  echo "  tar $v"
  docker run --rm -v "$v":/v:ro -v "$OUT/jupyter_user_vols":/backup alpine \
    tar -C /v -cf "/backup/${v}.tar" .
done

# The mc / alpine / docker-cp helper containers ran as root, so parts of OUT are
# root-owned. Hand the whole tree back to the invoking user (via a root container
# — no host sudo needed) so a plain tar/rsync as the user captures every file
# instead of silently skipping the root-owned ones.
docker run --rm -v "$OUT":/out alpine chown -R "$(id -u)":"$(id -g)" /out

echo "stage-dump: done."
du -sh "$OUT"/* 2>/dev/null || true
echo "Next: copy $OUT to the target and run util/portal-restore.sh there."
