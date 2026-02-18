#!/usr/bin/env bash
set -euo pipefail

STORAGE_ROOT="/var/lib/rancher/k3s/storage"
BACKUP_DIR="/home/ubuntu/data-backup/k3s-pvc"
LOG_FILE="${BACKUP_DIR}/restore.log"
DRY_RUN=0
ONLY_COMPONENT="all"     # loki | grafana | minio-mimir-blocks | all
SPECIFIC_FILE=""

# component -> namespace
NS_LOKI="loki"
NS_GRAFANA="grafana"
NS_MIMIR="mimir"

log() { echo "[$(date -Is)] $*" | tee -a "$LOG_FILE"; }

usage() {
  cat <<'EOF'
Usage:
  restore_k3s_storage_targets.sh [options]

Options:
  --component <loki|grafana|minio-mimir-blocks|all>   Restore latest for one component (default: all)
  --file <path-to-tar.gz>                             Restore a specific archive (component inferred from filename)
  --dry-run                                           Show actions only
  -h, --help                                          Show help

Examples:
  sudo restore_k3s_storage_targets.sh
  sudo restore_k3s_storage_targets.sh --component grafana
  sudo restore_k3s_storage_targets.sh --file /home/ubuntu/data-backup/k3s-pvc/pvc-loki-20260218085011.tar.gz
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --component) ONLY_COMPONENT="${2:-}"; shift 2;;
    --file) SPECIFIC_FILE="${2:-}"; shift 2;;
    --dry-run) DRY_RUN=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1"; usage; exit 1;;
  esac
done

mkdir -p "$BACKUP_DIR"

command -v kubectl >/dev/null 2>&1 || { log "ERROR: kubectl not found"; exit 1; }

latest_backup_for_prefix() {
  local prefix="$1"
  ls -1t "${BACKUP_DIR}/${prefix}-"*.tar.gz 2>/dev/null | head -n 1 || true
}

pick_target_dir_first_match() {
  local pattern="$1"
  find "$STORAGE_ROOT" -mindepth 1 -maxdepth 1 -type d -name "$pattern" -print -quit 2>/dev/null || true
}

infer_component_from_filename() {
  local f
  f="$(basename "$1")"
  case "$f" in
    pvc-loki-*.tar.gz) echo "loki" ;;
    pvc-grafana-*.tar.gz) echo "grafana" ;;
    minio-mimir-blocks-*.tar.gz) echo "minio-mimir-blocks" ;;
    *)
      log "ERROR: Cannot infer component from filename: $f"
      exit 1
      ;;
  esac
}

component_namespace() {
  case "$1" in
    loki) echo "$NS_LOKI" ;;
    grafana) echo "$NS_GRAFANA" ;;
    minio-mimir-blocks) echo "$NS_MIMIR" ;;
    *) echo "" ;;
  esac
}

# Save/restore replicas (deploy + sts) in a namespace
save_replicas() {
  local ns="$1"
  local outfile="$2"

  if [[ $DRY_RUN -eq 1 ]]; then
    log "[DRY-RUN] Would save replicas in ns=$ns to $outfile"
    return 0
  fi

  {
    echo "# kind name replicas"
    kubectl -n "$ns" get deploy -o jsonpath='{range .items[*]}deploy {.metadata.name} {.spec.replicas}{"\n"}{end}' 2>/dev/null || true
    kubectl -n "$ns" get sts   -o jsonpath='{range .items[*]}sts {.metadata.name} {.spec.replicas}{"\n"}{end}' 2>/dev/null || true
  } > "$outfile"
}

scale_all_to() {
  local ns="$1"
  local replicas="$2"

  log "Scaling namespace '$ns' deployments/statefulsets to $replicas"
  if [[ $DRY_RUN -eq 1 ]]; then
    log "[DRY-RUN] Would run: kubectl -n $ns scale deploy --all --replicas=$replicas"
    log "[DRY-RUN] Would run: kubectl -n $ns scale sts --all --replicas=$replicas"
    return 0
  fi

  kubectl -n "$ns" scale deploy --all --replicas="$replicas" 2>/dev/null || true
  kubectl -n "$ns" scale sts   --all --replicas="$replicas" 2>/dev/null || true
}

restore_saved_replicas() {
  local ns="$1"
  local infile="$2"

  log "Restoring previous replicas in namespace '$ns' from $infile"
  if [[ $DRY_RUN -eq 1 ]]; then
    log "[DRY-RUN] Would restore replicas from $infile"
    return 0
  fi

  [[ -f "$infile" ]] || { log "WARN: replica file missing: $infile"; return 0; }

  while read -r kind name reps; do
    [[ -z "${kind:-}" ]] && continue
    [[ "$kind" == "#" ]] && continue
    [[ -z "${name:-}" ]] && continue
    [[ -z "${reps:-}" ]] && reps=1

    case "$kind" in
      deploy) kubectl -n "$ns" scale deploy "$name" --replicas="$reps" 2>/dev/null || true ;;
      sts)    kubectl -n "$ns" scale sts   "$name" --replicas="$reps" 2>/dev/null || true ;;
    esac
  done < "$infile"
}

