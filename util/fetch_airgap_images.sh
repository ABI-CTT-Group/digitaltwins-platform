#!/usr/bin/env bash
# fetch_airgap_images.sh - Export all container images currently loaded in k3s
# Run AFTER the observability stack is fully deployed and all pods are Running.
# Output goes to ./airgap/images/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Must match fetch_airgap.sh's AIRGAP_DIR. On the box the deploy expects
# /mnt/install_src/airgap, so run: AIRGAP_DIR=/mnt/install_src/airgap ./fetch_airgap_images.sh
IMAGE_DIR="${AIRGAP_DIR:-${SCRIPT_DIR}/airgap}/images"
KUBECONFIG="${KUBECONFIG:-/etc/rancher/k3s/k3s.yaml}"

mkdir -p "${IMAGE_DIR}"

echo "==> Waiting for running pods to be ready (skipping Completed jobs)..."
sudo kubectl --kubeconfig="${KUBECONFIG}" wait pod \
    --all --all-namespaces \
    --for=condition=Ready \
    --timeout=300s \
    --field-selector='status.phase=Running' || true

echo ""
echo "==> Collecting image list from k3s containerd..."
IMAGES=$(sudo k3s ctr images list -q 2>/dev/null | grep -v '^sha256:' | sort -u)
IMAGE_COUNT=$(echo "${IMAGES}" | wc -l)
echo "    Found ${IMAGE_COUNT} images"
echo ""
echo "${IMAGES}"

echo ""
echo "==> Exporting all images into ONE archive..."
echo "    (single multi-image 'ctr export' — NOT a cat of separate tars. A"
echo "     concatenated bundle is the bug that bit us: 'ctr images import' stops"
echo "     at the first archive's EOF, so only ONE image ever imported and every"
echo "     app pod was ImagePullBackOff on an airgapped box. This may take several"
echo "     minutes for Mimir.)"
# ctr export accepts many refs and writes a single valid archive that imports whole.
mapfile -t IMAGE_ARR < <(printf '%s\n' "${IMAGES}")
sudo k3s ctr images export "${IMAGE_DIR}/k3s-images.tar" "${IMAGE_ARR[@]}"

echo ""
echo "==> Compressing..."
gzip -f "${IMAGE_DIR}/k3s-images.tar"

echo ""
echo "==> Writing image manifest..."
echo "${IMAGES}" > "${IMAGE_DIR}/image-list.txt"
echo "exported: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >> "${IMAGE_DIR}/image-list.txt"

echo ""
SIZE=$(du -sh "${IMAGE_DIR}/k3s-images.tar.gz" | cut -f1)
echo "================================================"
echo " Image bundle complete"
echo " ${IMAGE_DIR}/k3s-images.tar.gz  (${SIZE})"
echo " ${IMAGE_DIR}/image-list.txt"
echo "================================================"
echo ""
echo "Next: re-airgap the VM. On future deploys, the install playbook will"
echo "load images with:  k3s ctr images import airgap/images/k3s-images.tar.gz"
