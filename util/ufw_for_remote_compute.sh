#!/usr/bin/env bash
# Open the platform ports a remote Airflow compute node needs — restricted to
# ONE source IP (the compute node's VLAN address). Run this ON THE PORTAL.
#
#   util/ufw_for_remote_compute.sh <compute_vlan_ip> [port ...]
#     e.g.  util/ufw_for_remote_compute.sh 10.2.0.42
#
# Default ports = the raw-TCP portal services the worker reaches directly (see
# util/compute-node-README.md):
#   8003 postgres · 8005 redis · 8011 minio (S3) · 8010 digitaltwins-api
# The Airflow execution API and Keycloak are reached over the gateway's 443
# (already public), so they need no rule here.
# Pass an explicit list to override the defaults.
set -euo pipefail

REMOTE_IP="${1:?usage: ufw_for_remote_compute.sh <compute_vlan_ip> [port ...]}"
shift
PORTS=("$@")
[ "${#PORTS[@]}" -eq 0 ] && PORTS=(8003 8005 8011 8010)

for p in "${PORTS[@]}"; do
  echo "ufw allow from $REMOTE_IP to any port $p"
  sudo ufw allow from "$REMOTE_IP" to any port "$p"
done

echo "done. rules for $REMOTE_IP:"
sudo ufw status | grep "$REMOTE_IP" || true
