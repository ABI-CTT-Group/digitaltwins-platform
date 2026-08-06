#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# build-apt-debs.sh — (re)build the offline apt package set as a real LOCAL REPO.
#
# Run on a CONNECTED host that matches the target release (Ubuntu 24.04 "noble").
# It downloads the FULL dependency closure of the requested packages — not just
# the named ones — so that an airgapped `apt-get install` can RESOLVE and
# CONFIGURE them exactly like a connected install would: no half-configured
# ('iU') packages, no "dependency problems" warnings. Then it writes the
# Packages index (so the dir is a valid apt repo) and an INSTALL.list manifest of
# the top-level targets for install-apt-debs.sh to consume.
#
# The old approach (`apt-get download <names>` + `dpkg -i *.deb`) shipped only
# the named packages and could not resolve deps on the target — which is why
# e.g. certbot arrived without python3-josepy/python3-acme and stuck at 'iU'.
#
#   util/build-apt-debs.sh [-o OUTDIR] [pkg ...]
#     -o OUTDIR   output dir (default: /mnt/install_src/airgap/apt-debs)
#     pkg ...     top-level packages (default: the bootstrap + certbot set below)
# ---------------------------------------------------------------------------
set -euo pipefail

OUTDIR=/mnt/install_src/airgap/apt-debs
if [ "${1:-}" = "-o" ]; then OUTDIR="${2:?-o needs a dir}"; shift 2; fi

# Bootstrap set (pip/venv → lets us pip-install ansible) + tools the bundle
# has historically carried. certbot is here so its closure (python3-acme,
# python3-josepy, …) is pulled in — that is the bug this fixes.
DEFAULT_PKGS=(python3-pip python3-venv python3.12-venv python3-yaml unzip certbot)
PKGS=("$@"); [ "${#PKGS[@]}" -eq 0 ] && PKGS=("${DEFAULT_PKGS[@]}")

command -v dpkg-scanpackages >/dev/null || {
  echo "ERROR: dpkg-scanpackages missing — sudo apt-get install dpkg-dev" >&2; exit 1; }

. /etc/os-release
echo "release  : ${VERSION_CODENAME:-?} ${VERSION_ID:-?}  ($(dpkg --print-architecture))"
echo "targets  : ${PKGS[*]}"
echo "outdir   : $OUTDIR"

mkdir -p "$OUTDIR"; cd "$OUTDIR"
# Refresh lists if we can, but don't require root — apt-cache/apt-get download
# work off the existing lists, and this dir is normally user-owned.
apt-get update 2>/dev/null || sudo apt-get update 2>/dev/null \
  || echo "note: couldn't refresh apt lists — using existing ones"

# Full recursive dependency closure, real package names only:
#   apt-cache depends --recurse walks the whole tree; ^[a-z0-9] keeps the
#   column-0 package names and drops the indented "Depends:" lines; the -v '<'
#   drops virtual packages (e.g. <awk>), which apt-get download can't fetch.
echo "resolving dependency closure…"
mapfile -t CLOSURE < <(
  apt-cache depends --recurse --no-recommends --no-suggests \
    --no-conflicts --no-breaks --no-replaces --no-enhances "${PKGS[@]}" \
  | grep -E '^[a-z0-9]' | grep -v '<' | sort -u )
echo "closure  : ${#CLOSURE[@]} packages"

# Fresh set — clear old debs so stale versions don't linger in the repo.
rm -f ./*.deb
# Download each individually so one unfetchable pkg (rare: base-image-only) does
# not abort the whole set; report any skips loudly.
skipped=()
for p in "${CLOSURE[@]}"; do
  apt-get download "$p" >/dev/null 2>&1 || skipped+=("$p")
done
echo "debs     : $(ls -1 ./*.deb 2>/dev/null | wc -l) downloaded"
[ "${#skipped[@]}" -gt 0 ] && printf 'skipped  : %s\n' "${skipped[*]}" \
  && echo "  (skips are usually base-image packages already present on every target)"

# Build the apt repo index + the top-level manifest install-apt-debs.sh reads.
dpkg-scanpackages --multiversion . /dev/null > Packages
gzip -9c Packages > Packages.gz
printf '%s\n' "${PKGS[@]}" > INSTALL.list

echo "wrote    : Packages, Packages.gz, INSTALL.list"
echo "done. Install on the airgapped target with:  sudo util/install-apt-debs.sh"
