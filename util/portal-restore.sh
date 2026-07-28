#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# portal-restore.sh — restore a stage-dump into THIS (target) instance.
#
# Run this ON THE TARGET box, pointing at the directory produced by
# stage-dump.sh (copied over). It is DESTRUCTIVE: it overwrites the target's
# digitaltwins DB, HAPI DB, SEEK database + filestore, MinIO buckets, plugin
# registry, and Orthanc DICOM with the source's. It requires confirmation.
#
# Credentials come from the target containers' own env, so the source and
# target need not share passwords.
#
#   util/portal-restore.sh [IN_DIR]        (default /tmp/dtwins-migrate)
#
# NOTE (SEEK API token): restoring SEEK's database replaces the target's SEEK
# users, so the SEEK_API_TOKEN the buildout minted is no longer valid. After
# this runs, re-mint it and refresh .env (see the printed reminder at the end).
# ---------------------------------------------------------------------------
set -euo pipefail

IN="${1:-/tmp/dtwins-migrate}"
PROJECT="${PROJECT:-digitaltwins-platform}"
NETWORK="${NETWORK:-$PROJECT}"
BASE_DIR="${BASE_DIR:-$HOME/digitaltwins-platform}"
DB_C="${DB_C:-${PROJECT}-database-1}"
SEEKDB_C="${SEEKDB_C:-${PROJECT}-db-1}"
SEEK_C="${SEEK_C:-${PROJECT}-seek-1}"
PORTAL_BE_C="${PORTAL_BE_C:-${PROJECT}-portal-backend-1}"
MINIO_C="${MINIO_C:-${PROJECT}-minio-1}"
# volume=container pairs to stop while their DICOM volume is replaced
ORTHANC_MAP="${ORTHANC_MAP:-${PROJECT}_orthanc_1_data=${PROJECT}-orthanc-1-1 ${PROJECT}_orthanc_2_data=${PROJECT}-orthanc-2-1}"
MC_IMAGE="${MC_IMAGE:-quay.io/minio/mc:latest}"

[ -d "$IN" ] || { echo "portal-restore: no input dir $IN" >&2; exit 1; }
echo "portal-restore: $IN -> project '$PROJECT' on $(hostname)"
echo "This OVERWRITES digitaltwins, hapi, seek, minio, plugin-registry and orthanc on THIS host."
printf "Type 'yes' to proceed: "; read -r ans; [ "$ans" = "yes" ] || { echo "aborted."; exit 1; }

cd "$BASE_DIR"

# 1. digitaltwins DB ----------------------------------------------------------
if [ -f "$IN/digitaltwins.sql" ]; then
  echo "== restore digitaltwins DB =="
  docker exec -i "$DB_C" sh -c 'psql -U "$POSTGRES_USER" "${POSTGRES_DB:-digitaltwins}"' < "$IN/digitaltwins.sql"
fi

# 2. HAPI DB (source pg -> shared pg here; --clean dump handles the drop) ------
if [ -f "$IN/hapi.sql" ]; then
  echo "== restore hapi DB =="
  docker exec -i "$DB_C" sh -c 'psql -U "$POSTGRES_USER" hapi' < "$IN/hapi.sql"
fi

# 3. SEEK MySQL + filestore ---------------------------------------------------
if [ -f "$IN/seek_mysql.sql" ]; then
  echo "== restore seek mysql =="
  docker exec "$SEEKDB_C" sh -c \
    'exec mysql -u root -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS seek; CREATE DATABASE seek CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"'
  docker exec -i "$SEEKDB_C" sh -c 'exec mysql -u root -p"$MYSQL_ROOT_PASSWORD" seek' < "$IN/seek_mysql.sql"
fi
if [ -d "$IN/seek_filestore" ]; then
  echo "== restore seek filestore =="
  docker cp "$IN/seek_filestore/." "$SEEK_C:/seek/filestore/"
fi

# 4. MinIO buckets ------------------------------------------------------------
# Enumerate bucket dirs on the HOST (the minio/mc image has no ls/awk), then run
# mc per bucket in the container.
if [ -d "$IN/minio" ]; then
  echo "== restore minio =="
  MINIO_USER=$(docker exec "$MINIO_C" printenv MINIO_ROOT_USER)
  MINIO_PASS=$(docker exec "$MINIO_C" printenv MINIO_ROOT_PASSWORD)
  for b in $(cd "$IN/minio" && ls -1); do
    echo "  $b"
    docker run --rm --network "$NETWORK" -v "$IN/minio":/backup \
      -e A="$MINIO_USER" -e B="$MINIO_PASS" --entrypoint /bin/sh "$MC_IMAGE" \
      -c "mc alias set dst http://minio:9000 \"\$A\" \"\$B\" >/dev/null && mc mb --ignore-existing dst/$b >/dev/null && mc mirror /backup/$b dst/$b" || true
  done
fi

# 5. Portal plugin registry ---------------------------------------------------
if [ -f "$IN/plugin_registry.db" ]; then
  echo "== restore plugin registry (restarts portal-backend) =="
  docker cp "$IN/plugin_registry.db" "$PORTAL_BE_C:/data/plugin_registry.db"
  docker restart "$PORTAL_BE_C" >/dev/null
fi

# 6. Orthanc DICOM (stop container, replace volume, start) --------------------
for map in $ORTHANC_MAP; do
  vol="${map%%=*}"; cont="${map##*=}"; tar="$IN/${vol}.tar"
  [ -f "$tar" ] || { echo "  no $tar; skip"; continue; }
  echo "== restore orthanc $vol (stopping $cont) =="
  docker stop "$cont" >/dev/null
  docker run --rm -v "$vol":/v -v "$IN":/backup alpine sh -c "rm -rf /v/* /v/.[!.]* 2>/dev/null; tar -C /v -xf /backup/${vol}.tar"
  docker start "$cont" >/dev/null
done

# 7. Restart SEEK so Solr rebuilds its index from the restored DB -------------
echo "== restart seek/workers (Solr reindex) =="
docker compose restart seek workers >/dev/null 2>&1 || docker restart "$SEEK_C" >/dev/null

cat <<'EOF'

portal-restore: done.

!! ACTION REQUIRED — SEEK API token
   The restored SEEK database replaced this host's SEEK users, so the
   SEEK_API_TOKEN in .env is stale and digitaltwins-api can no longer talk to
   SEEK. Once SEEK is back up, re-mint and refresh .env, e.g.:

     cd ~/digitaltwins-platform
     SECRETS_FILE=/mnt/install_src/data/secrets.env util/generate-token.sh admin
     util/gen-env.sh -e /mnt/install_src/data/env -s /mnt/install_src/data/secrets.env
     docker compose up -d digitaltwins-api

   (Or copy the source's SEEK_API_TOKEN into secrets.env before re-rendering.)
EOF
