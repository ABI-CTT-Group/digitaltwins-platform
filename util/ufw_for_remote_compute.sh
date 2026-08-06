#!/usr/bin/env bash
# Open the platform ports a remote Airflow compute node needs — restricted to
# ONE source IP (the compute node's VLAN address). Run this ON THE PORTAL.
#
#   util/ufw_for_remote_compute.sh <compute_vlan_ip> [port ...]
#     e.g.  util/ufw_for_remote_compute.sh 10.2.0.42
#
# Default ports = the portal services the worker reaches directly over the VLAN
# (see util/compute-node-README.md):
#   8003 postgres · 8005 redis · 8002 airflow execution API · 8011 minio (S3) ·
#   8010 digitaltwins-api
# Only Keycloak is reached over the gateway's already-public 443, so it needs no
# rule here.
# NOTE: on OpenStack/cloud the SECURITY GROUP is a separate firewall layer below
# ufw — these ports (8002 especially) may also need opening there, RESTRICTED to
# this node's private IP (never 0.0.0.0/0).
# Pass an explicit list to override the defaults.
set -euo pipefail

REMOTE_IP="${1:?usage: ufw_for_remote_compute.sh <compute_vlan_ip> [port ...]}"
shift
PORTS=("$@")
[ "${#PORTS[@]}" -eq 0 ] && PORTS=(8003 8005 8002 8011 8010)

for p in "${PORTS[@]}"; do
  echo "ufw allow from $REMOTE_IP to any port $p"
  sudo ufw allow from "$REMOTE_IP" to any port "$p"
done

echo "done. rules for $REMOTE_IP:"
sudo ufw status | grep "$REMOTE_IP" || true