wait_rollout() {
  local ns="$1"
  log "Waiting for rollout in namespace '$ns' (best effort)"
  if [[ $DRY_RUN -eq 1 ]]; then
    log "[DRY-RUN] Would wait for deploy/sts rollout in ns=$ns"
    return 0
  fi
  kubectl -n "$ns" rollout status deploy --all --timeout=5m 2>/dev/null || true
  kubectl -n "$ns" rollout status sts   --all --timeout=5m 2>/dev/null || true
}

extract_tar_into_dir() {
  local tarfile="$1"
  local target="$2"

  [[ -f "$tarfile" ]] || { log "ERROR: backup file not found: $tarfile"; exit 1; }
  [[ -d "$target" ]] || { log "ERROR: target dir not found: $target"; exit 1; }

  log "Restoring: $tarfile -> $target"

  if [[ $DRY_RUN -eq 1 ]]; then
    log "[DRY-RUN] Would wipe: $target/* and extract archive into it"
    return 0
  fi

  case "$target" in
    "$STORAGE_ROOT"/*) ;;
    *) log "ERROR: refusing to restore outside $STORAGE_ROOT: $target"; exit 1;;
  esac

  # wipe existing
  rm -rf "${target:?}/"* "${target:?}/".* 2>/dev/null || true

  # extract
  tar -xzf "$tarfile" -C "$target"
}

restore_component() {
  local comp="$1"
  local tarfile="$2"
  local ns
  ns="$(component_namespace "$comp")"
  [[ -n "$ns" ]] || { log "ERROR: no namespace mapping for $comp"; exit 1; }

  local replica_file="${BACKUP_DIR}/.replicas-${comp}.txt"

  # Resolve target folder
  local target=""
  case "$comp" in
    loki)
      target="$(pick_target_dir_first_match '*loki*')"
      ;;
    grafana)
      target="$(pick_target_dir_first_match '*grafana*')"
      ;;
    minio-mimir-blocks)
      local minio_dir
      minio_dir="$(pick_target_dir_first_match '*mimir-minio*')"
      [[ -n "$minio_dir" ]] || { log "ERROR: no *mimir-minio* dir under $STORAGE_ROOT"; exit 1; }
      target="${minio_dir}/mimir-blocks"
      mkdir -p "$target"
      ;;
  esac

  [[ -n "$target" ]] || { log "ERROR: target directory not found for $comp"; exit 1; }

  log "---- Component: $comp (ns=$ns) ----"
  log "Target dir: $target"

  # scale down safely
  save_replicas "$ns" "$replica_file"
  scale_all_to "$ns" 0

  # restore files
  extract_tar_into_dir "$tarfile" "$target"

  # scale back up
  restore_saved_replicas "$ns" "$replica_file"
  wait_rollout "$ns"

  log "---- Done: $comp ----"
}

log "=== Restore start ==="
log "Storage root: $STORAGE_ROOT"
log "Backup dir:   $BACKUP_DIR"

if [[ -n "$SPECIFIC_FILE" ]]; then
  comp="$(infer_component_from_filename "$SPECIFIC_FILE")"
  restore_component "$comp" "$SPECIFIC_FILE"
  log "=== Restore finished ==="
  exit 0
fi

case "$ONLY_COMPONENT" in
  all)
    loki_bak="$(latest_backup_for_prefix 'pvc-loki')"
    grafana_bak="$(latest_backup_for_prefix 'pvc-grafana')"
    minio_bak="$(latest_backup_for_prefix 'minio-mimir-blocks')"

    [[ -n "$loki_bak" ]] && restore_component "loki" "$loki_bak" || log "No loki backups found."
    [[ -n "$grafana_bak" ]] && restore_component "grafana" "$grafana_bak" || log "No grafana backups found."
    [[ -n "$minio_bak" ]] && restore_component "minio-mimir-blocks" "$minio_bak" || log "No minio-mimir-blocks backups found."
    ;;
  loki)
    bak="$(latest_backup_for_prefix 'pvc-loki')"; [[ -n "$bak" ]] || { log "ERROR: No loki backups"; exit 1; }
    restore_component "loki" "$bak"
    ;;
  grafana)
    bak="$(latest_backup_for_prefix 'pvc-grafana')"; [[ -n "$bak" ]] || { log "ERROR: No grafana backups"; exit 1; }
    restore_component "grafana" "$bak"
    ;;
  minio-mimir-blocks)
    bak="$(latest_backup_for_prefix 'minio-mimir-blocks')"; [[ -n "$bak" ]] || { log "ERROR: No minio-mimir-blocks backups"; exit 1; }
    restore_component "minio-mimir-blocks" "$bak"
    ;;
  *)
    log "ERROR: invalid --component value: $ONLY_COMPONENT"
    usage
    exit 1
    ;;
esac

log "=== Restore finished ==="
