#!/bin/bash
# ==============================================================================
# buildout.sh — provision the drai_cc VM and related resources
# Requires: OpenStack CLI (os), Terraform, AWS credentials for remote state
# ==============================================================================

set -euo pipefail

# ------------------------------------------------------------------------------
# 1. Create SSH keypair (skip if already exists)
# ------------------------------------------------------------------------------
if ! os keypair show drai-inn-keypair &>/dev/null; then
  echo "[INFO] Creating keypair drai-inn-keypair..."
  os keypair create drai-inn-keypair > drai-inn-keypair.key
  chmod 600 drai-inn-keypair.key

  export GCLOUD_PROJECT=mygen3
  gsecret save digital-twins-drai-inn-keypair file:drai-inn-keypair.key
else
  echo "[INFO] Keypair drai-inn-keypair already exists, skipping."
fi

# ------------------------------------------------------------------------------
# 2. Remote state credentials (NeSI RDC object store)
#    Container: terraform-states-carvin
#    Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY before running this script,
#    or uncomment and fill the lines below.
# ------------------------------------------------------------------------------
: "${AWS_ACCESS_KEY_ID:?ERROR: AWS_ACCESS_KEY_ID must be exported before running this script}"
: "${AWS_SECRET_ACCESS_KEY:?ERROR: AWS_SECRET_ACCESS_KEY must be exported before running this script}"

export AWS_ACCESS_KEY_ID
export AWS_SECRET_ACCESS_KEY

# ------------------------------------------------------------------------------
# 3. OpenStack provider auth
#    Relies on clouds.yaml + OS_CLOUD env var (set to 'openstack').
# ------------------------------------------------------------------------------
export OS_CLOUD="${OS_CLOUD:-openstack}"

# ------------------------------------------------------------------------------
# 4. Terraform workflow
# ------------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[INFO] Running terraform init (remote state: terraform-states-carvin)..."
terraform init -reconfigure

echo "[INFO] Running terraform plan..."
terraform plan -out=tfplan

echo "[INFO] Applying plan..."
terraform apply tfplan

echo "[INFO] Done."
