#!/usr/bin/env bash
# unairgap.sh - Restore outgoing internet access via UFW

set -euo pipefail

ufw default allow outgoing
ufw reload

echo "==> UFW outgoing policy set to allow — internet access restored"
