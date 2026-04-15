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
GRAFANA_TLS_STATUS="FAILED/SKIPPED"
LOKI_STATUS="FAILED/SKIPPED"
MIMIR_STATUS="FAILED/SKIPPED"
ALLOY_STATUS="FAILED/SKIPPED"
DOCKER_COMPOSE_STATUS="SKIPPED"

# --- Resolve public IP once at startup ----------------------------------------
# Used for TLS cert SANs, Grafana root_url, and the summary report.
HOST_IP=$(curl -s --max-time 5 ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')
log "Detected host IP: ${HOST_IP}"

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
log "Installing python3-pip and python3-yaml via apt..."
sudo apt-get update -qq
sudo apt-get install -y python3-pip python3-yaml

log "Installing Python kubernetes client..."
# --break-system-packages is required on Python 3.12+ (PEP 668) for system-wide installs
sudo pip3 install --break-system-packages kubernetes

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
else
  log "Docker already installed, skipping."
fi

# Always ensure current user is in the docker group (idempotent).
# Then activate the new group membership for this shell session immediately
# so subsequent docker commands in this script don't require re-login.
log "Ensuring ${CURRENT_USER} is in the docker group..."
sudo usermod -aG docker "${CURRENT_USER}"
if ! id -nG "${CURRENT_USER}" | grep -qw docker; then
  warn "Could not verify docker group membership for ${CURRENT_USER}"
fi
# Re-exec this script under the docker group so the rest of the session
# inherits the membership — only triggers on the first run (no DOCKER_GROUP_ACTIVE set).
if [[ -z "${DOCKER_GROUP_ACTIVE:-}" ]]; then
  log "Activating docker group for current session (re-exec via sg)..."
  export DOCKER_GROUP_ACTIVE=1
  exec sg docker -c "bash \"$0\" $(printf '%q ' "$@")"
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

# k3s.yaml is root:root 600 by default.
# Wait for k3s to write it (it may take a few seconds after systemctl start).
log "Waiting for /etc/rancher/k3s/k3s.yaml to appear..."
for i in $(seq 1 30); do
  sudo test -f /etc/rancher/k3s/k3s.yaml && break
  sleep 2
done
if ! sudo test -f /etc/rancher/k3s/k3s.yaml; then
  err "k3s.yaml never appeared — k3s may not have started correctly. Aborting."
  exit 1
fi
# Make it group-readable so kubectl/helm can fall back to it even without a copy.
sudo chmod 644 /etc/rancher/k3s/k3s.yaml
# Also copy to ~/.kube/config as the canonical location for this user.
log "Setting up kubeconfig for ${CURRENT_USER}..."
mkdir -p "${HOME}/.kube"
sudo cp /etc/rancher/k3s/k3s.yaml "${HOME}/.kube/config"
sudo chown "${CURRENT_USER}:${CURRENT_USER}" "${HOME}/.kube/config"
chmod 600 "${HOME}/.kube/config"
export KUBECONFIG="${HOME}/.kube/config"

# Step 7 (firewalld) resets everything and applies all rules in one pass,
# including the --add-interface rules that need flannel.1/cni0 to exist.
# Those interfaces are now up (k3s just started), so no early reload needed here.

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
# 7. Configure firewalld — permanent rules (reload happens after k3s starts)
# ==============================================================================
# Ensure firewalld is running before we configure it
sudo systemctl enable firewalld
sudo systemctl start  firewalld

# ---- Reset to factory defaults -----------------------------------------------
# Wipe all custom permanent zone files and direct rules so the resulting state
# is 100% defined by this script — no residue from manual changes or prior runs.
log "Resetting firewalld to factory defaults..."
sudo rm -f /etc/firewalld/zones/public.xml
sudo rm -f /etc/firewalld/zones/trusted.xml
sudo rm -f /etc/firewalld/direct.xml
sudo firewall-cmd --complete-reload   # load the clean defaults from /usr/lib/firewalld/zones/
log "Firewalld reset complete."

log "Configuring firewalld — external platform ports..."
# ---- External-facing ports (opened in the public/default zone) ---------------
# These are the ports that must be reachable from outside the VM.
EXTERNAL_PORTS=(
  "80/tcp"      # HTTP  — nginx reverse proxy / platform web
  "443/tcp"     # HTTPS — nginx reverse proxy / platform web
  "8001/tcp"    # SEEK  — data platform
  "8002/tcp"    # Airflow API/webserver
  "8003/tcp"    # Postgres (docker container, mapped from 5432)
  "8004/tcp"    # Pgadmin (docker container, mapped from 80)
  "8008/tcp"    # JupiterLab (docker container, mapped from 8888)
  "8009/tcp"    # Keycloak HTTPS (docker container, mapped from 8443)
  "8010/tcp"    # Restt and API (docker container, mapped from 9005)
  "8012/tcp"    # Minio console (docker container, mapped from 9000)
  "30333/tcp"   # Grafana NodePort (k3s NodePort range 30000-32767)
)
for port in "${EXTERNAL_PORTS[@]}"; do
  sudo firewall-cmd --zone=public --add-port="$port" --permanent 2>/dev/null || true
  log "  opened public port $port"
done

log "Configuring firewalld — k3s pod/service CIDRs (trusted zone)..."
# ---- Trust k3s pod and service CIDRs -----------------------------------------
# Traffic from/to 10.42.0.0/16 (pods) and 10.43.0.0/16 (services) must be
# unrestricted so pods can talk to each other and to the host.
for cidr in 10.42.0.0/16 10.43.0.0/16; do
  sudo firewall-cmd --zone=trusted --add-source="$cidr" --permanent 2>/dev/null || true
done

log "Configuring firewalld — CNI interfaces (trusted zone)..."
# ---- Trust CNI interfaces ----------------------------------------------------
# k3s has already started by the time we reach step 7, so flannel.1 and cni0
# exist.  The --permanent flag saves them; the --reload at the end of this step
# activates them.
for iface in cni0 flannel.1; do
  sudo firewall-cmd --zone=trusted --add-interface="$iface" --permanent 2>/dev/null || true
done

log "Configuring firewalld — masquerade + FORWARD chain..."
# ---- Masquerade (NAT for pods/containers leaving the host) -------------------
sudo firewall-cmd --zone=public  --add-masquerade --permanent 2>/dev/null || true
sudo firewall-cmd --zone=trusted --add-masquerade --permanent 2>/dev/null || true

# ---- Allow forwarding through flannel overlay (pod-to-pod) -------------------
# Without explicit FORWARD ACCEPT rules, firewalld drops packets between pods
# (e.g., mimir-gateway → distributor, loki-gateway → loki) even when the source
# CIDR is trusted, because FORWARD is a separate chain.
for iface in flannel.1 cni0; do
  sudo firewall-cmd --permanent --direct \
    --add-rule ipv4 filter FORWARD 0 -i "$iface" -j ACCEPT 2>/dev/null || true
  sudo firewall-cmd --permanent --direct \
    --add-rule ipv4 filter FORWARD 0 -o "$iface" -j ACCEPT 2>/dev/null || true
done

# ---- IP forwarding at kernel level -------------------------------------------
sudo sysctl -w net.ipv4.ip_forward=1 2>/dev/null || true
echo "net.ipv4.ip_forward = 1" | sudo tee /etc/sysctl.d/99-ip-forward.conf > /dev/null

# ---- Activate all permanent rules and restore Docker -------------------------
# All --permanent rules above are saved but not yet active.  A final reload
# makes them live.  Because --complete-reload (the reset at the top of this
# step) wiped Docker's iptables chains (DOCKER-FORWARD etc.), we then restart
# Docker so it re-creates every chain it owns in the now-stable iptables state.
# This is the single point where both firewalld and Docker reach their final
# known-good configuration.
log "Activating firewalld rules..."
sudo firewall-cmd --reload
log "Restarting Docker to re-create iptables chains in clean firewalld state..."
sudo systemctl restart docker
sleep 5
# Verify Docker is up — abort early with a clear message if not
if ! sudo systemctl is-active --quiet docker; then
  err "Docker failed to start after firewalld configuration."
  err "Check: sudo journalctl -u docker -n 50"
  exit 1
fi
log "Docker is running."

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
if grep -q 'export KUBECONFIG=' ~/.bashrc 2>/dev/null; then
  sed -i 's|^export KUBECONFIG=.*|export KUBECONFIG=~/.kube/config|' ~/.bashrc
else
  echo 'export KUBECONFIG=~/.kube/config' >> ~/.bashrc
fi
# KUBECONFIG already exported after k3s setup above; no-op but kept for clarity
export KUBECONFIG="${HOME}/.kube/config"

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

# --- 11a. Generate self-signed TLS certificate for Grafana --------------------
log "Generating self-signed TLS certificate for Grafana (valid 10 years)..."
GRAFANA_TLS_DIR="/tmp/grafana-tls"
mkdir -p "${GRAFANA_TLS_DIR}"

openssl req -x509 -nodes -days 3650 \
  -newkey rsa:2048 \
  -keyout "${GRAFANA_TLS_DIR}/tls.key" \
  -out    "${GRAFANA_TLS_DIR}/tls.crt" \
  -subj   "/CN=${HOST_IP}/O=DigitalTwins/OU=Observability" \
  -addext "subjectAltName=IP:${HOST_IP},DNS:localhost" \
  2>/dev/null

if [[ -f "${GRAFANA_TLS_DIR}/tls.crt" ]]; then
  GRAFANA_TLS_STATUS="SUCCESS"
  log "Certificate generated: ${GRAFANA_TLS_DIR}/tls.crt"
  log "  CN=${HOST_IP}  SAN=IP:${HOST_IP},DNS:localhost  validity=3650 days"
else
  GRAFANA_TLS_STATUS="FAILED"
  warn "TLS certificate generation failed — Grafana will fall back to HTTP"
fi

# --- 11b. Create (or replace) the TLS secret in the grafana namespace ---------
if [[ "${GRAFANA_TLS_STATUS}" == "SUCCESS" ]]; then
  log "Creating Kubernetes TLS secret 'grafana-tls' in namespace grafana..."
  kubectl create secret tls grafana-tls \
    --cert="${GRAFANA_TLS_DIR}/tls.crt" \
    --key="${GRAFANA_TLS_DIR}/tls.key" \
    -n grafana \
    --dry-run=client -o yaml | kubectl apply -f -
fi

# --- 11c. Write a TLS overlay values file ------------------------------------
# This overlay is merged on top of grafana-values.yaml by helm (later values
# files win on collision), so it overrides root_url and adds the TLS settings
# without touching the base values file in the repo.
GRAFANA_TLS_VALUES="/tmp/observability/grafana-tls-values.yaml"
if [[ "${GRAFANA_TLS_STATUS}" == "SUCCESS" ]]; then
  # /tmp/observability is owned by root (created with sudo mkdir), so use
  # sudo tee to write there — same pattern used for all other files in this dir.
  sudo tee "${GRAFANA_TLS_VALUES}" > /dev/null << EOF
grafana.ini:
  server:
    protocol: https
    cert_file: /etc/ssl/grafana/tls.crt
    cert_key: /etc/ssl/grafana/tls.key
    root_url: https://${HOST_IP}:30333/
    domain: ${HOST_IP}

# Mount the TLS secret into the Grafana pod
extraSecretMounts:
  - name: grafana-tls
    secretName: grafana-tls
    defaultMode: 0440
    mountPath: /etc/ssl/grafana
    readOnly: true
EOF
  log "TLS overlay values written to ${GRAFANA_TLS_VALUES}"
fi

log "Applying Grafana dashboard ConfigMaps..."
for cm in /tmp/observability/cm-log-dashboards.yaml /tmp/observability/cm-metric-dashboards.yaml; do
  kubectl apply -f "$cm" -n grafana || warn "Failed to apply $cm"
done

log "Deploying Grafana..."
GRAFANA_HELM_CMD=(
  helm upgrade --install grafana /tmp/observability/grafana-10.5.4.tgz
  --namespace grafana
  --values /tmp/observability/grafana-values.yaml
  --set adminUser=admin
  --set "adminPassword=${GRAFANA_ADMIN_PASSWORD}"
)
# Append the TLS overlay only when the cert was generated successfully
[[ "${GRAFANA_TLS_STATUS}" == "SUCCESS" ]] && \
  GRAFANA_HELM_CMD+=(--values "${GRAFANA_TLS_VALUES}")

if "${GRAFANA_HELM_CMD[@]}"; then
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
  log "Installing unzip (required to extract alloy)..."
  sudo apt-get install -y unzip

  log "Downloading and installing alloy..."
  ALLOY_TMP=$(mktemp -d)
  if curl -fsSL \
    "https://github.com/grafana/alloy/releases/latest/download/alloy-linux-amd64.zip" \
    -o "${ALLOY_TMP}/alloy.zip"; then
    unzip -j "${ALLOY_TMP}/alloy.zip" -d "${ALLOY_TMP}/"
    # The binary inside the zip may be named 'alloy' or 'alloy-linux-amd64'
    ALLOY_BIN=$(find "${ALLOY_TMP}" -maxdepth 1 -type f -not -name "*.zip" | head -1)
    sudo install -m 0755 "${ALLOY_BIN}" /usr/local/bin/alloy
  else
    warn "Alloy download failed"
  fi
  sudo rm -rf "${ALLOY_TMP}"
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
nohup sudo kubectl -n loki        port-forward svc/loki-gateway    3100:80   > /tmp/loki-port-forward.log    2>&1 &
nohup sudo kubectl -n mimir       port-forward svc/mimir-gateway   9005:8080 > /tmp/mimir-port-forward.log   2>&1 &
nohup sudo kubectl -n kube-system port-forward svc/metrics-server  8443:443  > /tmp/metrics-port-forward.log 2>&1 &
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
# 16. Persist KUBECONFIG in shell config files
# ==============================================================================
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
# docker-compose.yml lives at the repo root (two levels above buildout/dev/).
COMPOSE_DIR="$(realpath "${SCRIPT_DIR}/../..")"
if [[ ! -f "${COMPOSE_DIR}/docker-compose.yml" ]]; then
  warn "docker-compose.yml not found at ${COMPOSE_DIR} — skipping docker compose steps"
  DOCKER_COMPOSE_STATUS="SKIPPED (no docker-compose.yml at ${COMPOSE_DIR})"
else
  log "Running docker compose down in ${COMPOSE_DIR}..."
  sudo docker compose -f "${COMPOSE_DIR}/docker-compose.yml" down \
    || warn "docker compose down failed (non-fatal)"

  log "Running docker compose up -d in ${COMPOSE_DIR}..."
  if sudo docker compose -f "${COMPOSE_DIR}/docker-compose.yml" up -d; then
    DOCKER_COMPOSE_STATUS="SUCCESS"
  else
    DOCKER_COMPOSE_STATUS="FAILED"
    warn "docker compose up failed — check: sudo docker compose -f ${COMPOSE_DIR}/docker-compose.yml logs"
  fi
fi

# ==============================================================================
# 19. Cleanup temporary files
# ==============================================================================
log "Cleaning up temporary files..."
rm -f /tmp/k3s-install.sh /tmp/get-helm-3.sh 2>/dev/null || true
sudo rm -rf /tmp/observability 2>/dev/null || true

# ==============================================================================
# Summary report
# ==============================================================================

# Helper: colour-code a status string
status_colour() {
  local s="$1"
  case "$s" in
    SUCCESS*)           echo -e "${GREEN}${s}${NC}" ;;
    SKIPPED*)           echo -e "${YELLOW}${s}${NC}" ;;
    FAILED*|ERROR*)     echo -e "${RED}${s}${NC}" ;;
    *)                  echo -e "${s}" ;;
  esac
}

