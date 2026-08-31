#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# install-apt-debs.sh — install the offline apt package set on an AIRGAPPED box.
#
# Treats the bundled apt-debs/ as a LOCAL apt repository and installs through
# apt, so dependencies are RESOLVED and CONFIGURED — the same end state a
# connected `apt-get install` produces. This replaces `dpkg -i *.deb`, which
# unpacks without resolving deps and leaves packages half-configured ('iU') plus
# a "dependency problems" warning whenever a dep is missing from the set.
#
# apt is restricted to ONLY the local repo (via -o Dir::Etc::*), so it never
# reaches for the box's unreachable upstream mirrors, and it picks the local debs
# rather than a newer upstream version it can't download.
#
#   sudo util/install-apt-debs.sh [pkg ...]
#     REPO   : $APT_DEBS_DIR or /mnt/install_src/airgap/apt-debs
#     pkg ...: packages to install (default: the repo's INSTALL.list, written by
#              build-apt-debs.sh; falls back to the pip/venv bootstrap set)
# ---------------------------------------------------------------------------
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "run as root (sudo util/install-apt-debs.sh)"; exit 1; }

REPO="${APT_DEBS_DIR:-/mnt/install_src/airgap/apt-debs}"
[ -f "$REPO/Packages" ] || {
  echo "ERROR: no Packages index in $REPO — (re)build it with build-apt-debs.sh." >&2
  echo "       A bare deb dir can't be resolved with apt; that's the old bug." >&2
  exit 1; }

# What to install: args > repo INSTALL.list > pip/venv bootstrap fallback.
if [ "$#" -gt 0 ]; then
  PKGS=("$@")
elif [ -f "$REPO/INSTALL.list" ]; then
  mapfile -t PKGS < "$REPO/INSTALL.list"
else
  PKGS=(python3-pip python3-venv python3.12-venv)
fi

LIST="$(mktemp /etc/apt/sources.list.d/airgap-local.XXXX.list)"
echo "deb [trusted=yes] file://$REPO ./" > "$LIST"
cleanup() { rm -f "$LIST"; }
trap cleanup EXIT

# Consider ONLY the local repo for both the index refresh and the install, so an
# airgapped box neither hits its dead mirrors nor tries to pull a newer upstream
# version of a dep it can't reach.
APT_ONLY_LOCAL=(-o Dir::Etc::sourcelist="$LIST"
                -o Dir::Etc::sourceparts="/dev/null"
                -o APT::Get::List-Cleanup="0")

# On an AIRGAPPED box, installing packages triggers two things that hang forever
# waiting on the network:
#   * esm-cache.service (ubuntu-pro-client) refreshes ESM apt metadata from
#     Canonical — a package trigger fires it and it sits on DNS/HTTP timeouts.
#   * needrestart then BATCH-restarts services on outdated libs, and lumps
#     esm-cache in with the rest (the classic
#     "systemctl restart esm-cache.service fail2ban.service" stall).
# Mask esm-cache so it can't run, and drive this apt run with needrestart in
# list-only mode + a non-interactive frontend so nothing restarts or prompts
# mid-transaction. All idempotent and guarded — a no-op where they don't apply.
if command -v systemctl >/dev/null 2>&1; then
  systemctl kill --signal=SIGKILL esm-cache.service 2>/dev/null || true   # unstick a running one
  systemctl mask esm-cache.service esm-cache.timer   2>/dev/null || true
fi

echo "repo     : $REPO"
echo "install  : ${PKGS[*]}"
apt-get "${APT_ONLY_LOCAL[@]}" update
DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l \
  apt-get "${APT_ONLY_LOCAL[@]}" install -y "${PKGS[@]}"

echo "done. verify with:  apt-mark showmanual >/dev/null; certbot --version 2>/dev/null || true"
