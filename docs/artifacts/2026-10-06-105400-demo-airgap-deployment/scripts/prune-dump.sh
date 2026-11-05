#!/usr/bin/env bash
# prune-dump.sh — prune a COPY of the 2026-10-06 stage-dump down to the demo scope:
# Test Programme (7) / Test Project (12) and the data for assays 41/42/43.
#
# Usage: ./prune-dump.sh /path/to/dtwins-migrate
#
# Run against the migrate COPY only — it refuses to touch the pristine backup dir.
# DB-level pruning (SEEK tree, digitaltwins rows) happens on the TARGET after
# portal-restore.sh; this script only trims what portal-restore would copy.
set -euo pipefail

MIGRATE_DIR="${1:?usage: prune-dump.sh <migrate-dir>}"
MIGRATE_DIR="$(readlink -f "$MIGRATE_DIR")"
PRISTINE="/home/clin864/Projects/archive/digitaltwins-platform/20261006"

[ "$MIGRATE_DIR" = "$PRISTINE" ] && { echo "REFUSING to prune the pristine backup $PRISTINE"; exit 1; }
[ -f "$MIGRATE_DIR/digitaltwins.sql" ] || { echo "$MIGRATE_DIR does not look like a stage-dump dir"; exit 1; }

cd "$MIGRATE_DIR"

echo "== old config/secrets must not travel =="
rm -fv .env env secrets.env keycloak.sql hapi.sql   # HAPI FHIR: dropped (not used by the demo assays)
rm -rfv config-backup

echo "== Orthanc PACS data: out of scope =="
rm -fv digitaltwins-platform_orthanc_1_data.tar digitaltwins-platform_orthanc_2_data.tar

echo "== MinIO prune =="
# measurements: keep test_dicom, test_curated_dataset, test_converted
rm -rfv "minio/measurements/199eeb0e-a7fe-11f1-afdc-ee55ba67a387" \
        "minio/measurements/a8221374-bb7c-11f1-85de-2e4916f17eff" \
        "minio/measurements/clinical report.xlsx"
# models: none requested
rm -rfv minio/models
# workflows: keep 752540e2 (image_conversion/89), 1a6c77d6 (mri_curation/97),
# 7434f526 (volview/95) + the three wizard-build dirs
rm -rfv "minio/workflows/276ddb38-a0ff-11f1-af44-c25fd839e7a1" \
        "minio/workflows/270752f8-c055-11f1-a456-0abece750f00"
# tools (all 4 kept) and tool-builds (volview bundle) stay as-is
# airflow-workspace: scratch — empty it but keep the bucket dir so it's recreated
if [ -d minio/airflow-workspace ]; then
  find minio/airflow-workspace -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  echo "emptied minio/airflow-workspace"
fi

echo "== scrub the old MinIO secret from ingested DAG/tool code copies =="
# workflow/tool datasets carry copies of the DAG code with the source box's MinIO
# secret as a hardcoded os.environ.get fallback. Read the value from the source
# secrets file (never echoed) and make the lookup fail-loud instead.
OLD_SECRETS="${OLD_SECRETS:-/home/clin864/Projects/digitaltwins-platform/secrets.env}"
OLD_MINIO="$(grep -oP '^MINIO_ROOT_PASSWORD=\K.+' "$OLD_SECRETS" | tr -d '"')"
[ -n "$OLD_MINIO" ] || { echo "cannot read old MinIO secret from $OLD_SECRETS"; exit 1; }
{ grep -rlaF -- "$OLD_MINIO" minio || true; } | while IFS= read -r f; do
  OLD_MINIO="$OLD_MINIO" perl -0pi -e 's/os\.environ\.get\(\s*"MINIO_SECRET_KEY"\s*,\s*"\Q$ENV{OLD_MINIO}\E"\s*\)/os.environ["MINIO_SECRET_KEY"]/g' "$f"
  echo "scrubbed $f"
done
if grep -rqaF -- "$OLD_MINIO" minio; then echo "old MinIO secret still present under minio/"; exit 1; fi

echo "== plugin registry: keep plugins, drop out-of-scope measurement rows =="
# (VACUUM so deleted rows don't survive in SQLite free pages)
if [ -f plugin_registry.db ]; then
python3 - plugin_registry.db <<'PY2'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
for t in ("measurement_annotations", "measurements"):
    print(f"  {t}: {c.execute(f'DELETE FROM {t}').rowcount} row(s) deleted")
c.commit(); c.execute("VACUUM"); c.close()
PY2
fi

echo "== Jupyter volume: keep only assay_41 in admin1's volume =="
JTAR="jupyter_user_vols/digitaltwins-platform_jupyterhub_user_admin1.tar"
# (grep -c, not grep -q: under pipefail, -q's early exit SIGPIPEs the producer
#  and silently skips the repack)
NPRUNE=0
[ -f "$JTAR" ] && NPRUNE="$(tar -tf "$JTAR" | grep -c '^\./\(assay_31\|assay_32\|assay_37\|assay_40\|PACS\)/' || true)"
if [ "${NPRUNE:-0}" -gt 0 ]; then
  # extract/repack as root (alpine) so jovyan uid/gid + root-dir mode survive.
  # (tar --delete corrupts this archive — do not use it.)
  docker run --rm -v "$MIGRATE_DIR/jupyter_user_vols":/backup alpine sh -ec '
    mkdir /v
    tar -C /v -xf /backup/digitaltwins-platform_jupyterhub_user_admin1.tar
    cd /v
    for d in assay_31 assay_32 assay_37 assay_40 PACS; do rm -rf "$d"; done
    tar -C /v -cf /backup/digitaltwins-platform_jupyterhub_user_admin1.tar .
  '
  echo "repacked $JTAR:"
  tar -tf "$JTAR" | sed 's|^\./||' | cut -d/ -f1 | sort -u
else
  echo "jupyter tar already pruned or missing — skipped"
fi

echo
echo "== Result =="
du -sh "$MIGRATE_DIR"
echo "-- expected to remain: digitaltwins.sql seek_mysql.sql seek_filestore/"
echo "-- plugin_registry.db nginx_plugin_configs.tar minio/ jupyter_user_vols/"
ls -la "$MIGRATE_DIR"
echo "-- minio keep-set:"
find minio -mindepth 2 -maxdepth 2 -type d | sort
