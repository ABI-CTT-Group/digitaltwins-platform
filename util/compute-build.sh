#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# compute-build.sh — seed a fresh (airgapped) compute node with the SUBSET of
# /mnt/install_src it needs to come up. Run this ON THE PORTAL (the box that
# already holds a full /mnt/install_src). It creates /mnt/install_src on the
# target node and rsyncs the required pieces over the VLAN.
#
# What a compute node needs (and what this copies) — NOT the 6.3G portal image
# bundle, just:
#   clean_src/                          the code (util scripts, playbooks,
#                                        compute-worker compose, alloy config)
#   docker-*.tgz + docker-compose-*     docker static binaries (airgap step2)
#   ansible-packages.tar.gz             ansible wheels (to run step2)
#   airgap/apt-debs/                    offline apt repo (python3-pip, unzip, …)
#   airgap/binaries/alloy-linux-amd64.zip   Alloy (obs shipping; optional)
#   airflow-worker.tar.gz               the worker image (docker load)
#
#   util/compute-build.sh [user@]<node-host> [remote_mnt_dir]
#     e.g.  util/compute-build.sh ubuntu@10.2.0.14
#           SSH_OPTS='-J abi_portal' util/compute-build.sh ubuntu@10.2.0.14
#           DRY_RUN=1 util/compute-build.sh ubuntu@10.2.0.14      # preview only
#
# Env:
#   SRC_DIR    source bundle dir on THIS box     (default /mnt/install_src)
#   SSH_OPTS   extra ssh options, e.g. '-J jump' (default empty)
#   DRY_RUN    non-empty = rsync --dry-run, skip remote mkdir
#
# NOT copied (they aren't in /mnt/install_src) — do these separately, from the
# portal, per util/compute-node-README.md:
#   * the node's .env  ->  util/generate-compute-env.sh <portal_vlan_ip> ... then scp
#   * the workflow DAGs -> util/sync-compute-dags.sh <node>
#
# Refresh the bundle's code first so the node gets the latest scripts:
#   ( cd /mnt/install_src/clean_src/digitaltwins-platform && git pull \
#       && git submodule update --init --recursive )
# ---------------------------------------------------------------------------
set -euo pipefail

TARGET="${1:?usage: compute-build.sh [user@]<node-host> [remote_mnt_dir]}"
REMOTE_MNT="${2:-/mnt/install_src}"
SRC="${SRC_DIR:-/mnt/install_src}"
SSH_OPTS="${SSH_OPTS:-}"

[ -d "$SRC" ] || { echo "ERROR: source bundle $SRC not found on this box (set SRC_DIR)." >&2; exit 1; }
command -v rsync >/dev/null 2>&1 || { echo "ERROR: rsync not installed on this box." >&2; exit 1; }

cd "$SRC"
shopt -s nullglob

# Patterns (relative to $SRC). Globs tolerate version bumps; plain names are
# checked for existence below. apt-debs is the whole repo; from binaries we take
# ONLY the alloy zip (k3s/helm/k9s are portal-only, node doesn't run k3s).
PATTERNS=(
  clean_src
  docker-*.tgz
  docker-compose-linux-x86_64-*
  ansible-packages.tar.gz
  airflow-worker.tar.gz
  airgap/apt-debs
  airgap/binaries/alloy-linux-amd64.zip
)
# Items whose absence should HARD-FAIL (a node can't come up without them).
CRITICAL=(clean_src docker-*.tgz airflow-worker.tar.gz airgap/apt-debs)

ITEMS=()
for pat in "${PATTERNS[@]}"; do
  found=0
  for p in $pat; do [ -e "$p" ] && { ITEMS+=("$p"); found=1; }; done
  if [ "$found" -eq 0 ]; then
    hard=0; for c in "${CRITICAL[@]}"; do [ "$c" = "$pat" ] && hard=1; done
    if [ "$hard" -eq 1 ]; then
      echo "ERROR: required '$pat' not found in $SRC — build the bundle first." >&2
      exit 1
    fi
    echo "note: optional '$pat' not in $SRC — skipping (e.g. alloy needs fetch_airgap.sh)." >&2
  fi
done

echo "==> Seeding compute node '$TARGET':$REMOTE_MNT from $SRC"
echo "    items: ${ITEMS[*]}"
du -shc "${ITEMS[@]}" 2>/dev/null | awk 'END{print "    total to copy: " $1}'

RSYNC_OPTS=(-aR --human-readable --info=progress2 --partial)
if [ -n "$DRY_RUN" ]; then
  echo "==> DRY RUN (no changes)"
  RSYNC_OPTS+=(--dry-run)
else
  echo "==> Creating $REMOTE_MNT on the node (owned by the login user)"
  # shellcheck disable=SC2029  # deliberately expand id/quoting on the REMOTE side
  ssh $SSH_OPTS "$TARGET" \
    "sudo mkdir -p '$REMOTE_MNT' && sudo chown \"\$(id -un)\":\"\$(id -gn)\" '$REMOTE_MNT'"
fi

echo "==> rsync -> $TARGET:$REMOTE_MNT/"
rsync "${RSYNC_OPTS[@]}" -e "ssh $SSH_OPTS" "${ITEMS[@]}" "$TARGET:$REMOTE_MNT/"

echo
echo "Done. On the node ($TARGET), from a login shell:"
cat <<EOF
  CS=$REMOTE_MNT/clean_src/digitaltwins-platform

  # 1) OS deps (unzip, pip) + ansible from the bundle
  sudo "\$CS/util/install-apt-debs.sh"
  tar xzf $REMOTE_MNT/ansible-packages.tar.gz -C ~ \\
    && pip3 install --no-index --find-links ~/ansible-packages/ ansible --break-system-packages
  #   ... log out/in so ansible-playbook is on PATH ...

  # 2) Docker (static binaries)
  ansible-playbook -i "localhost," -c local "\$CS/util/airgap_build_step2.yml" \\
    -e "ansible_user=\$USER" -e "install_src_dir=$REMOTE_MNT"
  #   ... log out/in so the docker group takes ...

  # 3) Worker + Alloy  (see util/compute-node-README.md §C/§D/§G;
  #     the node's .env comes from the portal's generate-compute-env.sh)
  docker load -i $REMOTE_MNT/airflow-worker.tar.gz
EOF
