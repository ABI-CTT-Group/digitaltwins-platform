#!/bin/bash
# ==============================================================================
# deploy_observability.sh
# Mirrors: build_observability_full.yaml
# Deploys: k3s, k9s, helm, grafana, loki, mimir, alloy + port-forwarding
# Run this script directly on each target host (portal, drai_mp, drai_cc).
# ==============================================================================

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OBSERVABILITY_DIR="${OBSERVABILITY_DIR:-$SCRIPT_DIR/observability}"
KUBECONFIG_PATH=/etc/rancher/k3s/k3s.yaml
CURRENT_USER="${USER:-$(whoami)}"

# --- Colours ------------------------------------------------------------------
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC}  $*"; }
err()  { echo -e "${RED}[ERROR]${NC} $*"; }

# --- Status tracking (mirrors ansible summary report) -------------------------
K3S_STATUS="SKIPPED"
GRAFANA_STATUS="FAILED/SKIPPED"
LOKI_STATUS="FAILED/SKIPPED"
MIMIR_STATUS="FAILED/SKIPPED"
ALLOY_STATUS="FAILED/SKIPPED"

# ==============================================================================
# 1. Verify required environment variables
# ==============================================================================
log "Verifying required environment variables..."
if [[ -z "${GRAFANA_ADMIN_PASSWORD:-}" ]]; then
  err "FATAL: The required environment variable GRAFANA_ADMIN_PASSWORD must be set."
  exit 1
fi

log "Current remote work directory: $(pwd)"
log "Observability source directory: $OBSERVABILITY_DIR"

# ==============================================================================
# 2. Install python3-pip and Python kubernetes client
# ==============================================================================
log "Installing python3-pip..."
sudo apt-get update -qq
sudo apt-get install -y python3-pip

log "Installing Python kubernetes + pyyaml..."
sudo pip3 install kubernetes pyyaml

# ==============================================================================
# 3. Install Docker
# ==============================================================================
log "Checking for Docker..."
if ! command -v docker &>/dev/null; then
  log "Installing Docker (official repo)..."
  sudo apt-get install -y ca-certificates curl gnupg lsb-release

  sudo install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
  sudo chmod a+r /etc/apt/keyrings/docker.gpg

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu \
$(lsb_release -cs) stable" \
    | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

  sudo apt-get update -qq
  sudo apt-get install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

  sudo systemctl enable docker
  sudo systemctl start  docker

  log "Adding ${CURRENT_USER} to docker group..."
  sudo usermod -aG docker "${CURRENT_USER}"
  warn "Docker group membership takes effect on next login / use 'newgrp docker'"
else
  log "Docker already installed, skipping."
fi

# ==============================================================================
# 4. Install k3s
# ==============================================================================
log "Checking for k3s..."
if [[ ! -f /usr/local/bin/k3s ]]; then
  log "Downloading k3s installation script..."
  if curl -fsSL https://get.k3s.io -o /tmp/k3s-install.sh; then
    chmod +x /tmp/k3s-install.sh
    log "Installing k3s..."
    if sudo sh /tmp/k3s-install.sh; then
      K3S_STATUS="SUCCESS"
      log "Waiting for k3s API server on port 6443 (up to 5 min)..."
      for i in $(seq 1 60); do
        if nc -z localhost 6443 2>/dev/null; then
          log "k3s API server is ready."
          break
        fi
        sleep 5
      done
    else
      warn "k3s installation failed"
    fi
  else
    warn "Failed to download k3s install script"
  fi
else
  log "k3s already installed, skipping."
  K3S_STATUS="SKIPPED (already installed)"
fi

log "Ensuring k3s service is running..."
sudo systemctl enable k3s 2>/dev/null || true
sudo systemctl start  k3s 2>/dev/null || true