echo ""
echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}  Deployment Summary${NC}"
echo -e "${GREEN}============================================================${NC}"
printf " %-26s %s\n" "K3s:"              "$(status_colour "${K3S_STATUS}")"
printf " %-26s %s\n" "Grafana:"          "$(status_colour "${GRAFANA_STATUS}")"
printf " %-26s %s\n" "Grafana TLS cert:" "$(status_colour "${GRAFANA_TLS_STATUS}")"
printf " %-26s %s\n" "Loki:"             "$(status_colour "${LOKI_STATUS}")"
printf " %-26s %s\n" "Mimir:"            "$(status_colour "${MIMIR_STATUS}")"
printf " %-26s %s\n" "Alloy:"            "$(status_colour "${ALLOY_STATUS}")"
printf " %-26s %s\n" "Docker Compose:"   "$(status_colour "${DOCKER_COMPOSE_STATUS}")"
echo ""
echo -e "${GREEN}------------------------------------------------------------${NC}"
echo " Service Access URLs"
echo -e "${GREEN}------------------------------------------------------------${NC}"
GRAFANA_SCHEME="http"; [[ "${GRAFANA_TLS_STATUS}" == "SUCCESS" ]] && GRAFANA_SCHEME="https"
printf " %-28s %s\n" "Grafana:"        "${GRAFANA_SCHEME}://${HOST_IP}:30333"
printf " %-28s %s\n" "Keycloak (HTTPS):" "https://${HOST_IP}:8009"
printf " %-28s %s\n" "SEEK:"           "http://${HOST_IP}:8001"
printf " %-28s %s\n" "Airflow:"        "http://${HOST_IP}:8002"
printf " %-28s %s\n" "JupyterLab:"     "http://${HOST_IP}:8008"
printf " %-28s %s\n" "MinIO Console:"  "http://${HOST_IP}:8012"
printf " %-28s %s\n" "pgAdmin:"        "http://${HOST_IP}:8004"
echo ""
echo -e "${GREEN}------------------------------------------------------------${NC}"
echo " Internal Port Forwards (Alloy → k3s, localhost only)"
echo -e "${GREEN}------------------------------------------------------------${NC}"
printf " %-28s %s\n" "Loki push:"      "localhost:3100  →  loki-gateway:80"
printf " %-28s %s\n" "Mimir push:"     "localhost:9005  →  mimir-gateway:8080"
printf " %-28s %s\n" "Metrics server:" "localhost:8443  →  metrics-server:443"
echo " Logs: /tmp/loki-port-forward.log"
echo "        /tmp/mimir-port-forward.log"
echo "        /tmp/metrics-port-forward.log"
echo ""
echo -e "${GREEN}------------------------------------------------------------${NC}"
echo " Verification Commands"
echo -e "${GREEN}------------------------------------------------------------${NC}"
echo "  kubectl get secret grafana-tls -n grafana -o yaml  # inspect TLS secret"
echo "  openssl x509 -in /tmp/grafana-tls/tls.crt -noout -text  # inspect cert"
echo "  kubectl get pods -A                    # all k3s pods"
echo "  kubectl get pods -n mimir -o wide      # mimir pod IPs"
echo "  kubectl get pods -n loki  -o wide      # loki pod IPs"
echo "  sudo journalctl -u alloy -f            # alloy logs"
echo "  sudo firewall-cmd --list-all-zones           # full firewall state"
echo "  sudo /usr/local/bin/k3s-port-forward.sh    # restart port-forwards"
echo "  k9s                                    # interactive cluster view"
echo ""
if [[ "${DOCKER_COMPOSE_STATUS}" == "FAILED" ]]; then
  echo -e "${RED}------------------------------------------------------------${NC}"
  echo -e "${RED} Docker Compose FAILED — troubleshooting steps:${NC}"
  echo "  sudo systemctl restart docker"
  echo "  sudo docker compose -f ${COMPOSE_DIR}/docker-compose.yml up -d"
  echo "  sudo docker compose -f ${COMPOSE_DIR}/docker-compose.yml logs --tail=50"
  echo -e "${RED}------------------------------------------------------------${NC}"
  echo ""
fi
echo -e "${YELLOW} ACTION REQUIRED — docker without sudo in new terminals:${NC}"
echo "   newgrp docker       (activates group in current shell)"
echo "   — or — log out and back in"
echo -e "${GREEN}============================================================${NC}"
echo ""
