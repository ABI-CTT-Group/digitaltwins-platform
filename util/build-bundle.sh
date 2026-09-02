#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# build-bundle.sh — build the airgap install bundle in ONE command, self-verifying.
#
# Runs Phase A of BUILD-FULL-SYSTEM.md end to end on a CONNECTED build box:
#   A.0.1 bootstrap tooling → A.1 code+config → A.2 offline packages →
#   A.3 platform freeze → A.4 obs image bundle → A.5 completeness GATE.
#
# Every step is verified at the step (fail loud, not three phases later), and the
# run ends on the A.5 gate — so you get either "== BUNDLE COMPLETE ==" and a
# shippable /mnt/install_src, or a precise STOP naming what's wrong. No hand-walking,
# no "did I run build-apt-debs?", no discovering gaps at install time.
#
# It is idempotent: re-running skips steps whose output already exists (use --force
# to redo). It self-re-execs under the docker group after adding you (no logout).
#
#   ./build-bundle.sh                 # full build + gate
#   ./build-bundle.sh --gate-only     # just re-run the A.5 completeness gate
#   ./build-bundle.sh --from packages # resume from a phase (bootstrap|code|packages|freeze|obsimages|gate)
#   ./build-bundle.sh --force         # redo steps even if their output exists
#   ./build-bundle.sh --yes           # accept data/env + data/secrets.env as-is (don't stop to fill them)
#   ./build-bundle.sh --clean         # wipe generated artifacts + docker volumes first
#
# Env: SRC_DIR (default /mnt/install_src), BRANCH (default main).
#
# Run as your NORMAL user (not sudo) on a box with internet + passwordless sudo.
# On a truly bare box, get this script first:
#   curl -fsSLO https://raw.githubusercontent.com/ABI-CTT-Group/digitaltwins-platform/main/util/build-bundle.sh
# ---------------------------------------------------------------------------
set -euo pipefail

SELF="$(readlink -f "$0")"
SRC="${SRC_DIR:-/mnt/install_src}"
CS="$SRC/clean_src/digitaltwins-platform"
AIRGAP="$SRC/airgap"
BRANCH="${BRANCH:-main}"
REPO="${REPO:-https://github.com/ABI-CTT-Group/digitaltwins-platform.git}"

FROM=""; GATE_ONLY=0; FORCE=0; CLEAN=0; ACCEPT=0
while [ $# -gt 0 ]; do
  case "$1" in
    --from) FROM="$2"; shift 2 ;;
    --gate-only) GATE_ONLY=1; shift ;;
    --force) FORCE=1; shift ;;
    --clean) CLEAN=1; shift ;;
    -y|--yes|--accept-config) ACCEPT=1; shift ;;
    -h|--help) sed -n '2,33p' "$SELF"; exit 0 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done
# re-exec preserves the flags (not raw $@) so the docker-group restart is transparent.
# Built with `if` (not $(...&&echo...)) — a false command-substitution would make the
# assignment non-zero and set -e would kill the script silently.
REEXEC_ARGS=""
if [ -n "$FROM" ];       then REEXEC_ARGS+=" --from $FROM"; fi
if [ "$GATE_ONLY" = 1 ]; then REEXEC_ARGS+=" --gate-only"; fi
if [ "$FORCE" = 1 ];     then REEXEC_ARGS+=" --force"; fi
if [ "$CLEAN" = 1 ];     then REEXEC_ARGS+=" --clean"; fi
if [ "$ACCEPT" = 1 ];    then REEXEC_ARGS+=" --yes"; fi

c_hdr=$'\033[1;36m'; c_ok=$'\033[32m'; c_warn=$'\033[1;33m'; c_err=$'\033[1;31m'; c_off=$'\033[0m'
log()  { printf '\n%s==> %s%s\n' "$c_hdr" "$*" "$c_off"; }
ok()   { printf '  %sok%s %s\n' "$c_ok" "$c_off" "$*"; }
warn() { printf '%sWARN: %s%s\n' "$c_warn" "$*" "$c_off" >&2; }
die()  { printf '%sSTOP: %s%s\n' "$c_err" "$*" "$c_off" >&2; exit 1; }

[ "$(id -u)" -ne 0 ] || die "run as your normal login user (not root/sudo) — it escalates per step, and Docker/ownership need your user."

