#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# portal-restore.sh — restore a stage-dump into THIS (target) instance.
#
# Run this ON THE TARGET box, pointing at the directory produced by
# stage-dump.sh (copied over). It is DESTRUCTIVE: it overwrites the target's
# digitaltwins DB, HAPI DB, SEEK database + filestore, MinIO buckets, plugin
# registry, gateway plugin route configs, JupyterHub per-user volumes, and
# Orthanc DICOM with the source's. It requires confirmation.
#
# Credentials come from the target containers' own env, so the source and
# target need not share passwords.
#
# After the data is restored it RE-STAMPS the SEEK config the restore clobbers
# (step 10): site_base_host + feature flags (enable-features.sh, read from THIS
# host's rendered .env) and SEEK server-admin access for the platform admin
# (promote-seek-admin.sh, by Keycloak sub) — so you don't have to remember to
# re-run them by hand.
#
#   util/portal-restore.sh [IN_DIR]        (default /tmp/dtwins-migrate)
#
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
MC_IMAGE="${MC_IMAGE:-minio/mc:RELEASE.2024-05-09T17-04-24Z}"
PLUGIN_CONF_VOL="${PLUGIN_CONF_VOL:-${PROJECT}_nginx_plugin_configs}"
GATEWAY_C="${GATEWAY_C:-${PROJECT}-gateway}"

[ -d "$IN" ] || { echo "portal-restore: no input dir $IN" >&2; exit 1; }
IN="$(cd "$IN" && pwd)"   # absolutise: the later `cd "$BASE_DIR"` must not strand a relative $IN
echo "portal-restore: $IN -> project '$PROJECT' on $(hostname)"
echo "This OVERWRITES digitaltwins, hapi, seek, minio, plugin-registry, plugin nginx configs, jupyterhub user volumes and orthanc on THIS host."
printf "Type 'yes' to proceed: "; read -r ans; [ "$ans" = "yes" ] || { echo "aborted."; exit 1; }

cd "$BASE_DIR"

# A present-but-empty .sql is the silent trap: `psql < empty.sql` succeeds doing
# nothing, so the restore "passes" while the data never lands. Refuse to restore
# a dump that has no schema/data — better to fail here than to look successful and
# quietly leave the target unchanged. (A genuinely absent file is still skipped by
# the `if [ -f ]` guards below; this only fires when the file exists but is empty.)
assert_sql_has_data() {  # $1=file  $2=label
  [ -s "$1" ] || { echo "FATAL: $2 dump '$1' is empty — refusing to 'restore' nothing. Re-dump on the source." >&2; exit 1; }
  grep -qiE 'CREATE TABLE|INSERT INTO|^COPY ' "$1" || {
    echo "FATAL: $2 dump '$1' has no schema/data (no CREATE TABLE/COPY/INSERT) — the source dump was empty or wrong." >&2
    exit 1
  }
}

# 1. digitaltwins DB ----------------------------------------------------------
if [ -f "$IN/digitaltwins.sql" ]; then
  echo "== restore digitaltwins DB =="
  assert_sql_has_data "$IN/digitaltwins.sql" "digitaltwins"
  docker exec -i "$DB_C" sh -c 'psql -U "$POSTGRES_USER" "${POSTGRES_DB:-digitaltwins}"' < "$IN/digitaltwins.sql"
fi

# 2. HAPI DB (source pg -> shared pg here; --clean dump handles the drop) ------
if [ -f "$IN/hapi.sql" ]; then
  echo "== restore hapi DB =="
  assert_sql_has_data "$IN/hapi.sql" "hapi"
  docker exec -i "$DB_C" sh -c 'psql -U "$POSTGRES_USER" hapi' < "$IN/hapi.sql"
fi

# 3. SEEK MySQL + filestore ---------------------------------------------------
if [ -f "$IN/seek_mysql.sql" ]; then
  echo "== restore seek mysql =="
  assert_sql_has_data "$IN/seek_mysql.sql" "seek mysql"
  docker exec "$SEEKDB_C" sh -c \
    'unset MYSQL_HOST; exec mysql -u root -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS seek; CREATE DATABASE seek CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"'
  docker exec -i "$SEEKDB_C" sh -c 'unset MYSQL_HOST; exec mysql -u root -p"$MYSQL_ROOT_PASSWORD" seek' < "$IN/seek_mysql.sql"
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
      -c "mc alias set dst http://minio:9000 \"\$A\" \"\$B\" >/dev/null && mc mb --ignore-existing dst/$b >/dev/null && mc mirror --overwrite /backup/$b dst/$b" || true
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

