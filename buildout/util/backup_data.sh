#!/bin/bash
# Data-level backup — no downtime required, password-agnostic restore.
# matt.pestle@auckland.ac.nz
#
# Backs up:
#   - PostgreSQL (platform database)
#   - SEEK MySQL database
#   - SEEK filestore
#   - MinIO buckets
#
# Skips:
#   - SEEK Solr index  (rebuilt automatically on startup)
#   - SEEK cache       (disposable)
#
# Usage:
#   cd ~/digitaltwins-platform
#   bash buildout/util/backup_data.sh

set -euo pipefail

BASE_DIR=~/digitaltwins-platform
ENV_FILE=$BASE_DIR/.env

# Load .env for credentials
set -a
source "$ENV_FILE"
set +a

now=$(date +%Y%m%d%H%M)
BACKUP_DIR=~/backups/$now
mkdir -p "$BACKUP_DIR"
cd "$BACKUP_DIR"

echo "=== Backup started: $now ==="
echo "=== Destination: $BACKUP_DIR ==="

# ── PostgreSQL ────────────────────────────────────────────────────────────────
echo "--- Backing up PostgreSQL (digitaltwins)..."
docker exec digitaltwins-platform-database-1 \
    pg_dump -U "$POSTGRES_USER" --clean --if-exists "$POSTGRES_DB" \
    > postgres.sql
echo "    Done: postgres.sql"

echo "--- Backing up PostgreSQL (airflow)..."
docker exec digitaltwins-platform-database-1 \
    pg_dump -U "$POSTGRES_USER" --clean --if-exists "${AIRFLOW_DB_NAME:-airflow}" \
    > postgres_airflow.sql
echo "    Done: postgres_airflow.sql"

echo "--- Backing up PostgreSQL (keycloak)..."
docker exec digitaltwins-platform-database-1 \
    pg_dump -U "$POSTGRES_USER" --clean --if-exists "${KEYCLOAK_DB_USER:-keycloak}" \
    > postgres_keycloak.sql
echo "    Done: postgres_keycloak.sql"

# ── SEEK MySQL ────────────────────────────────────────────────────────────────
echo "--- Backing up SEEK MySQL..."
docker exec digitaltwins-platform-db-1 \
    mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" seek \
    > seek_mysql.sql
echo "    Done: seek_mysql.sql"

# ── SEEK filestore ────────────────────────────────────────────────────────────
echo "--- Backing up SEEK filestore..."
docker cp seek:/seek/filestore ./seek_filestore
echo "    Done: seek_filestore/"

# ── MinIO ─────────────────────────────────────────────────────────────────────
echo "--- Backing up MinIO buckets..."
MC_IMAGE=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep '/mc:' | head -1)
if [ -z "$MC_IMAGE" ]; then
    echo "    No mc image found locally, pulling quay.io/minio/mc:latest..."
    docker pull quay.io/minio/mc:latest
    MC_IMAGE="quay.io/minio/mc:latest"
fi
echo "    Using mc image: $MC_IMAGE"
docker run --rm --network digitaltwins \
    -v "$BACKUP_DIR/minio":/minio_backup \
    -e MINIO_ROOT_USER="$MINIO_ROOT_USER" \
    -e MINIO_ROOT_PASSWORD="$MINIO_ROOT_PASSWORD" \
    --entrypoint /bin/sh \
    "$MC_IMAGE" \
    -c '
        mc alias set src http://minio:9000 $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD &&
        for bucket in $(mc ls src | while read a b c d name; do echo $name; done | tr -d "/"); do
            if [ "$bucket" = "airflow-logs" ]; then
                echo "  Skipping bucket: $bucket"
                continue
            fi
            echo "  Mirroring bucket: $bucket"
            mc mirror src/$bucket /minio_backup/$bucket || true
        done
    '
echo "    Done: minio/"

# ── MinIO mc image (needed for airgapped restore) ────────────────────────────
echo "--- Saving MinIO mc image..."
docker save "$MC_IMAGE" | gzip > minio_mc_image.tar.gz
echo "    Done: minio_mc_image.tar.gz"

# ── Airflow DAGs ──────────────────────────────────────────────────────────────
echo "--- Backing up Airflow DAGs..."
tar cf dags.tar -C "$BASE_DIR/services/airflow" dags
echo "    Done: dags.tar"

# ── Write restore script ──────────────────────────────────────────────────────
cat > restore.sh << EOF
#!/bin/bash
# DigitalTWINS Platform — Data Restore
# Created from backup: $now
# Source host: $(hostname)
#
# Contents of this backup:
#   postgres.sql          — Platform PostgreSQL database (digitaltwins)
#   postgres_airflow.sql  — Airflow PostgreSQL database
#   postgres_keycloak.sql — Keycloak PostgreSQL database
#   seek_mysql.sql        — SEEK MySQL database dump
#   seek_filestore/       — SEEK uploaded files
#   minio/                — MinIO bucket contents
#   dags.tar              — Airflow DAG files
#
# Usage:
#   Copy this directory to the target machine, then:
#   cd /path/to/this/directory
#   bash restore.sh
#
# The target system must be fully up before running this script.
# (docker compose up -d && wait for all services healthy)
# This script uses the target system's own credentials — no need to match the source.

set -euo pipefail

# Load target system credentials
BASE_DIR=\${BASE_DIR:-~/digitaltwins-platform}
set -a
source "\$BASE_DIR/.env"
set +a

