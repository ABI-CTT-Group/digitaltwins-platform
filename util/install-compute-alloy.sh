#!/usr/bin/env bash
# Install Grafana Alloy on a REMOTE COMPUTE NODE so it ships this box's docker
# logs, Airflow task logs and host metrics to the observability stack on the
# portal (Loki :3100 / Mimir :9005 over the VLAN).
#
# Run this ON THE COMPUTE NODE (e.g. drai-compute), as the normal login user
# (e.g. ubuntu). It's airgap-friendly: the alloy binary comes from the install
# bundle, same as every other compute-node component — no internet needed.
#
# Alloy runs as YOUR user (the one owning ~/digitaltwins-compute), NOT a separate
# 'alloy' system account. That user already owns its home, the worker's task logs
# are world-readable (0644), and it's in the docker group — so there's no ACL,
# chmod, or root-owned anything to wrangle. That's the whole point.
#
#   util/install-compute-alloy.sh <portal_vlan_ip> [install_src_dir]
#     e.g.  util/install-compute-alloy.sh 10.2.0.195
#           util/install-compute-alloy.sh 10.2.0.195 /mnt/install_src/airgap
#
# Prereqs (see util/compute-node-README.md §G):
#   - On the PORTAL: Loki/Mimir port-forwards bound to 0.0.0.0 AND
#     `util/ufw_for_remote_compute.sh <this_node_ip> 3100 9005` + the same two
#     ports opened to this node in the cloud security group.
#   - This repo checked out here, and the bundle's binaries/alloy-linux-amd64.zip.
set -euo pipefail

OBS_HOST="${1:?usage: install-compute-alloy.sh <portal_vlan_ip> [install_src_dir]}"
INSTALL_SRC="${2:-/mnt/install_src/airgap}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OBS_DIR="${SCRIPT_DIR}/observability"
ALLOY_ZIP="${INSTALL_SRC}/binaries/alloy-linux-amd64.zip"
NODE_NAME="$(hostname)"

# Run Alloy as the invoking login user (works whether or not the script itself is
# run under sudo). This is the user whose home holds the worker + its logs.
RUN_USER="${SUDO_USER:-$(id -un)}"
RUN_GROUP="$(id -gn "${RUN_USER}")"
RUN_HOME="$(getent passwd "${RUN_USER}" | cut -d: -f6)"

# HOST-side path of the worker's ./logs bind-mount (Airflow task logs live here).
# Alloy runs on the host, so it tails this, NOT the in-container /opt/airflow/logs.
WORKER_LOGS_DIR="${WORKER_LOGS_DIR:-${RUN_HOME}/digitaltwins-compute/logs}"

echo "==> Installing Alloy on '${NODE_NAME}' as user '${RUN_USER}', shipping to portal ${OBS_HOST} (Loki :3100 / Mimir :9005)"

for f in "${OBS_DIR}/config.alloy.compute" "${OBS_DIR}/alloy.service"; do
  [ -f "$f" ] || { echo "ERROR: missing $f — run from a full checkout of this repo" >&2; exit 1; }
done

# ── alloy binary (from the bundle) ──────────────────────────────────────────
if [ ! -x /usr/local/bin/alloy ]; then
  [ -f "${ALLOY_ZIP}" ] || { echo "ERROR: ${ALLOY_ZIP} not found (set install_src_dir arg)" >&2; exit 1; }
  command -v unzip >/dev/null 2>&1 || { echo "ERROR: unzip not installed" >&2; exit 1; }
  echo "==> Extracting alloy from ${ALLOY_ZIP}"
  sudo unzip -o "${ALLOY_ZIP}" alloy-linux-amd64 -d /tmp/
  sudo mv /tmp/alloy-linux-amd64 /usr/local/bin/alloy
  sudo chmod +x /usr/local/bin/alloy
else
  echo "==> alloy already at /usr/local/bin/alloy — keeping it"
fi

# ── dirs (owned by the run user) + docker socket access ─────────────────────
sudo install -d -o "${RUN_USER}" -g "${RUN_GROUP}" /etc/alloy /var/lib/alloy
# install -d does NOT re-own an existing dir — chown explicitly so a re-run that
# changes RUN_USER (e.g. from an earlier 'alloy' system user) can still write its
# state files under /var/lib/alloy. Without this, alloy fails to start.
sudo chown -R "${RUN_USER}:${RUN_GROUP}" /etc/alloy /var/lib/alloy
# the docker socket (container logs) is group 'docker' — make sure we can read it
if getent group docker >/dev/null 2>&1 && ! id -nG "${RUN_USER}" | tr ' ' '\n' | grep -qx docker; then
  echo "==> adding ${RUN_USER} to the docker group"
  sudo usermod -aG docker "${RUN_USER}"
  echo "    (a docker-group change needs a fresh login to take for interactive shells;"
  echo "     the alloy service picks it up on start regardless)"
fi
# No ACL / chmod / alloy-user dance: ${RUN_USER} owns its home and the worker's
# task-log files are world-readable, so it can already read them.

# ── config (resolve ${OBS_HOST}/${NODE_NAME}/${WORKER_LOGS_DIR}, leave the rest) ─
[ -d "${WORKER_LOGS_DIR}" ] || echo "WARN: ${WORKER_LOGS_DIR} not found yet — override WORKER_LOGS_DIR=... if the worker dir isn't ~/digitaltwins-compute (docker + host metrics still ship)." >&2
echo "==> Rendering /etc/alloy/config.alloy"
OBS_HOST="${OBS_HOST}" NODE_NAME="${NODE_NAME}" WORKER_LOGS_DIR="${WORKER_LOGS_DIR}" \
  envsubst '${OBS_HOST} ${NODE_NAME} ${WORKER_LOGS_DIR}' < "${OBS_DIR}/config.alloy.compute" \
  | sudo tee /etc/alloy/config.alloy >/dev/null
sudo chown "${RUN_USER}:${RUN_GROUP}" /etc/alloy/config.alloy

# ── systemd unit (run as the login user, not a system 'alloy' account) ──────
sudo cp "${OBS_DIR}/alloy.service" /etc/systemd/system/alloy.service
sudo sed -i "s/^User=.*/User=${RUN_USER}/; s/^Group=.*/Group=${RUN_GROUP}/" /etc/systemd/system/alloy.service
# guarantee docker-socket access even though we pin the primary group
grep -q '^SupplementaryGroups=' /etc/systemd/system/alloy.service \
  || sudo sed -i "/^Group=/a SupplementaryGroups=docker" /etc/systemd/system/alloy.service
sudo systemctl daemon-reload
sudo systemctl enable alloy
sudo systemctl restart alloy   # restart (not just --now) so a re-run reloads the config

echo
echo "==> alloy status:"
sudo systemctl --no-pager --full status alloy | head -n 12 || true
echo
echo "Done. Verify from the PORTAL's Grafana:"
echo "  logs:    Explore (Loki)  -> {node=\"${NODE_NAME}\"}   and  {job=\"airflow-task\"}"
echo "  metrics: Explore (Mimir) -> up{node=\"${NODE_NAME}\"}"
echo "If nothing shows: 'journalctl -u alloy -f' here, and confirm the portal opened"
echo "3100/9005 to this node (ufw + security group) and bound them to 0.0.0.0."
