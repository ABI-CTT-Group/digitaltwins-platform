#!/usr/bin/env bash
# Install Grafana Alloy on a REMOTE COMPUTE NODE so it ships this box's docker
# logs, Airflow task logs and host metrics to the observability stack on the
# portal (Loki :3100 / Mimir :9005 over the VLAN).
#
# Run this ON THE COMPUTE NODE (e.g. drai-compute), as a sudo-capable user.
# It's airgap-friendly: the alloy binary comes from the install bundle, same as
# every other compute-node component — no internet needed.
#
#   util/install-compute-alloy.sh <portal_vlan_ip> [install_src_dir]
#     e.g.  util/install-compute-alloy.sh 10.2.0.195
#           util/install-compute-alloy.sh 10.2.0.195 /mnt/install_src/airgap
#
# Prereqs (see util/compute-node-README.md §G):
#   - On the PORTAL: Loki/Mimir port-forward bound to 0.0.0.0 (re-run the
#     observability playbook after pulling this branch) AND
#     `util/ufw_for_remote_compute.sh <this_node_ip> 3100 9005` + the same two
#     ports opened to this node in the cloud security group.
#   - This repo checked out here (for config.alloy.compute + alloy.service), and
#     the bundle's binaries/alloy-linux-amd64.zip present.
set -euo pipefail

OBS_HOST="${1:?usage: install-compute-alloy.sh <portal_vlan_ip> [install_src_dir]}"
INSTALL_SRC="${2:-/mnt/install_src/airgap}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OBS_DIR="${SCRIPT_DIR}/observability"
ALLOY_ZIP="${INSTALL_SRC}/binaries/alloy-linux-amd64.zip"
NODE_NAME="$(hostname)"

echo "==> Installing Alloy on '${NODE_NAME}', shipping to portal ${OBS_HOST} (Loki :3100 / Mimir :9005)"

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

# ── alloy user, dirs, docker access ─────────────────────────────────────────
id alloy >/dev/null 2>&1 || sudo useradd --system --no-create-home --shell /usr/sbin/nologin alloy
sudo install -d -o alloy -g alloy /etc/alloy /var/lib/alloy
# read the docker socket (container logs) and the bind-mounted airflow logs
getent group docker >/dev/null 2>&1 && sudo usermod -aG docker alloy || true

# ── config (resolve ${OBS_HOST} + ${NODE_NAME}, leave all other syntax intact) ─
echo "==> Rendering /etc/alloy/config.alloy"
OBS_HOST="${OBS_HOST}" NODE_NAME="${NODE_NAME}" \
  envsubst '${OBS_HOST} ${NODE_NAME}' < "${OBS_DIR}/config.alloy.compute" \
  | sudo tee /etc/alloy/config.alloy >/dev/null
sudo chown alloy:alloy /etc/alloy/config.alloy

# ── systemd unit ────────────────────────────────────────────────────────────
sudo cp "${OBS_DIR}/alloy.service" /etc/systemd/system/alloy.service
sudo systemctl daemon-reload
sudo systemctl enable --now alloy

echo
echo "==> alloy status:"
sudo systemctl --no-pager --full status alloy | head -n 12 || true
echo
echo "Done. Verify from the PORTAL that logs/metrics are arriving:"
echo "  logs:    Grafana Explore (Loki) -> {node=\"${NODE_NAME}\"}"
echo "  metrics: Grafana Explore (Mimir) -> up{node=\"${NODE_NAME}\"}"
echo "If nothing shows: check 'journalctl -u alloy -f' here, and that the portal"
echo "opened 3100/9005 to this node (ufw + security group) and bound them to 0.0.0.0."
