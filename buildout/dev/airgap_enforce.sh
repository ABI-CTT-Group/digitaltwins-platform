#!/usr/bin/env bash
# Restore outgoing internet access via UFW

set -euo pipefail

ufw default deny outgoing
ufw reload

echo "==> UFW outgoing policy set to allow — internet access restored"
