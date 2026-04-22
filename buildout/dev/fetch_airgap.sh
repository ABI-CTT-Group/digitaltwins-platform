#!/usr/bin/env bash
# fetch_airgap.sh - Download everything needed for airgap deployment
# Run this on an internet-connected Linux (amd64) machine.
# Populates ./airgap/ relative to this script's directory.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AIRGAP_DIR="${SCRIPT_DIR}/airgap"
OBS_SRC="${SCRIPT_DIR}/observability"

BIN_DIR="${AIRGAP_DIR}/binaries"
CHART_DIR="${AIRGAP_DIR}/charts"
OBS_DIR="${AIRGAP_DIR}/observability"
PIP_DIR="${AIRGAP_DIR}/pip-wheels"
APT_DIR="${AIRGAP_DIR}/apt-debs"

echo "==> Creating airgap directory structure under ${AIRGAP_DIR}"
mkdir -p "${BIN_DIR}" "${CHART_DIR}" "${OBS_DIR}/dashboards" "${PIP_DIR}" "${APT_DIR}"

# ─── Detect latest GitHub release tag ────────────────────────────────────────
latest_release() {
    # $1 = owner/repo, returns tag name like "v1.2.3"
    curl -fsSL "https://api.github.com/repos/$1/releases/latest" \
        | grep '"tag_name"' | head -1 | sed 's/.*"tag_name": "\(.*\)".*/\1/'
}

# ─── k3s ─────────────────────────────────────────────────────────────────────
echo ""
echo "==> Fetching k3s"
K3S_TAG=$(latest_release "k3s-io/k3s")
echo "    version: ${K3S_TAG}"
curl -fsSL --progress-bar \
    "https://github.com/k3s-io/k3s/releases/download/${K3S_TAG}/k3s" \
    -o "${BIN_DIR}/k3s"
chmod +x "${BIN_DIR}/k3s"
# Save the install script too (used to register the k3s systemd service)
curl -fsSL "https://get.k3s.io" -o "${BIN_DIR}/k3s-install.sh"
chmod +x "${BIN_DIR}/k3s-install.sh"
echo "    k3s ${K3S_TAG} + install script saved"

# ─── k9s ─────────────────────────────────────────────────────────────────────
echo ""
echo "==> Fetching k9s"
K9S_TAG=$(latest_release "derailed/k9s")
echo "    version: ${K9S_TAG}"
curl -fsSL --progress-bar \
    "https://github.com/derailed/k9s/releases/download/${K9S_TAG}/k9s_Linux_amd64.tar.gz" \
    -o "${BIN_DIR}/k9s_Linux_amd64.tar.gz"
echo "    k9s ${K9S_TAG} saved"

# ─── Helm ─────────────────────────────────────────────────────────────────────
echo ""
echo "==> Fetching Helm (latest 3.x — kubernetes.core.helm requires <4.0.0)"
HELM_TAG=$(curl -fsSL "https://api.github.com/repos/helm/helm/releases" \
    | grep '"tag_name"' | grep '"v3\.' | head -1 \
    | sed 's/.*"tag_name": "\(.*\)".*/\1/')
echo "    version: ${HELM_TAG}"
curl -fsSL --progress-bar \
    "https://get.helm.sh/helm-${HELM_TAG}-linux-amd64.tar.gz" \
    -o "${BIN_DIR}/helm-linux-amd64.tar.gz"
echo "    helm ${HELM_TAG} saved"

# ─── Grafana Alloy ────────────────────────────────────────────────────────────
echo ""
echo "==> Fetching Grafana Alloy"
ALLOY_TAG=$(latest_release "grafana/alloy")
echo "    version: ${ALLOY_TAG}"
curl -fsSL --progress-bar \
    "https://github.com/grafana/alloy/releases/download/${ALLOY_TAG}/alloy-linux-amd64.zip" \
    -o "${BIN_DIR}/alloy-linux-amd64.zip"
echo "    alloy ${ALLOY_TAG} saved"

# ─── Helm charts (copy from existing observability/charts/) ──────────────────
echo ""
echo "==> Copying Helm charts"
for chart in "${OBS_SRC}/charts/"*.tgz; do
    cp -v "${chart}" "${CHART_DIR}/"
done

# ─── Observability config/values/dashboards ───────────────────────────────────
echo ""
echo "==> Copying observability config files"
cp -v "${OBS_SRC}/grafana-values.yaml"  "${OBS_DIR}/"
cp -v "${OBS_SRC}/loki-values.yaml"     "${OBS_DIR}/"
cp -v "${OBS_SRC}/mimir-values.yaml"    "${OBS_DIR}/"
cp -v "${OBS_SRC}/config.alloy"         "${OBS_DIR}/"
cp -v "${OBS_SRC}/alloy.service"        "${OBS_DIR}/"
cp -v "${OBS_SRC}/dashboards/"*.yaml    "${OBS_DIR}/dashboards/"

# ─── Python wheels ────────────────────────────────────────────────────────────
echo ""
echo "==> Downloading Python wheels (kubernetes, pyyaml)"
pip3 download kubernetes pyyaml --dest "${PIP_DIR}" --quiet
echo "    $(ls "${PIP_DIR}" | wc -l) wheel(s)/sdist(s) saved"

# ─── APT packages + local repo ────────────────────────────────────────────────
echo ""
echo "==> Downloading apt packages (python3-pip, unzip + ALL deps)"
APT_PKGS=(python3-pip python3-pip-whl python3-setuptools python3-setuptools-whl python3-wheel python3-yaml python3-venv python3.12-venv python3.12 unzip)

# Ensure dpkg-dev is available to build the repo index later
sudo apt-get install -y dpkg-dev 2>/dev/null || true

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

echo "    $(ls "${APT_DIR}" | wc -l) .deb(s) saved"

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
du -sh "${BIN_DIR}" "${CHART_DIR}" "${OBS_DIR}" "${PIP_DIR}" "${APT_DIR}"
echo ""
echo "Next step: bring up k3s + observability stack, then run"
echo "  fetch_airgap_images.sh  (to be written) to capture container images."