# ==============================================================================
# 5. Install k9s
# ==============================================================================
log "Checking for k9s..."
if [[ ! -f /usr/local/bin/k9s ]]; then
  log "Downloading k9s..."
  if curl -fsSL "https://github.com/derailed/k9s/releases/latest/download/k9s_Linux_amd64.tar.gz" \
       -o /tmp/k9s.tar.gz; then
    sudo tar -xzf /tmp/k9s.tar.gz -C /usr/local/bin k9s || warn "Failed to extract k9s"
  else
    warn "Failed to download k9s"
  fi
fi
sudo chmod 0755 /usr/local/bin/k9s 2>/dev/null || true
log "k9s ready."

# ==============================================================================
# 6. Install Helm
# ==============================================================================
log "Checking for helm..."
if [[ ! -f /usr/local/bin/helm ]]; then
  log "Downloading helm installation script..."
  if curl -fsSL https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 \
       -o /tmp/get-helm-3.sh; then
    chmod +x /tmp/get-helm-3.sh
    sudo bash /tmp/get-helm-3.sh || warn "Helm installation failed"
  else
    warn "Failed to download helm install script"
  fi
else
  log "Helm already installed, skipping."
fi

# ==============================================================================
# 7. Configure firewalld for k3s
# ==============================================================================
log "Configuring firewalld for k3s..."
for cidr in 10.42.0.0/16 10.43.0.0/16; do
  sudo firewall-cmd --zone=trusted --add-source="$cidr" --permanent 2>/dev/null || true
done
for iface in cni0 flannel.1; do
  sudo firewall-cmd --zone=trusted --add-interface="$iface" --permanent 2>/dev/null || true
done
sudo firewall-cmd --add-masquerade --permanent 2>/dev/null || true
sudo systemctl reload firewalld 2>/dev/null || true

# ==============================================================================
# 8. Copy observability files to /tmp/observability
# ==============================================================================
log "Copying observability files to /tmp/observability..."
sudo mkdir -p /tmp/observability
sudo chmod 0755 /tmp/observability

FILES=(
  "$OBSERVABILITY_DIR/grafana-values.yaml"
  "$OBSERVABILITY_DIR/loki-values.yaml"
  "$OBSERVABILITY_DIR/mimir-values.yaml"
  "$OBSERVABILITY_DIR/charts/grafana-10.5.4.tgz"
  "$OBSERVABILITY_DIR/charts/loki-6.49.0.tgz"
  "$OBSERVABILITY_DIR/charts/mimir-distributed-6.1.0-weekly.378.tgz"
  "$OBSERVABILITY_DIR/dashboards/cm-log-dashboards.yaml"
  "$OBSERVABILITY_DIR/dashboards/cm-metric-dashboards.yaml"
)
for f in "${FILES[@]}"; do
  sudo cp "$f" /tmp/observability/ || warn "Failed to copy: $f"
done

# ==============================================================================
# 9. Set KUBECONFIG in ~/.bashrc
# ==============================================================================
log "Setting KUBECONFIG in ~/.bashrc..."
if ! grep -q 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml' ~/.bashrc 2>/dev/null; then
  echo 'export KUBECONFIG=/etc/rancher/k3s/k3s.yaml' | sudo tee -a ~/.bashrc > /dev/null
fi
export KUBECONFIG="$KUBECONFIG_PATH"

# ==============================================================================
# 10. Add Grafana helm repo and update
# ==============================================================================
log "Adding Grafana helm repo..."
helm repo add grafana https://grafana.github.io/helm-charts 2>/dev/null || true
helm repo update || true

# ==============================================================================
# 11. Deploy Grafana
# ==============================================================================
log "Creating grafana namespace..."
kubectl create namespace grafana --dry-run=client -o yaml | kubectl apply -f - || true

log "Applying Grafana dashboard ConfigMaps..."
for cm in /tmp/observability/cm-log-dashboards.yaml /tmp/observability/cm-metric-dashboards.yaml; do
  kubectl apply -f "$cm" -n grafana || warn "Failed to apply $cm"
done