RESTORE_DIR=\$(cd \$(dirname "\$0") && pwd)

echo "=== Restore started ==="
echo "=== Source: \$RESTORE_DIR ==="

# ── Step 1: Load mc image (required for MinIO restore on airgapped systems) ──
echo "--- Loading MinIO mc image..."
docker load < "\$RESTORE_DIR/minio_mc_image.tar.gz"
echo "    Done."

# ── Step 2: PostgreSQL ────────────────────────────────────────────────────────
echo "--- Restoring PostgreSQL (digitaltwins)..."
docker exec digitaltwins-platform-database-1 \\
    psql -U "\$POSTGRES_USER" postgres \\
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '\$POSTGRES_DB';" \\
    -c "DROP DATABASE IF EXISTS \"\$POSTGRES_DB\";" \\
    -c "CREATE DATABASE \"\$POSTGRES_DB\";"
docker exec -i digitaltwins-platform-database-1 \\
    psql -U "\$POSTGRES_USER" "\$POSTGRES_DB" < "\$RESTORE_DIR/postgres.sql"
echo "    Done."

echo "--- Restoring PostgreSQL (airflow)..."
docker exec digitaltwins-platform-database-1 \\
    psql -U "\$POSTGRES_USER" postgres \\
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '\${AIRFLOW_DB_NAME:-airflow}';" \\
    -c "DROP DATABASE IF EXISTS \"\${AIRFLOW_DB_NAME:-airflow}\";" \\
    -c "CREATE DATABASE \"\${AIRFLOW_DB_NAME:-airflow}\" OWNER \"\${AIRFLOW_DB_USER:-airflow}\";"
docker exec -i digitaltwins-platform-database-1 \\
    psql -U "\$POSTGRES_USER" "\${AIRFLOW_DB_NAME:-airflow}" < "\$RESTORE_DIR/postgres_airflow.sql"
echo "    Done."

echo "--- Restoring PostgreSQL (keycloak)..."
docker exec digitaltwins-platform-database-1 \\
    psql -U "\$POSTGRES_USER" postgres \\
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '\${KEYCLOAK_DB_USER:-keycloak}';" \\
    -c "DROP DATABASE IF EXISTS \"\${KEYCLOAK_DB_USER:-keycloak}\";" \\
    -c "CREATE DATABASE \"\${KEYCLOAK_DB_USER:-keycloak}\" OWNER \"\${KEYCLOAK_DB_USER:-keycloak}\";"
docker exec -i digitaltwins-platform-database-1 \\
    psql -U "\$POSTGRES_USER" "\${KEYCLOAK_DB_USER:-keycloak}" < "\$RESTORE_DIR/postgres_keycloak.sql"
echo "    Done."

# ── Step 3: SEEK MySQL ────────────────────────────────────────────────────────
echo "--- Restoring SEEK MySQL..."
docker exec digitaltwins-platform-db-1 \\
    mysql -u root -p"\$MYSQL_ROOT_PASSWORD" \\
    -e "DROP DATABASE IF EXISTS seek; CREATE DATABASE seek CHARACTER SET utf8mb4;"
docker exec -i digitaltwins-platform-db-1 \\
    mysql -u root -p"\$MYSQL_ROOT_PASSWORD" seek < "\$RESTORE_DIR/seek_mysql.sql"
echo "    Done."

# ── Step 4: SEEK filestore ────────────────────────────────────────────────────
echo "--- Restoring SEEK filestore..."
docker cp "\$RESTORE_DIR/seek_filestore/." seek:/seek/filestore/
echo "    Done."

# ── Step 5: MinIO buckets ─────────────────────────────────────────────────────
echo "--- Restoring MinIO buckets..."
MC_IMAGE=\$(docker images --format '{{.Repository}}:{{.Tag}}' | grep '/mc:' | head -1)
if [ -z "\$MC_IMAGE" ]; then
    echo "ERROR: no mc image found. Ensure minio_mc_image.tar.gz was loaded."
    exit 1
fi
echo "    Using mc image: \$MC_IMAGE"
docker run --rm --network digitaltwins \\
    -v "\$RESTORE_DIR/minio":/minio_backup \\
    -e MINIO_ROOT_USER="\$MINIO_ROOT_USER" \\
    -e MINIO_ROOT_PASSWORD="\$MINIO_ROOT_PASSWORD" \\
    --entrypoint /bin/sh \\
    "\$MC_IMAGE" \\
    -c '
        mc alias set dst http://minio:9000 \$MINIO_ROOT_USER \$MINIO_ROOT_PASSWORD &&
        for bucket in \$(ls /minio_backup); do
            echo "  Creating bucket: \$bucket"
            mc mb --ignore-existing dst/\$bucket
            echo "  Mirroring bucket: \$bucket"
            mc mirror /minio_backup/\$bucket dst/\$bucket || true
        done
    '
echo "    Done."

# ── Step 6: Airflow DAGs ─────────────────────────────────────────────────────
echo "--- Restoring Airflow DAGs..."
tar xf "\$RESTORE_DIR/dags.tar" -C "\$BASE_DIR/services/airflow"
echo "    Done."

# ── Step 7: Restart SEEK to rebuild Solr index ───────────────────────────────
echo "--- Restarting SEEK to rebuild Solr search index..."
docker compose restart seek workers
echo "    Done."

echo "=== Restore complete ==="
EOF

chmod +x restore.sh

echo "    Done: restore.sh"
echo "=== Backup complete: $BACKUP_DIR ==="
