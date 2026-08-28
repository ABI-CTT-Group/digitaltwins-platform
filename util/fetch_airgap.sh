#!/usr/bin/env bash
# fetch_airgap.sh - Download everything needed for airgap deployment
# Run this on an internet-connected Linux (amd64) machine.
# Populates ./airgap/ relative to this script's directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Where the bundle's airgap/ payload is written. Defaults next to this script, but
# the deploy expects it at /mnt/install_src/airgap — so when building on the box:
#   AIRGAP_DIR=/mnt/install_src/airgap ./fetch_airgap.sh
AIRGAP_DIR="${AIRGAP_DIR:-${SCRIPT_DIR}/airgap}"

# The bundle holds ONLY what is not in the repo and needs the internet to obtain.
# The observability values, config.alloy, dashboards and Helm charts are NOT copied
# here — the playbook reads them straight from the git checkout (observability_dir =
# playbook_dir/observability). One source of truth, nothing to drift.
BIN_DIR="${AIRGAP_DIR}/binaries"
PIP_DIR="${AIRGAP_DIR}/pip-wheels"
APT_DIR="${AIRGAP_DIR}/apt-debs"

echo "==> Creating airgap directory structure under ${AIRGAP_DIR}"
mkdir -p "${BIN_DIR}" "${PIP_DIR}" "${APT_DIR}"

# ─── Pinned tool versions ────────────────────────────────────────────────────
# Pinned so every bundle build produces the IDENTICAL tool set (the Helm charts are
# already pinned as committed .tgz). Bump deliberately, or override per-run via env:
#   K3S_VERSION=v1.36.0+k3s1 ./fetch_airgap.sh
# k3s binary and its airgap-images tarball share K3S_TAG so they always match.
K3S_TAG="${K3S_VERSION:-v1.35.3+k3s1}"
K9S_TAG="${K9S_VERSION:-v0.50.18}"
HELM_TAG="${HELM_VERSION:-v3.20.2}"          # get.helm.sh wants the bare vX.Y.Z (no +g… git suffix)
ALLOY_TAG="${ALLOY_VERSION:-v1.15.1}"

# ─── k3s ─────────────────────────────────────────────────────────────────────
echo ""
echo "==> Fetching k3s ${K3S_TAG}"
curl -fsSL --progress-bar \
    "https://github.com/k3s-io/k3s/releases/download/${K3S_TAG}/k3s" \
    -o "${BIN_DIR}/k3s"
chmod +x "${BIN_DIR}/k3s"
# k3s system-images tarball (pause / coredns / traefik / metrics-server /
# local-path-provisioner). The playbook drops this into
# /var/lib/rancher/k3s/agent/images so k3s brings up its own pods with NO registry
# access — without it an airgapped k3s never starts. Must match the k3s binary tag.
curl -fsSL --progress-bar \
    "https://github.com/k3s-io/k3s/releases/download/${K3S_TAG}/k3s-airgap-images-amd64.tar.gz" \
    -o "${BIN_DIR}/k3s-airgap-images-amd64.tar.gz"
# Save the install script too (used to register the k3s systemd service)
curl -fsSL "https://get.k3s.io" -o "${BIN_DIR}/k3s-install.sh"
chmod +x "${BIN_DIR}/k3s-install.sh"
echo "    k3s ${K3S_TAG} + install script saved"

# ─── k9s ─────────────────────────────────────────────────────────────────────
echo ""
echo "==> Fetching k9s ${K9S_TAG}"
curl -fsSL --progress-bar \
    "https://github.com/derailed/k9s/releases/download/${K9S_TAG}/k9s_Linux_amd64.tar.gz" \
    -o "${BIN_DIR}/k9s_Linux_amd64.tar.gz"
echo "    k9s ${K9S_TAG} saved"

# ─── Helm ─────────────────────────────────────────────────────────────────────
echo ""
echo "==> Fetching Helm ${HELM_TAG} (kubernetes.core.helm requires 3.x, <4.0.0)"
curl -fsSL --progress-bar \
    "https://get.helm.sh/helm-${HELM_TAG}-linux-amd64.tar.gz" \
    -o "${BIN_DIR}/helm-linux-amd64.tar.gz"
echo "    helm ${HELM_TAG} saved"

# ─── Grafana Alloy ────────────────────────────────────────────────────────────
echo ""
echo "==> Fetching Grafana Alloy ${ALLOY_TAG}"
curl -fsSL --progress-bar \
    "https://github.com/grafana/alloy/releases/download/${ALLOY_TAG}/alloy-linux-amd64.zip" \
    -o "${BIN_DIR}/alloy-linux-amd64.zip"
echo "    alloy ${ALLOY_TAG} saved"