log "Deploying Grafana..."
if helm upgrade --install grafana /tmp/observability/grafana-10.5.4.tgz \
  --namespace grafana \
  --values /tmp/observability/grafana-values.yaml \
  --set adminUser=admin \
  --set adminPassword="${GRAFANA_ADMIN_PASSWORD}"; then
  GRAFANA_STATUS="SUCCESS"
else
  warn "Grafana deployment failed"
fi

# ==============================================================================
# 12. Deploy Loki
# ==============================================================================
log "Creating loki namespace..."
kubectl create namespace loki --dry-run=client -o yaml | kubectl apply -f - || true

log "Deploying Loki..."
if helm upgrade --install loki /tmp/observability/loki-6.49.0.tgz \
  --namespace loki \
  --values /tmp/observability/loki-values.yaml; then
  LOKI_STATUS="SUCCESS"
else
  warn "Loki deployment failed"
fi

# ==============================================================================
# 13. Deploy Mimir
# ==============================================================================
log "Creating mimir namespace..."
kubectl create namespace mimir --dry-run=client -o yaml | kubectl apply -f - || true

log "Deploying Mimir..."
if helm upgrade --install mimir /tmp/observability/mimir-distributed-6.1.0-weekly.378.tgz \
  --namespace mimir \
  --values /tmp/observability/mimir-values.yaml; then
  MIMIR_STATUS="SUCCESS"
else
  warn "Mimir deployment failed"
fi

# ==============================================================================
# 14. Install Grafana Alloy
# ==============================================================================
log "Checking for alloy..."
if [[ ! -f /usr/local/bin/alloy ]]; then
  log "Downloading and installing alloy..."
  if curl -fsSL \
    "https://github.com/grafana/alloy/releases/latest/download/alloy-linux-amd64.zip" \
    | funzip > /tmp/alloy; then
    sudo mv /tmp/alloy /usr/local/bin/alloy
    sudo chmod +x /usr/local/bin/alloy
  else
    warn "Alloy download/install failed"
  fi
fi

log "Creating alloy system user..."
sudo useradd --system --no-create-home --shell /usr/sbin/nologin alloy 2>/dev/null || true

log "Creating alloy config and data directories..."
sudo mkdir -p /etc/alloy /var/lib/alloy
sudo chown alloy:alloy /etc/alloy /var/lib/alloy
sudo chmod 0755 /etc/alloy /var/lib/alloy

log "Copying alloy config..."
sudo cp "$OBSERVABILITY_DIR/config.alloy" /etc/alloy/config.alloy || warn "Failed to copy alloy config"
sudo chown alloy:alloy /etc/alloy/config.alloy
sudo chmod 0644 /etc/alloy/config.alloy

log "Copying alloy systemd service file..."
sudo cp "$OBSERVABILITY_DIR/alloy.service" /etc/systemd/system/alloy.service || warn "Failed to copy alloy.service"
sudo chmod 0644 /etc/systemd/system/alloy.service

log "Adding alloy user to docker group..."
sudo usermod -aG docker alloy 2>/dev/null || true

log "Reloading systemd and starting alloy..."
sudo systemctl daemon-reload
if sudo systemctl enable alloy && sudo systemctl start alloy; then
  ALLOY_STATUS="SUCCESS"
else
  warn "Alloy service start failed"
fi

# ==============================================================================
# 15. Port forwarding script + systemd service
# ==============================================================================
log "Creating port-forward script..."
sudo tee /usr/local/bin/k3s-port-forward.sh > /dev/null << 'PFEOF'
#!/bin/bash
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml

# Kill existing port-forward processes
pkill -f "kubectl.*port-forward" || true

# Start port forwarding
nohup kubectl -n loki        port-forward svc/loki-gateway    3100:80   > /var/log/loki-port-forward.log    2>&1 &
nohup kubectl -n mimir       port-forward svc/mimir-gateway   9005:8080 > /var/log/mimir-port-forward.log   2>&1 &
nohup kubectl -n kube-system port-forward svc/metrics-server  8443:443  > /var/log/metrics-port-forward.log 2>&1 &
PFEOF
sudo chmod 0755 /usr/local/bin/k3s-port-forward.sh