# 7. Gateway plugin route configs (into nginx_plugin_configs volume) ----------
if [ -f "$IN/nginx_plugin_configs.tar" ]; then
  echo "== restore plugin nginx configs =="
  docker volume create "$PLUGIN_CONF_VOL" >/dev/null
  docker run --rm -v "$PLUGIN_CONF_VOL":/v -v "$IN":/backup alpine \
    tar -C /v -xf /backup/nginx_plugin_configs.tar
  # Reload the gateway so it picks up the restored plugin routes. A route whose
  # plugin upstream isn't present yet 502s on that route only (resolver/var
  # pattern), so this is safe even before the plugin image/container is added.
  docker exec "$GATEWAY_C" nginx -s reload >/dev/null 2>&1 || true
fi

# 8. JupyterHub per-user volumes ----------------------------------------------
if [ -d "$IN/jupyter_user_vols" ]; then
  echo "== restore jupyterhub user volumes =="
  for tar in "$IN"/jupyter_user_vols/*.tar; do
    [ -e "$tar" ] || continue
    v=$(basename "$tar" .tar)
    echo "  $v"
    docker volume create "$v" >/dev/null
    docker run --rm -v "$v":/v -v "$IN/jupyter_user_vols":/backup alpine \
      sh -c "rm -rf /v/* /v/.[!.]* 2>/dev/null; tar -C /v -xf /backup/${v}.tar"
  done
fi

# 9. Restart SEEK so Solr rebuilds its index from the restored DB -------------
echo "== restart seek/workers (Solr reindex) =="
docker compose restart seek workers >/dev/null 2>&1 || docker restart "$SEEK_C" >/dev/null

# 10. Re-stamp the SEEK config the restore clobbered --------------------------
# The SEEK MySQL restore (step 3) overwrote the `settings` and `users` tables with
# the SOURCE's, which reverts two TARGET-specific things:
#   - site_base_host  -> the source's (e.g. http://localhost:8001) — breaks every
#     "SEEK ID" URL on this host until reset;
#   - the feature flags (omniauth/programmes/workflows/GA4GH/git) -> the source's.
# enable-features.sh re-applies both, using PLATFORM_PROTOCOL/PLATFORM_DOMAIN from
# THIS host's rendered .env. The restore also replaces SEEK's whole user set, so
# whichever user was a server admin before is gone; promote-seek-admin.sh restores
# admin access by the platform admin's Keycloak `sub` (pinned in the realm
# template), NOT by guessing the SEEK login — SEEK derives that login itself
# (e.g. Keycloak "admin1" -> SEEK "admin1186") and it doesn't match any .env var.
# Non-fatal: a failure here warns and points at the manual fix rather than
# aborting the restore.
echo "== re-stamp SEEK site_base_host + features + admin =="
ENV_FILE="$BASE_DIR/.env"
if [ -f "$ENV_FILE" ]; then
  PROT=$(grep -E '^PLATFORM_PROTOCOL=' "$ENV_FILE" | cut -d= -f2-)
  DOM=$(grep  -E '^PLATFORM_DOMAIN='   "$ENV_FILE" | cut -d= -f2-)
  # SEEK was just restarted — wait until Rails answers before poking it.
  for _ in $(seq 1 30); do
    docker exec "$SEEK_C" sh -c 'cd /seek && RAILS_ENV=production bundle exec rails runner "exit 0"' >/dev/null 2>&1 && break
    sleep 5
  done
  if [ -n "$PROT" ] && [ -n "$DOM" ]; then
    SEEK_SITE_BASE_URL="$PROT://$DOM/seek" ./util/enable-features.sh \
      || echo "  WARN: enable-features failed — site_base_host/features NOT reset; run: SEEK_SITE_BASE_URL=$PROT://$DOM/seek ./util/enable-features.sh"
  else
    echo "  WARN: PLATFORM_PROTOCOL/DOMAIN missing from $ENV_FILE — site_base_host NOT reset"
  fi
else
  echo "  WARN: $ENV_FILE not found — cannot auto reset site_base_host/features. Run enable-features.sh (with SEEK_SITE_BASE_URL) manually."
fi
./util/promote-seek-admin.sh \
  || echo "  WARN: promote-seek-admin failed — the platform admin may not be a SEEK server admin; run: ./util/promote-seek-admin.sh"

cat <<'EOF'

portal-restore: done.


EOF
