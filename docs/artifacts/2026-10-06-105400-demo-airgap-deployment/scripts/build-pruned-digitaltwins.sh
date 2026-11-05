#!/usr/bin/env bash
# build-pruned-digitaltwins.sh — prune the platform DB LOCALLY: load the pristine
# digitaltwins.sql into a throwaway postgres:16, run prune-digitaltwins.sql, and
# re-dump in the same form stage-dump.sh produces (pg_dump --clean --if-exists),
# so portal-restore.sh consumes it unchanged.
#
# Usage: build-pruned-digitaltwins.sh <pristine-backup-dir> <migrate-dir>
set -euo pipefail
SRC="$(readlink -f "${1:?pristine backup dir}")"
DST="$(readlink -f "${2:?migrate dir}")"
HERE="$(cd "$(dirname "$0")" && pwd)"
C=dt-prune-pg
cleanup() { docker rm -f "$C" >/dev/null 2>&1 || true; }
trap cleanup EXIT; cleanup

docker run -d --name "$C" -e POSTGRES_USER=admin -e POSTGRES_PASSWORD="$(openssl rand -hex 16)" \
  -e POSTGRES_DB=digitaltwins postgres:16 >/dev/null
until docker exec "$C" pg_isready -U admin -d digitaltwins >/dev/null 2>&1; do sleep 1; done
sleep 2
docker exec "$C" psql -q -U admin -d digitaltwins -c 'CREATE ROLE portal LOGIN' >/dev/null
docker exec -i "$C" psql -q -U admin -d digitaltwins -v ON_ERROR_STOP=1 < "$SRC/digitaltwins.sql" >/dev/null
docker exec -i "$C" psql -U admin -d digitaltwins -v ON_ERROR_STOP=1 < "$HERE/prune-digitaltwins.sql"
# nothing local-only should ride along in session/log tables
docker exec "$C" psql -q -U admin -d digitaltwins -c 'DELETE FROM upload_session' >/dev/null
docker exec "$C" pg_dump -U admin --clean --if-exists digitaltwins > "$DST/digitaltwins.sql.new"
grep -q 'COPY public.dataset ' "$DST/digitaltwins.sql.new" || { echo "pruned dump looks empty"; exit 1; }
mv "$DST/digitaltwins.sql.new" "$DST/digitaltwins.sql"
echo "wrote $DST/digitaltwins.sql ($(du -h "$DST/digitaltwins.sql" | cut -f1))"
