#!/usr/bin/env bash
set -euo pipefail

# --- Config ---
STORAGE_ROOT="/var/lib/rancher/k3s/storage"
BACKUP_DIR="/home/ubuntu/data-backup/k3s-pvc"
KEEP_LATEST=2
TS="$(date +%Y%m%d%H%M%S)"

mkdir -p "$BACKUP_DIR"
LOG_FILE="${BACKUP_DIR}/backup.log"

log() { echo "[$(date -Is)] $*" | tee -a "$LOG_FILE"; }

backup_tar() {
  local src="$1"
  local prefix="$2"
  local out="${BACKUP_DIR}/${prefix}-${TS}.tar.gz"

  if [[ ! -d "$src" ]]; then
    log "SKIP: missing dir: $src"
    return
  fi

  log "Backup: ${src} -> ${out}"
  tar -C "$src" -czf "$out" .

  # keep latest 3
  ls -1t "${BACKUP_DIR}/${prefix}-"*.tar.gz 2>/dev/null \
      | tail -n +"$((KEEP_LATEST+1))" \
      | xargs -r rm -f
}

log "=== Backup start ${TS} ==="

# loki pvc
loki_dir=$(find "$STORAGE_ROOT" -mindepth 1 -maxdepth 1 -type d -name '*loki*' -print -quit || true)
[[ -n "$loki_dir" ]] && backup_tar "$loki_dir" "pvc-loki"

# grafana pvc
grafana_dir=$(find "$STORAGE_ROOT" -mindepth 1 -maxdepth 1 -type d -name '*grafana*' -print -quit || true)
[[ -n "$grafana_dir" ]] && backup_tar "$grafana_dir" "pvc-grafana"

# mimir-blocks inside mimir-minio pvc
minio_dir=$(find "$STORAGE_ROOT" -mindepth 1 -maxdepth 1 -type d -name '*mimir-minio*' -print -quit || true)
if [[ -n "$minio_dir" ]]; then
    backup_tar "${minio_dir}/mimir-blocks" "minio-mimir-blocks"
fi

log "=== Backup finished ==="
