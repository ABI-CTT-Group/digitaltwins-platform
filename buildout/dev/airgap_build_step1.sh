#!/usr/bin/env bash
# airgap.sh - Equivalent of airgap_build_step1.yml
# Configures UFW to simulate an airgapped environment.
# Run as root or with sudo.

set -euo pipefail

echo "==> Configuring UFW rules"

# Inbound allows
ufw allow in  on lo
ufw allow in  proto tcp to any port 22
ufw allow in  proto tcp to any port 80
ufw allow in  proto tcp to any port 443

# k3s pod/service networks
ufw allow in  from 10.42.0.0/16
ufw allow in  from 10.43.0.0/16
ufw allow out to   10.42.0.0/16
ufw allow out to   10.43.0.0/16

# Loopback outgoing
ufw allow out on lo

# Default policies
ufw default deny incoming
ufw default deny outgoing

echo "==> Enabling UFW"
ufw --force enable

echo "==> Done. UFW status:"
ufw status verbose
