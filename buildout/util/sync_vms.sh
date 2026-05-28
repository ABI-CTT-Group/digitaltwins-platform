#!/bin/bash
# Sync digitaltwins-platform code to all VMs.
#
# - abi_portal, abi_mp:
#     1. rsync to /mnt/install_src/clean_src/ (installer source, may be USB)
#     2. rsync to ~/digitaltwins-platform/ (running deployment, skipping
#        environment-specific generated files — see deploy-sync-excludes)
# - gendev: git pull
#
# Usage:
#   bash buildout/util/sync_vms.sh

set -euo pipefail

VM_LIST="abi_portal abi_mp"
LOCAL_SRC=~/twins/digitaltwins-platform
EXCLUDES="$LOCAL_SRC/buildout/util/deploy-sync-excludes"

# ── rsync clean_src on production VMs ────────────────────────────────────────
for VM in $VM_LIST; do
    echo "=== Rsyncing clean_src on $VM ==="
    rsync -av --progress --exclude='.git' --filter=':- .gitignore' \
        "$LOCAL_SRC/" "$VM:/mnt/install_src/clean_src/digitaltwins-platform/"

    echo "=== Rsyncing running deployment on $VM ==="
    rsync -av --progress \
        --exclude-from="$EXCLUDES" \
        --filter=':- .gitignore' \
        "$LOCAL_SRC/" "$VM:~/digitaltwins-platform/"
done

# ── gendev: git pull ──────────────────────────────────────────────────────────
echo "=== Syncing gendev ==="
ssh gendev bash <<'ENDSSH'
set -euo pipefail
cd ~/twins/digitaltwins-platform
git pull
#git submodule update --remote
git submodule update
echo "Done."
ENDSSH
