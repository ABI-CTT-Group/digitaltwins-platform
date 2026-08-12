#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# reset.sh — return a box to a clean baseline so the install can be re-run.
#
# The physical-box equivalent of dropping & recreating a VM, WITHOUT reimaging:
# tears down the platform, its data, and (optionally) the apt/pip and docker
# state, leaving the box at the point the install procedure starts from. The
# install bundle at /mnt/install_src is NEVER touched.
#
#   sudo util/reset.sh [--level platform|apt|bare] [--dry-run] [--yes]
#
# LEVELS (cumulative — each includes the ones above it):
#   platform  (default) stop+remove the stack & ALL its data volumes, remove the
#             systemd boot units, delete the runtime repo copy. Docker, apt and
#             the bundle stay → re-run the install from the deploy (step-3) stage.
#   apt       ALSO repair the apt/pip damage a bundle `dpkg -i *.deb` causes
#             (half-configured certbot, python3.12 version skew). NEEDS one-time
#             ONLINE access to re-align packages from the archive.
#   bare      ALSO prune all docker images/volumes, remove the docker engine,
#             reset ufw, and wipe /etc/letsencrypt — closest to a fresh VM.
#
# SAFETY: preview everything with --dry-run first; without --yes it requires you
# to type the hostname to confirm. It NEVER purges system Python (python3 /
# python3-minimal / python3.12-minimal — doing so bricks Ubuntu) and NEVER
# deletes /mnt/install_src.
#
# ⚠️ UNTESTED as shipped — run with --dry-run and read every line before the real
# thing. Run it from the BUNDLE copy (/mnt/install_src/clean_src/.../util), NOT
# from the runtime repo it is about to delete.
# ---------------------------------------------------------------------------
set -euo pipefail

# --- args --------------------------------------------------------------------
LEVEL=platform
DRY=0
ASSUME_YES=0
RUNTIME_DIR="${RUNTIME_DIR:-$HOME/digitaltwins-platform}"
COMPUTE_DIR="${COMPUTE_DIR:-$HOME/digitaltwins-compute}"
BUNDLE="${INSTALL_SRC_DIR:-/mnt/install_src}"

while [ $# -gt 0 ]; do
  case "$1" in
    --level)    LEVEL="${2:?--level needs platform|apt|bare}"; shift ;;
    --dry-run|-n) DRY=1 ;;
    --yes|-y)   ASSUME_YES=1 ;;
    --runtime)  RUNTIME_DIR="${2:?--runtime needs a path}"; shift ;;
    -h|--help)  sed -n '2,38p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done
case "$LEVEL" in platform|apt|bare) ;; *) echo "ERROR: --level must be platform|apt|bare" >&2; exit 2 ;; esac

# certbot + apt + systemctl + rm of system files need root.
if [ "$(id -u)" -ne 0 ]; then exec sudo -E bash "$0" --level "$LEVEL" $([ "$DRY" = 1 ] && echo --dry-run) $([ "$ASSUME_YES" = 1 ] && echo --yes) --runtime "$RUNTIME_DIR"; fi