# ─── Helm charts + observability configs/dashboards ──────────────────────────
# NOT bundled — the playbook reads charts, *-values.yaml, config.alloy and the
# dashboard ConfigMaps straight from the git checkout (observability_dir). Keeping
# them out of the bundle is what makes the checkout the single source of truth.

# ─── Python wheels ────────────────────────────────────────────────────────────
echo ""
echo "==> Downloading Python wheels (kubernetes client + full dependency closure)"
# Keep the FULL closure — the observability playbook installs it into a
# --system-site-packages venv, so newer wheels never clash with apt-managed system
# packages, and a complete closure makes that venv install self-contained.
pip3 download kubernetes --dest "${PIP_DIR}" --quiet
echo "    $(ls "${PIP_DIR}" | wc -l) wheel(s)/sdist(s) saved"

# ─── APT packages + local repo ────────────────────────────────────────────────
echo ""
echo "==> Downloading apt packages (python3-pip, unzip + ALL deps)"
APT_PKGS=(python3-pip python3-pip-whl python3-setuptools python3-setuptools-whl python3-wheel python3-yaml python3-venv python3.12-venv python3.12 unzip)

# Ensure dpkg-dev (provides dpkg-scanpackages, used to build the repo index below)
# is present. THIS STEP NEEDS WORKING INTERNET APT. If the observability install has
# already run on this box it disabled the real Ubuntu apt sources (moved them to
# *.bak, added a local-airgap repo) and this will fail — restore them first.
sudo apt-get update
if ! command -v dpkg-scanpackages >/dev/null 2>&1; then
    sudo apt-get install -y dpkg-dev || {
        echo "FATAL: cannot install dpkg-dev (dpkg-scanpackages) — apt can't reach the" >&2
        echo "       Ubuntu archive. If the observability install has run on this box," >&2
        echo "       restore the real apt sources and drop the local-airgap repo:" >&2
        echo "         sudo mv /etc/apt/sources.list.d/ubuntu.sources{.bak,} 2>/dev/null" >&2
        echo "         sudo rm -f /etc/apt/sources.list.d/local-airgap.list && sudo apt-get update" >&2
        exit 1
    }
fi

# Download the target packages + all their dependencies into the apt cache.
# We use a temp dir so we get a clean set without unrelated cached debs.
TMP_APT=$(mktemp -d)
sudo apt-get install -y --download-only --no-install-recommends \
    -o Dir::Cache::archives="${TMP_APT}" \
    "${APT_PKGS[@]}" 2>/dev/null || true
# --reinstall catches packages already installed (apt skips them otherwise)
sudo apt-get install -y --download-only --reinstall --no-install-recommends \
    -o Dir::Cache::archives="${TMP_APT}" \
    "${APT_PKGS[@]}" 2>/dev/null || true

sudo find "${TMP_APT}" -maxdepth 1 -name "*.deb" -exec cp -v {} "${APT_DIR}/" \;
sudo rm -rf "${TMP_APT}"

_deb_count=$(ls "${APT_DIR}"/*.deb 2>/dev/null | wc -l)
echo "    ${_deb_count} .deb(s) saved"
if [ "${_deb_count}" -eq 0 ]; then
    echo "FATAL: no .deb packages downloaded — apt could not reach the Ubuntu archive." >&2
    echo "       Restore the real apt sources (see above) and re-run." >&2
    exit 1
fi

# Build a local apt repository index so the airgapped machine can use apt normally
echo ""
echo "==> Building local apt repository index"
( cd "${APT_DIR}" && dpkg-scanpackages . > Packages && gzip -k -f Packages )
echo "    Repository index written to ${APT_DIR}/Packages.gz"

# ─── Record versions ─────────────────────────────────────────────────────────
echo ""
echo "==> Writing versions manifest"
cat > "${AIRGAP_DIR}/versions.txt" <<EOF
k3s:   ${K3S_TAG}
k9s:   ${K9S_TAG}
helm:  ${HELM_TAG}
alloy: ${ALLOY_TAG}
fetched: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
EOF

# ─── Summary ─────────────────────────────────────────────────────────────────
echo ""
echo "================================================"
echo " Airgap bundle complete: ${AIRGAP_DIR}"
echo "================================================"
cat "${AIRGAP_DIR}/versions.txt"
echo ""
echo "Directory sizes:"
du -sh "${BIN_DIR}" "${PIP_DIR}" "${APT_DIR}"
echo ""
echo "Next: deploy the observability stack, then — WHILE k3s is still running —"
echo "capture its container images so an airgapped rebuild has them:"
echo "  AIRGAP_DIR=${AIRGAP_DIR} KUBECONFIG=/etc/rancher/k3s/k3s.yaml ./fetch_airgap_images.sh"
echo "(this must be done before the box/VM is destroyed — the images live in the running k3s)."
