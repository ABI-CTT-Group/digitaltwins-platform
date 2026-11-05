#!/usr/bin/env bash
# build-pruned-seek.sh — prune SEEK LOCALLY so only demo-scope data ever reaches
# the drive. Loads the pristine backup's seek_mysql.sql + seek_filestore into a
# throwaway MySQL + SEEK (ldh) sandbox, runs seek-prune.rb, rebuilds SEEK's auth
# lookup tables, then writes:
#   <migrate-dir>/seek_mysql.sql   — pruned dump (same mysqldump form as stage-dump.sh)
#   <migrate-dir>/seek_filestore/  — ONLY files referenced by the pruned DB.
#     Never copied: secret_key_base, attr_encrypted/ (local secrets — the target
#     SEEK keeps its own), tmp/ (bioschemas dumps of ALL local people/projects),
#     rdf/ (per-item cache, regenerated on demand).
# Sandbox containers/network/volume are removed on exit.
#
# Usage: build-pruned-seek.sh <pristine-backup-dir> <migrate-dir> <work-dir>
set -euo pipefail

SRC="$(readlink -f "${1:?pristine backup dir}")"
DST="$(readlink -f "${2:?migrate dir}")"
WORK="${3:?work dir}"; mkdir -p "$WORK"; WORK="$(readlink -f "$WORK")"
HERE="$(cd "$(dirname "$0")" && pwd)"

LDH_IMAGE="${LDH_IMAGE:-ghcr.io/nfdi4health/ldh:v0.3.2}"
KEEP_PROGRAMME="${KEEP_PROGRAMME:-7}"
KEEP_PROJECT="${KEEP_PROJECT:-12}"
ADMIN_SUB="${ADMIN_SUB:-1afb2774-0277-494f-a976-34a72683d972}"
STALE_SOP_IDS="${STALE_SOP_IDS:-38}"

NET=seek-prune-net DB=seek-prune-db FSVOL=seek-prune-filestore
PW="$(openssl rand -hex 16)"
cleanup() { docker rm -f "$DB" >/dev/null 2>&1 || true
            docker volume rm "$FSVOL" >/dev/null 2>&1 || true
            docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT
cleanup

[ -f "$SRC/seek_mysql.sql" ] && [ -d "$SRC/seek_filestore" ] || { echo "no SEEK dump in $SRC"; exit 1; }

echo "== sandbox MySQL =="
docker network create "$NET" >/dev/null
docker run -d --name "$DB" --network "$NET" --network-alias db \
  -e MYSQL_ROOT_PASSWORD="$PW" -e MYSQL_DATABASE=seek -e MYSQL_USER=seek -e MYSQL_PASSWORD="$PW" \
  mysql:8.0 --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci >/dev/null
until docker exec "$DB" mysql -uroot -p"$PW" -e 'select 1' seek >/dev/null 2>&1; do sleep 2; done
docker exec -i "$DB" mysql -uroot -p"$PW" seek < "$SRC/seek_mysql.sql" 2>/dev/null
echo "loaded $(docker exec "$DB" mysql -N -uroot -p"$PW" seek -e 'select count(*) from people' 2>/dev/null) people"

echo "== sandbox filestore (copy of the backup, owned by www-data) =="
docker volume create "$FSVOL" >/dev/null
docker run --rm -v "$SRC/seek_filestore":/src:ro -v "$FSVOL":/fs alpine \
  sh -c 'cp -a /src/. /fs/ && chown -R 33:33 /fs'

rm -rf "$WORK/out"; mkdir -p "$WORK/out"
seek() {  # run a command in a one-shot ldh container wired to the sandbox
  docker run --rm -i --network "$NET" \
    -e RAILS_ENV=production -e MYSQL_HOST=db -e MYSQL_DATABASE=seek -e MYSQL_USER=seek -e MYSQL_PASSWORD="$PW" \
    -e SOLR_HOST=127.0.0.1 -e SOLR_PORT=1 \
    -e KEEP_PROGRAMME="$KEEP_PROGRAMME" -e KEEP_PROJECT="$KEEP_PROJECT" \
    -e ADMIN_SUB="$ADMIN_SUB" -e STALE_SOP_IDS="$STALE_SOP_IDS" \
    -v "$FSVOL":/seek/filestore -v "$WORK/out":/out -v "$HERE/seek-prune.rb":/prune.rb:ro \
    --user root --entrypoint bash "$LDH_IMAGE" \
    -c "cd /seek && cp docker/database.docker.mysql.yml config/database.yml && $1"
  # (the image's default database.yml is sqlite; its entrypoint swaps in the
  #  mysql one — we bypass the entrypoint, so do the swap ourselves)
}

echo "== prune =="
seek 'bundle exec rails runner /prune.rb' 2>&1 | grep -v -i 'warn\|deprecat' | tee "$WORK/prune.log" | tail -12
echo "== rebuild auth lookup tables =="
seek 'bundle exec rake seek:repopulate_auth_lookup_tables_sync' 2>&1 | tail -2
# the rake may enqueue jobs; nothing should travel in delayed_jobs
docker exec "$DB" mysql -uroot -p"$PW" seek -e 'DELETE FROM delayed_jobs' 2>/dev/null

echo "== write pruned dump + filestore =="
docker exec "$DB" sh -c 'exec mysqldump -u root -p"$MYSQL_ROOT_PASSWORD" seek' 2>/dev/null > "$DST/seek_mysql.sql.new"
grep -q '^INSERT INTO `people`' "$DST/seek_mysql.sql.new" || { echo "pruned dump looks empty"; exit 1; }
mv "$DST/seek_mysql.sql.new" "$DST/seek_mysql.sql"
rm -rf "$DST/seek_filestore"; mkdir -p "$DST/seek_filestore"
docker run --rm -v "$FSVOL":/fs:ro -v "$DST/seek_filestore":/dst -v "$WORK/out":/out:ro alpine sh -ec '
  cd /fs
  while IFS= read -r p; do
    [ -n "$p" ] || continue
    mkdir -p "/dst/$(dirname "$p")" && cp -a "$p" "/dst/$p"
  done < /out/keep-files.txt
  # empty skeleton dirs SEEK expects (contents regenerated on the target)
  for d in assets converted-assets git avatars model_images rdf tmp; do mkdir -p "/dst/$d"; done
  chown -R '"$(id -u):$(id -g)"' /dst'
cp "$WORK/out/forbidden.txt" "$WORK/forbidden-seek.txt"
echo "filestore: $(find "$DST/seek_filestore" -type f | wc -l) files, $(du -sh "$DST/seek_filestore" | cut -f1)"
echo "forbidden strings for leak scan: $WORK/forbidden-seek.txt ($(wc -l < "$WORK/forbidden-seek.txt"))"
