#!/usr/bin/env bash
# fetch_airgap_images.sh - Export all container images currently loaded in k3s
# Run AFTER the observability stack is fully deployed and all pods are Running.
# Output goes to ./airgap/images/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_DIR="${SCRIPT_DIR}/airgap/images"
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
echo "==> Exporting images one at a time (skipping missing layers)..."
echo "    (This may take several minutes for Mimir...)"
EXPORTED=0
SKIPPED=0
TMPDIR=$(mktemp -d)
while IFS= read -r image; do
    SAFE=$(echo "${image}" | tr '/:' '__')
    if sudo k3s ctr images export "${TMPDIR}/${SAFE}.tar" "${image}" 2>/dev/null; then
        EXPORTED=$((EXPORTED + 1))
    else
        echo "    SKIP: ${image}"
        SKIPPED=$((SKIPPED + 1))
    fi
done <<< "${IMAGES}"

echo ""
echo "==> Combining ${EXPORTED} image tars (skipped ${SKIPPED})..."
cat "${TMPDIR}"/*.tar > "${IMAGE_DIR}/k3s-images.tar"
rm -rf "${TMPDIR}"

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