# ── A.0.1  bootstrap the build box ──────────────────────────────────────────
bootstrap() {
  log "A.0.1  bootstrap build-box tooling"
  command -v docker >/dev/null 2>&1 || { log "installing docker (get.docker.com)"; curl -fsSL https://get.docker.com | sudo sh; }
  if ! id -nG | tr ' ' '\n' | grep -qx docker; then
    log "adding $USER to the docker group + re-entering shell with it (no logout needed)"
    sudo usermod -aG docker "$USER"
    exec sg docker -c "$(printf '%q' "$SELF") $REEXEC_ARGS"
  fi
  local need=()
  command -v ansible-playbook  >/dev/null 2>&1 || need+=(ansible)
  command -v dpkg-scanpackages  >/dev/null 2>&1 || need+=(dpkg-dev)
  command -v pip3               >/dev/null 2>&1 || need+=(python3-pip)
  [ "${#need[@]}" -eq 0 ] || { log "apt install: ${need[*]}"; sudo apt-get update -qq && sudo apt-get install -y "${need[@]}"; }
  command -v k3s  >/dev/null 2>&1 || { log "installing k3s (containerd = the image pull/export engine)"; curl -sfL https://get.k3s.io | sh -; }
  command -v helm >/dev/null 2>&1 || { log "installing helm"; curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash; }
  local c
  for c in docker ansible-playbook dpkg-scanpackages pip3 k3s helm; do
    command -v "$c" >/dev/null 2>&1 && ok "$c" || die "$c still missing after bootstrap"
  done
  sudo k3s ctr version >/dev/null 2>&1 || die "'sudo k3s ctr' not working — is k3s running? (systemctl status k3s)"
}

# ── A.1  code + config ──────────────────────────────────────────────────────
code_config() {
  log "A.1  code + config"
  if [ -d "$CS/.git" ]; then
    ( cd "$CS" && git fetch origin -q && git checkout -q "$BRANCH" && git pull -q && git submodule update --init --recursive -q )
    ok "clean_src refreshed on $BRANCH"
  else
    mkdir -p "$SRC/clean_src"
    git clone --recurse-submodules -b "$BRANCH" "$REPO" "$CS"
    ok "clean_src cloned"
  fi
  mkdir -p "$SRC/data"
  local fresh=0
  [ -f "$SRC/data/env" ]         || { cp "$CS/env.template"         "$SRC/data/env";         fresh=1; }
  [ -f "$SRC/data/secrets.env" ] || { cp "$CS/secrets.env.template" "$SRC/data/secrets.env"; fresh=1; }
  if [ "$fresh" -ne 0 ]; then
    if [ "$ACCEPT" = 1 ]; then
      warn "data/env + data/secrets.env were just created from templates, and --yes was given — proceeding with them AS-IS. Make sure they're actually filled in."
    else
      die "created data/env + data/secrets.env from templates — FILL THEM IN (PLATFORM_DOMAIN, DB/SEEK passwords, GRAFANA_*, MIMIR_*) then re-run; or pass --yes to accept them as-is. (Config is not code; the build can't invent your secrets.)"
    fi
  fi
  ok "data/env + data/secrets.env present (using the values as-is)"
  # TLS cert — required for https (A.3/step3 verifies + installs data/{fullchain,privkey}.pem).
  # Check it HERE (seconds in) rather than let A.3's platform build get 20 min in and fail.
  local proto
  proto="$(grep -E '^(export[[:space:]]+)?PLATFORM_PROTOCOL=' "$SRC/data/env" | tail -1 | sed -E 's/.*=//; s/["'\'' ]//g' || true)"
  proto="${proto:-https}"
  if [ "$proto" = https ]; then
    { [ -e "$SRC/data/fullchain.pem" ] && [ -e "$SRC/data/privkey.pem" ]; } \
      || die "PLATFORM_PROTOCOL=https but data/fullchain.pem and/or data/privkey.pem missing (or a dangling symlink) — put the TLS cert, or symlinks to it, in data/ (see INSTALL-BUNDLE). A.3 needs it."
    ok "TLS cert (data/fullchain.pem + privkey.pem)"
  else
    ok "PLATFORM_PROTOCOL=$proto — no TLS cert needed"
  fi
}

# ── A.2  offline packages + binaries ────────────────────────────────────────
offline_packages() {
  log "A.2  offline packages + binaries"
  if [ "$FORCE" = 1 ] || ! ls "$AIRGAP"/pip-wheels/kubernetes-* >/dev/null 2>&1; then
    AIRGAP_DIR="$AIRGAP" "$CS/util/fetch_airgap.sh"
  else ok "fetch_airgap outputs present (skip; --force to redo)"; fi
  # verify the pieces the install actually consumes (these silently went missing before)
  test -s "$AIRGAP/binaries/alloy-linux-amd64.zip"            || die "fetch_airgap: airgap/binaries/alloy-linux-amd64.zip missing"
  test -s "$AIRGAP/binaries/k3s-airgap-images-amd64.tar.gz"   || die "fetch_airgap: airgap/binaries/k3s-airgap-images-amd64.tar.gz missing"
  test -s "$AIRGAP/binaries/k3s"                              || die "fetch_airgap: airgap/binaries/k3s missing"
  test -s "$AIRGAP/binaries/helm-linux-amd64.tar.gz"          || die "fetch_airgap: airgap/binaries/helm-linux-amd64.tar.gz missing"
  ls "$AIRGAP"/pip-wheels/kubernetes-* >/dev/null 2>&1        || die "fetch_airgap: airgap/pip-wheels (kubernetes client) empty — is pip3 installed?"
  ok "binaries + pip-wheels"

  # re-run if EITHER the index or the manifest is missing (a bare dpkg-scanpackages
  # recovery writes Packages but not INSTALL.list — don't let that slip through)
  if [ "$FORCE" = 1 ] || [ ! -s "$AIRGAP/apt-debs/Packages" ] || [ ! -s "$AIRGAP/apt-debs/INSTALL.list" ]; then
    "$CS/util/build-apt-debs.sh"
  else ok "apt-debs Packages + INSTALL.list present (skip)"; fi
  test -s "$AIRGAP/apt-debs/Packages"     || die "build-apt-debs: airgap/apt-debs/Packages missing (dpkg-dev installed? internet up?)"
  test -s "$AIRGAP/apt-debs/INSTALL.list" || die "build-apt-debs: airgap/apt-debs/INSTALL.list missing — regenerate with build-apt-debs.sh (not a bare dpkg-scanpackages)"
  ok "apt repo index + manifest"

  # docker static binaries — versions read from airgap_build_step2.yml so they can't drift
  local dtgz dcver
  dtgz="$(grep -oE 'docker-[0-9][0-9.]*\.tgz' "$CS/util/airgap_build_step2.yml" | head -1 || true)"
  dcver="$(grep -oE 'v[0-9]+\.[0-9]+\.[0-9]+' "$CS/util/airgap_build_step2.yml" | head -1 || true)"
  [ -n "$dtgz" ] && [ -n "$dcver" ] || die "could not read docker/compose versions from airgap_build_step2.yml"
  [ -s "$SRC/$dtgz" ] || { log "fetching $dtgz"; wget -qO "$SRC/$dtgz" "https://download.docker.com/linux/static/stable/x86_64/$dtgz"; }
  [ -s "$SRC/docker-compose-linux-x86_64-$dcver" ] || { log "fetching compose $dcver"; wget -qO "$SRC/docker-compose-linux-x86_64-$dcver" "https://github.com/docker/compose/releases/download/$dcver/docker-compose-linux-x86_64"; }
  ok "docker static binaries ($dtgz, $dcver)"

  if [ "$FORCE" = 1 ] || [ ! -s "$SRC/ansible-packages.tar.gz" ]; then
    log "downloading ansible wheels"
    rm -rf "$SRC/ansible-packages"; pip3 download ansible -d "$SRC/ansible-packages/" --quiet
    tar -C "$SRC" -czf "$SRC/ansible-packages.tar.gz" ansible-packages/ && rm -rf "$SRC/ansible-packages/"
  else ok "ansible-packages.tar.gz present (skip)"; fi
  test -s "$SRC/ansible-packages.tar.gz" || die "ansible wheels tarball missing"

  [ -s "$SRC/alpine.tar" ] || { log "saving alpine helper image"; docker pull -q alpine && docker save alpine > "$SRC/alpine.tar"; }
  ok "alpine.tar"
}

# ── A.3  platform images (build from source, then freeze) ───────────────────
platform_freeze() {
  log "A.3  platform images (build from source, then freeze)"
  if [ "$FORCE" != 1 ] && [ -s "$SRC/digitaltwins-images-all.tar.gz" ] && [ -s "$SRC/airflow-worker.tar.gz" ]; then
    ok "frozen image archive + worker present (skip; --force to re-freeze)"; return 0
  fi
  set -a; . "$SRC/data/secrets.env"; . "$SRC/data/env"; set +a   # step3 reads PLATFORM_DOMAIN/MySQL/SEEK creds from the env
  ansible-playbook -i "localhost," -c local "$CS/util/airgap_build_step3.yml" \
    -e "ansible_user=$USER" -e "install_src_dir=$SRC" -e load_frozen_images=false
  log "freezing images"
  INSTALL_SRC_DIR="$SRC" "$CS/util/freeze_images.sh"
  docker save digitaltwins-platform-airflow-worker:latest | gzip > "$SRC/airflow-worker.tar.gz"
  test -s "$SRC/digitaltwins-images-all.tar.gz" || die "freeze_images did not write digitaltwins-images-all.tar.gz"
  test -s "$SRC/airflow-worker.tar.gz"          || die "worker image save failed"
  ok "platform images frozen"
}

# ── A.4  observability image bundle (deterministic, chart-driven) ───────────
obs_images() {
  log "A.4  observability image bundle"
  if [ "$FORCE" != 1 ] && [ -s "$AIRGAP/images/k3s-images.tar.gz" ] && [ -s "$AIRGAP/images/image-list.txt" ]; then
    ok "obs image bundle present (skip; --force to rebuild)"; return 0
  fi
  AIRGAP_DIR="$AIRGAP" "$CS/util/build_image_bundle.sh"
  test -s "$AIRGAP/images/k3s-images.tar.gz" || die "build_image_bundle did not write images/k3s-images.tar.gz"
  ok "obs image bundle built"
}

# ── A.5  completeness GATE ──────────────────────────────────────────────────
gate() {
  log "A.5  completeness gate"
  local f gaps=0
  for f in \
    "$CS" "$SRC/data" "$SRC/data/env" "$SRC/data/secrets.env" \
    "$SRC"/ansible-packages.tar.gz "$SRC"/alpine.tar \
    "$SRC"/docker-*.tgz "$SRC"/docker-compose-linux-x86_64-* \
    "$SRC"/digitaltwins-images-all.tar.gz "$SRC"/airflow-worker.tar.gz \
    "$AIRGAP"/apt-debs/Packages "$AIRGAP"/apt-debs/INSTALL.list \
    "$AIRGAP"/binaries/alloy-linux-amd64.zip "$AIRGAP"/binaries/k3s \
    "$AIRGAP"/binaries/k3s-airgap-images-amd64.tar.gz "$AIRGAP"/binaries/helm-linux-amd64.tar.gz \
    "$AIRGAP"/pip-wheels/kubernetes-* \
    "$AIRGAP"/images/k3s-images.tar.gz "$AIRGAP"/images/image-list.txt ; do
    if ls -d $f >/dev/null 2>&1; then ok "$f"; else printf '  %sMISSING%s %s\n' "$c_err" "$c_off" "$f"; gaps=1; fi
  done
  [ "$gaps" -eq 0 ] || die "bundle INCOMPLETE — do NOT ship / drop the build box. Fix the MISSING items (re-run the relevant phase) and re-run."
  printf '\n%s== BUNDLE COMPLETE ==%s  ship %s to each target.\n' "$c_ok" "$c_off" "$SRC"
}

# ── driver ──────────────────────────────────────────────────────────────────
[ -d "$SRC" ] || die "$SRC not found — mount the install-source volume first (util/mount_src.sh)."

if [ "$CLEAN" = 1 ]; then
  log "--clean: wiping generated artifacts + docker volumes (clean_src + data kept)"
  ( cd "$SRC" && rm -rf airgap ansible-packages.tar.gz ./*.tgz docker-compose-linux-x86_64-* \
      digitaltwins-images-all.tar.gz airflow-worker.tar.gz alpine.tar 2>/dev/null || true )
  ( cd "$HOME/digitaltwins-platform" 2>/dev/null && docker compose down 2>/dev/null ) || true
  [ -x "$CS/util/docker_delete_volumes.sh" ] && "$CS/util/docker_delete_volumes.sh" || true
fi

if [ "$GATE_ONLY" = 1 ]; then gate; exit 0; fi

# phase order + optional --from resume
phases=(bootstrap code_config offline_packages platform_freeze obs_images gate)
start=0
if [ -n "$FROM" ]; then
  case "$FROM" in
    bootstrap) start=0 ;; code) start=1 ;; packages) start=2 ;;
    freeze) start=3 ;; obsimages) start=4 ;; gate) start=5 ;;
    *) die "unknown --from phase '$FROM' (bootstrap|code|packages|freeze|obsimages|gate)" ;;
  esac
fi
for i in "${!phases[@]}"; do
  [ "$i" -ge "$start" ] && "${phases[$i]}"
done
