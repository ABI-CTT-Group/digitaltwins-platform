#!/usr/bin/env bash
# demo-setup.sh — load the demo data into a freshly installed platform and make
# the three demo assays launchable. Run once, on the server, after the platform
# install (DEPLOYMENT.md step 2). Asks for confirmation before replacing data.
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"            # the drive (/mnt/install_src)
PLATFORM="${PLATFORM:-$HOME/digitaltwins-platform}"
cd "$PLATFORM"
set -a; . "$SRC/data/secrets.env"; . "$SRC/data/env"; set +a
URL="${PLATFORM_PROTOCOL:-http}://${PLATFORM_DOMAIN:-localhost}"

echo "== 1/4 load demo data =="
rm -rf /tmp/dtwins-migrate && cp -r "$SRC/dtwins-migrate" /tmp/dtwins-migrate
util/portal-restore.sh /tmp/dtwins-migrate

echo "== 2/4 SEEK: admin password + search index =="
util/set-seek-password.sh admin1186 "$PLATFORM_ADMIN_PASSWORD"   # admin1's SEEK login
docker compose exec -T seek bash -c 'cd /seek && RAILS_ENV=production bundle exec rake seek:reindex_all'

echo "== 3/4 Airflow DAG workflow_89 =="
cp -r "$SRC/dags-payload/." services/airflow/dags/
for i in $(seq 1 30); do
  docker compose exec -T airflow-scheduler airflow dags list 2>/dev/null | grep -q workflow_89 && break
  sleep 10
done
docker compose exec -T airflow-scheduler airflow dags unpause workflow_89
docker compose exec -T airflow-scheduler airflow dags list 2>/dev/null | grep workflow_89

echo "== 4/4 check =="
util/seek-user-report.sh
echo
echo "Done. Log in at $URL as admin1 and open:"
echo "  $URL/study-dashboard?trail=7,12,10,11"