# Don't delete the tree we're running from.
SCRIPT_DIR="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
case "$SCRIPT_DIR/" in
  "$RUNTIME_DIR"/*) echo "ERROR: reset.sh is inside the runtime dir it would delete ($RUNTIME_DIR)." >&2
                    echo "       Run it from the bundle copy: $BUNDLE/clean_src/digitaltwins-platform/util/reset.sh" >&2
                    exit 1 ;;
esac

echo "reset: host=$(hostname)  level=$LEVEL  runtime=$RUNTIME_DIR  bundle=$BUNDLE (preserved)"
[ "$DRY" = 1 ] && echo "reset: DRY RUN — nothing will be changed"

# --- confirmation ------------------------------------------------------------
if [ "$ASSUME_YES" = 0 ] && [ "$DRY" = 0 ]; then
  echo
  echo "This DESTROYS the platform and ALL its data (SEEK / Postgres / MinIO / Keycloak) on this box."
  printf "Type this host's name (%s) to proceed: " "$(hostname)"
  read -r ans
  [ "$ans" = "$(hostname)" ] || { echo "aborted."; exit 1; }
fi

# run CMD — print it; execute unless --dry-run. Best-effort (never aborts the reset).
run() { echo "  ${DRY:+[dry-run] }$1"; [ "$DRY" = 1 ] || eval "$1" || echo "    (non-fatal: previous step returned $?)"; }

compose_down() {  # $1 = dir, $2 = extra flags
  local d="$1" extra="$2"
  if [ -f "$d/docker-compose.yml" ] || [ -f "$d/compose.yaml" ] || [ -f "$d/compose.yml" ]; then
    run "cd '$d' && docker compose down --volumes --remove-orphans $extra"
  else
    echo "  (no compose file in $d — skipping stack teardown there)"
  fi
}

# Resolve a compose project's name from its runtime .env (COMPOSE_PROJECT_NAME),
# falling back to $2 when the dir/.env is already gone.
project_name() {  # $1 = runtime dir, $2 = fallback
  local envf="$1/.env" p=""
  [ -f "$envf" ] && p="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' "$envf" | tail -1)"
  echo "${p:-$2}"
}

# GUARANTEED teardown of a compose project, independent of COMPOSE_FILE.
# `docker compose down -v` silently misses volumes when COMPOSE_FILE isn't fully
# enumerated (e.g. run without the runtime .env), and the leftover *stopped*
# containers then make `docker system prune --volumes` skip their volumes — which
# is why DAG runs (Postgres) and logs (airflow-logs bucket in minio) survived a
# 'bare' reset. Remove the project's containers, named volumes and network by
# label / name-prefix so nothing can linger. Platform volumes are named
# ${PROJECT_NAME}_* and ${PROJECT_NAME} == COMPOSE_PROJECT_NAME by design.
force_project_teardown() {  # $1 = project name
  local p="$1"
  [ -n "$p" ] || return 0
  echo "  force teardown of compose project: $p"
  run "docker ps -aq --filter 'label=com.docker.compose.project=$p' | xargs -r docker rm -f"
  run "docker volume ls -q --filter 'label=com.docker.compose.project=$p' | xargs -r docker volume rm"
  # explicit name: \${PROJECT_NAME}_* volumes may not carry the project label
  run "docker volume ls -q | grep -E '^${p}_' | xargs -r docker volume rm"
  run "docker network rm '$p' 2>/dev/null"
}

# =============================================================================
# TIER 1 — platform stack + boot units + runtime copy
# =============================================================================
echo; echo "== Tier 1: platform stack, boot units, runtime copy =="

# 1a. stop the boot units first so nothing re-ups the stack.
for u in digitaltwins-platform digitaltwins-worker; do
  if systemctl list-unit-files "$u.service" >/dev/null 2>&1 && systemctl cat "$u.service" >/dev/null 2>&1; then
    run "systemctl disable --now $u.service"
    run "rm -f /etc/systemd/system/$u.service"
  fi
done
run "systemctl daemon-reload"

# 1b. tear the stack down (data volumes + containers + networks). Keep images at
#     this tier (fast re-install); 'bare' removes them below.
#     First the graceful compose path, THEN a guaranteed by-label/name sweep so
#     nothing survives (see force_project_teardown). Resolve project names BEFORE
#     1c deletes the runtime dirs their .env lives in.
plat_project="$(project_name "$RUNTIME_DIR" digitaltwins-platform)"
comp_project="$(project_name "$COMPUTE_DIR"  digitaltwins-compute)"
compose_down "$RUNTIME_DIR" ""
compose_down "$COMPUTE_DIR" ""
force_project_teardown "$plat_project"
force_project_teardown "$comp_project"

# 1c. delete the runtime repo copy(ies). sync-runtime recreates from clean_src.
[ -d "$RUNTIME_DIR" ] && run "rm -rf '$RUNTIME_DIR'"
[ -d "$COMPUTE_DIR" ] && run "rm -rf '$COMPUTE_DIR'"

# =============================================================================
# TIER 2 — repair the apt/pip damage (NEEDS ONE-TIME ONLINE ACCESS)
# =============================================================================
if [ "$LEVEL" = apt ] || [ "$LEVEL" = bare ]; then
  echo; echo "== Tier 2: repair apt / pip (needs the box ONLINE) =="

  # Purge ONLY platform-added packages. NEVER python3 / python3-minimal / *-minimal.
  run "apt-get purge -y certbot python3-certbot python3-acme"
  run "apt-get autoremove -y"

  # Re-align system Python to one consistent archive version (REPAIR, not remove) —
  # this undoes the skew from a bundle 'dpkg -i' unpacking a mismatched python3.12.
  run "apt-get update"
  run "apt-get install --only-upgrade -y python3.12 python3.12-minimal libpython3.12-stdlib python3.12-venv python3.12-dev"
  run "apt-get -f install -y"
  run "dpkg --configure -a"

  # Remove pip cruft added with --break-system-packages during the cert scramble.
  run "pip3 uninstall -y certbot acme josepy pyRFC3339 ConfigArgParse parsedatetime 2>/dev/null"
  # (Leave apt-managed python alone; only pip-installed extras are removed.)

  echo "  NOTE: on re-install, DON'T 'dpkg -i apt-debs/*.deb' — use util/install-apt-debs.sh"
  echo "        (local repo, resolves deps) or plain apt when online. That's what avoids this."
fi

# =============================================================================
# TIER 3 — bare baseline: docker, ufw, letsencrypt
# =============================================================================
if [ "$LEVEL" = bare ]; then
  echo; echo "== Tier 3: bare baseline (docker, ufw, letsencrypt) =="

  # nuke every remaining docker artifact (images/volumes/networks/build cache)
  run "docker system prune -af --volumes"

  # remove the docker engine — covers BOTH install methods:
  #   apt (connected install)  and  static tarball + systemd unit (airgap step2)
  run "apt-get purge -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin 2>/dev/null"
  run "systemctl disable --now docker.service docker.socket containerd.service 2>/dev/null"
  run "rm -f /usr/local/bin/docker /usr/local/bin/dockerd /usr/local/bin/docker-init /usr/local/bin/docker-proxy /usr/local/bin/containerd /usr/local/bin/containerd-shim* /usr/local/bin/ctr /usr/local/bin/runc"
  run "rm -f /usr/local/lib/docker/cli-plugins/docker-compose /etc/systemd/system/docker.service /etc/systemd/system/docker.socket /etc/systemd/system/containerd.service"
  run "systemctl daemon-reload"

  # ufw back to the distro default (the install / airgap.sh re-applies its rules)
  run "ufw --force reset"

  # wipe Let's Encrypt so certs are re-issued fresh on re-install
  run "rm -rf /etc/letsencrypt"
fi

# =============================================================================
echo
echo "reset: done (level=$LEVEL)${DRY:+ — DRY RUN, nothing changed}."
echo "preserved: $BUNDLE (bundle + data/ + certs)."
case "$LEVEL" in
  platform) echo "next: re-render .env (util/gen-env.sh), sync-runtime, then bring the stack up." ;;
  apt)      echo "next: as above; apt/pip are repaired (verify: 'certbot --version' won't run — it's purged; that's expected)." ;;
  bare)     echo "next: start from the install README (step 2 installs docker again)." ;;
esac