log "Executing port-forward script..."
/usr/local/bin/k3s-port-forward.sh || true

log "Creating k3s-port-forward systemd service..."
sudo tee /etc/systemd/system/k3s-port-forward.service > /dev/null << 'SVCEOF'
[Unit]
Description=K3s Port Forward Service
After=k3s.service
Requires=k3s.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/k3s-port-forward.sh
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
SVCEOF

sudo systemctl daemon-reload
sudo systemctl enable k3s-port-forward 2>/dev/null || true

# ==============================================================================
# 16. Setup ~/.kube/config for current user
# ==============================================================================
log "Setting up kubeconfig for user ${CURRENT_USER}..."
mkdir -p "/home/${CURRENT_USER}/.kube"
sudo cp "$KUBECONFIG_PATH" "/home/${CURRENT_USER}/.kube/config"
sudo chown "${CURRENT_USER}:${CURRENT_USER}" "/home/${CURRENT_USER}/.kube/config"
sudo chmod 0600 "/home/${CURRENT_USER}/.kube/config"

log "Setting KUBECONFIG in .bash_aliases..."
BASH_ALIASES="./.bash_aliases"
if grep -q '^export KUBECONFIG=' "$BASH_ALIASES" 2>/dev/null; then
  sed -i 's|^export KUBECONFIG=.*|export KUBECONFIG=~/.kube/config|' "$BASH_ALIASES"
else
  echo 'export KUBECONFIG=~/.kube/config' >> "$BASH_ALIASES"
fi
chmod 0600 "$BASH_ALIASES" 2>/dev/null || true

# ==============================================================================
# 17. Patch Traefik ports (HTTP -> 81, HTTPS -> 7443) and restart
# ==============================================================================
log "Patching Traefik HTTP port to 81..."
kubectl patch svc traefik -n kube-system --type="json" \
  -p='[{"op": "replace", "path": "/spec/ports/0/port", "value":81}]' \
  || warn "Traefik HTTP port patch failed"

log "Patching Traefik HTTPS port to 7443..."
kubectl patch svc traefik -n kube-system --type="json" \
  -p='[{"op": "replace", "path": "/spec/ports/1/port", "value":7443}]' \
  || warn "Traefik HTTPS port patch failed"

log "Restarting Traefik deployment..."
kubectl rollout restart deployment traefik -n kube-system || warn "Traefik restart failed"

# ==============================================================================
# 18. Docker Compose down / up
# ==============================================================================
log "Running docker compose down in ./digitaltwins-platform..."
(cd ./digitaltwins-platform && docker compose down) || warn "docker compose down failed"

log "Running docker compose up -d in ./digitaltwins-platform..."
(cd ./digitaltwins-platform && docker compose up -d) || warn "docker compose up failed"

# ==============================================================================
# 19. Cleanup temporary files
# ==============================================================================
log "Cleaning up temporary files..."
rm -f /tmp/k3s-install.sh /tmp/get-helm-3.sh 2>/dev/null || true
sudo rm -rf /tmp/observability 2>/dev/null || true

# ==============================================================================
# Summary report
# ==============================================================================
echo ""
echo "=========================================="
echo " Deployment Summary"
echo "=========================================="
echo " K3s Installation : ${K3S_STATUS}"
echo " Grafana          : ${GRAFANA_STATUS}"
echo " Loki             : ${LOKI_STATUS}"
echo " Mimir            : ${MIMIR_STATUS}"
echo " Alloy            : ${ALLOY_STATUS}"
echo "=========================================="
echo " Port forwards:"
echo "   Loki           -> localhost:3100"
echo "   Mimir          -> localhost:9005"
echo "   Metrics-server -> localhost:8443"
echo " Use 'k9s' to manage your cluster"
echo " Review /var/log/*-port-forward.log for port-forward status"
echo "=========================================="
