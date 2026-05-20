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
echo "--- Backing up PostgreSQL..."
docker exec digitaltwins-platform-database-1 \
    pg_dump -U "$POSTGRES_USER" --clean --if-exists "$POSTGRES_DB" \
    > postgres.sql
echo "    Done: postgres.sql"

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
docker run --rm --network digitaltwins \
    -v "$BACKUP_DIR/minio":/minio_backup \
    --entrypoint /bin/sh \
    quay.io/minio/mc:latest \
    -c "
        mc alias set src http://minio:9000 '$MINIO_ROOT_USER' '$MINIO_ROOT_PASSWORD' &&
        for bucket in measurements models workflows processes tools; do
            echo \"  Mirroring bucket: \$bucket\" &&
            mc mirror src/\$bucket /minio_backup/\$bucket || true
        done
    "
echo "    Done: minio/"

# ── MinIO mc image (needed for airgapped restore) ────────────────────────────
echo "--- Saving MinIO mc image..."
MC_IMAGE=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep '/mc:' | head -1)
if [ -z "$MC_IMAGE" ]; then
    echo "    WARNING: no mc image found locally, pulling quay.io/minio/mc:latest..."
    docker pull quay.io/minio/mc:latest
    MC_IMAGE="quay.io/minio/mc:latest"
fi
echo "    Using: $MC_IMAGE"
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
#   postgres.sql      — Platform PostgreSQL database dump
#   seek_mysql.sql    — SEEK MySQL database dump
#   seek_filestore/   — SEEK uploaded files
#   minio/            — MinIO bucket contents (measurements, models, workflows, processes, tools)
#   dags.tar          — Airflow DAG files
#
# Usage:
#   Copy this directory to the target machine, then:
#   cd /path/to/this/directory
#   bash restore.sh
#
# The target system must be up and running before restoring.
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
# Ensure it's available under the name used in the restore command
docker tag \$(docker images --format '{{.Repository}}:{{.Tag}}' | grep '/mc:' | head -1) quay.io/minio/mc:latest 2>/dev/null || true
echo "    Done."

# ── Step 2: Make sure platform is up ─────────────────────────────────────────
echo "--- Ensuring platform is up..."
cd "\$BASE_DIR"
docker compose up -d
echo "    Waiting 15s for services to be ready..."
sleep 15

# ── Step 3: PostgreSQL ────────────────────────────────────────────────────────
echo "--- Restoring PostgreSQL..."
docker exec digitaltwins-platform-database-1 \\
    psql -U "\$POSTGRES_USER" postgres \\
    -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '\$POSTGRES_DB'; DROP DATABASE IF EXISTS \"\$POSTGRES_DB\"; CREATE DATABASE \"\$POSTGRES_DB\";"
docker exec -i digitaltwins-platform-database-1 \\
    psql -U "\$POSTGRES_USER" "\$POSTGRES_DB" < "\$RESTORE_DIR/postgres.sql"
echo "    Done."

# ── Step 4: SEEK MySQL ────────────────────────────────────────────────────────
echo "--- Restoring SEEK MySQL..."
docker exec digitaltwins-platform-db-1 \\
    mysql -u root -p"\$MYSQL_ROOT_PASSWORD" \\
    -e "DROP DATABASE IF EXISTS seek; CREATE DATABASE seek CHARACTER SET utf8mb4;"
docker exec -i digitaltwins-platform-db-1 \\
    mysql -u root -p"\$MYSQL_ROOT_PASSWORD" seek < "\$RESTORE_DIR/seek_mysql.sql"
echo "    Done."

# ── Step 5: SEEK filestore ────────────────────────────────────────────────────
echo "--- Restoring SEEK filestore..."
docker cp "\$RESTORE_DIR/seek_filestore/." seek:/seek/filestore/
echo "    Done."

# ── Step 6: MinIO buckets ─────────────────────────────────────────────────────
echo "--- Restoring MinIO buckets..."
docker run --rm --network digitaltwins \\
    -v "\$RESTORE_DIR/minio":/minio_backup \\
    --entrypoint /bin/sh \\
    quay.io/minio/mc:latest \\
    -c "
        mc alias set dst http://minio:9000 '\$MINIO_ROOT_USER' '\$MINIO_ROOT_PASSWORD' &&
        for bucket in measurements models workflows processes tools; do
            echo \"  Mirroring bucket: \\\$bucket\" &&
            mc mirror /minio_backup/\\\$bucket dst/\\\$bucket || true
        done
    "
echo "    Done."

# ── Step 7: Airflow DAGs ─────────────────────────────────────────────────────
echo "--- Restoring Airflow DAGs..."
tar xf "\$RESTORE_DIR/dags.tar" -C "\$BASE_DIR/services/airflow"
echo "    Done."

# ── Step 8: Restart SEEK to rebuild Solr index ────────────────────────────────
echo "--- Restarting SEEK to rebuild Solr search index..."
docker compose restart seek workers
echo "    Done."

echo "=== Restore complete ==="
EOF

chmod +x restore.sh

echo "    Done: restore.sh"
echo "=== Backup complete: $BACKUP_DIR ==="
