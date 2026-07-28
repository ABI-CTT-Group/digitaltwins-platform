#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# mount_src.sh — mount the install-source drive at /mnt/install_src.
#
# This is airgap build "step 0" (the old buildout/util/mount_install_src and
# airgap_build_step0.yml): the persistent /dev/vdb volume that carries the repo
# checkout, data/, and frozen images survives VM rebuilds, unlike the ephemeral
# root disk. Mount it and add it to fstab so it comes back after a reboot.
#
# Run as root (or with sudo). Idempotent — safe to re-run.
#
#   sudo util/mount_src.sh                 # /dev/vdb -> /mnt/install_src
#   sudo SRC_DEV=/dev/sdb1 util/mount_src.sh
#   sudo MOUNT_POINT=/mnt/other util/mount_src.sh
#
# If you plugged in a USB drive instead of the cloud volume, find its device
# with `lsblk` and pass it as SRC_DEV.
# ---------------------------------------------------------------------------
set -euo pipefail

SRC_DEV="${SRC_DEV:-/dev/vdb}"
MOUNT_POINT="${MOUNT_POINT:-/mnt/install_src}"
# When run via sudo, own the mount by the human user, not root, so the rest of
# the buildout (which runs unprivileged) can write to it.
OWNER="${OWNER:-${SUDO_USER:-ubuntu}}"

if [ "$(id -u)" -ne 0 ]; then
  echo "mount_src.sh: must run as root (use sudo)" >&2
  exit 1
fi

if [ ! -b "$SRC_DEV" ]; then
  echo "mount_src.sh: $SRC_DEV is not a block device — check \`lsblk\` and set SRC_DEV" >&2
  exit 1
fi

echo "==> Ensuring mount point $MOUNT_POINT"
mkdir -p "$MOUNT_POINT"
chmod 0755 "$MOUNT_POINT"
chown "$OWNER":"$OWNER" "$MOUNT_POINT"

# fstype auto lets mount detect the existing ext4/xfs on the volume.
fstab_line="$SRC_DEV $MOUNT_POINT auto defaults 0 0"
if grep -qsE "^[^#]*[[:space:]]${MOUNT_POINT}[[:space:]]" /etc/fstab; then
  echo "==> fstab already has an entry for $MOUNT_POINT — leaving it"
else
  echo "==> Adding to /etc/fstab: $fstab_line"
  printf '%s\n' "$fstab_line" >> /etc/fstab
fi

if mountpoint -q "$MOUNT_POINT"; then
  echo "==> $MOUNT_POINT is already mounted — nothing to do"
else
  echo "==> Mounting $SRC_DEV at $MOUNT_POINT"
  # Prefer the fstab entry we just ensured; fall back to an explicit mount.
  mount "$MOUNT_POINT" 2>/dev/null || mount -o defaults "$SRC_DEV" "$MOUNT_POINT"
fi

echo "==> Done:"
findmnt "$MOUNT_POINT" || true
