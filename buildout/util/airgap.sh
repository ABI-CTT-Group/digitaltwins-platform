#!/usr/bin/env bash
# airgap.sh - Equivalent of airgap_build_step1.yml
# Configures UFW to simulate an airgapped environment.
# Run as root or with sudo.

#set -euo pipefail

echo "==> Installing UFW"
apt-get install -y ufw

echo "==> Configuring UFW rules"

# Inbound allows
ufw allow in  on lo
ufw allow in  proto tcp to any port 22
ufw allow in  proto tcp to any port 80
ufw allow in  proto tcp to any port 443

ufw allow from 10.2.0.0/24 to any port 8000
ufw allow from 10.2.0.0/24 to any port 8002
ufw allow from 10.2.0.0/24 to any port 8011
ufw allow from 10.2.0.0/24 to any port 8013
ufw allow from 10.2.0.0/24 to any port 8016


# k3s pod/service networks
ufw allow in  from 10.42.0.0/16
ufw allow in  from 10.43.0.0/16
ufw allow out to   10.42.0.0/16
ufw allow out to   10.43.0.0/16

# Allow forwarding (so portal can act as jump host)
ufw route allow in on eth0 out on eth1
ufw allow out to 10.2.0.0/24

# Loopback outgoing
ufw allow out on lo

# Default policies
ufw default deny incoming
ufw default deny outgoing

echo "==> Enabling UFW"
ufw --force enable

echo "==> Done. UFW status:"
ufw status verbose
