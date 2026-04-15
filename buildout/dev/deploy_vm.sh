#!/bin/bash
# install.sh — VM setup script (equivalent of build_all.yaml)
# Run from the home directory of the ubuntu user on the target VM.
# Usage: bash install.sh
set -euo pipefail

PLATFORM_DIR="$HOME/digitaltwins-platform"
BUILDOUT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"  # dir containing this script
UTIL_DIR="$PLATFORM_DIR/buildout/util"

###############################################################################
# 1. Verify required environment variables
###############################################################################
check_env() {
    local var="$1"
    if [[ -z "${!var:-}" ]]; then
        echo "FATAL: The required environment variable $var must be set." >&2
        exit 1
    fi
}

check_env SEEK_ADMIN_PASSWORD
check_env KC_HTTPS_KEY_STORE_PASSWORD
check_env KC_CLIENT_SECRET
check_env KC_BOOTSTRAP_ADMIN_PASSWORD

echo "All required environment variables are set."

###############################################################################
# 2. Install required software
###############################################################################
echo "==> Installing required packages..."
sudo apt-get update -q
sudo apt-get install -y \
    jq \
    curl \
    telnet \
    firewalld \
    net-tools \
    openssl \
    units \
    bc \
    zip \
    postgresql-client \
    certbot

###############################################################################
# 3. Add user to docker group & enable Docker
###############################################################################
echo "==> Configuring Docker..."
sudo usermod -aG docker "$USER"
sudo systemctl enable docker
sudo systemctl start docker

# Note: group change takes effect in new login sessions.
# If docker commands below fail with permission denied, run:
#   newgrp docker
# or log out and back in, then re-run from this point.

###############################################################################
# 4. Clone the platform repository
###############################################################################
echo "==> Cloning digitaltwins-platform (branch: buildout)..."
if [[ -d "$PLATFORM_DIR/.git" ]]; then
    git -C "$PLATFORM_DIR" fetch --all
    git -C "$PLATFORM_DIR" checkout buildout
    git -C "$PLATFORM_DIR" pull --force
else
    git clone --branch buildout \
        https://github.com/ABI-CTT-Group/digitaltwins-platform.git \
        "$PLATFORM_DIR"
fi

echo "==> Updating submodules..."
git -C "$PLATFORM_DIR" submodule update --remote --recursive

###############################################################################
# 5. Write Docker daemon DNS config and restart
###############################################################################
echo "==> Configuring Docker DNS..."
sudo tee /etc/docker/daemon.json > /dev/null <<'EOF'
{
  "dns": ["8.8.8.8", "8.8.4.4"]
}
EOF
sudo systemctl restart docker

###############################################################################
# 6. Set up .env
###############################################################################
echo "==> Configuring .env..."
if [[ ! -f "$PLATFORM_DIR/.env" ]]; then
    cp "$PLATFORM_DIR/.env.template" "$PLATFORM_DIR/.env"
fi

# Update PORTAL_BACKEND_HOST_IP with the current public IP
MYIP=$(curl -s ifconfig.me)
sed -i "s/PORTAL_BACKEND_HOST_IP=.*/PORTAL_BACKEND_HOST_IP=$MYIP/g" "$PLATFORM_DIR/.env"

# Update AIRFLOW_UID with current user's UID
MYUID=$(id -u)
sed -i "s/AIRFLOW_UID=.*/AIRFLOW_UID=$MYUID/g" "$PLATFORM_DIR/.env"

###############################################################################
# 7. Set up API configs.ini
###############################################################################
echo "==> Configuring API configs.ini..."
API_CONFIGS="$PLATFORM_DIR/services/api/digitaltwins-api/configs.ini"
if [[ ! -f "$API_CONFIGS" ]]; then
    cp "${API_CONFIGS}.template" "$API_CONFIGS"
fi

###############################################################################
# 8. Set up SEEK database passwords
###############################################################################
echo "==> Configuring SEEK docker-compose.env..."
SEEK_ENV="$PLATFORM_DIR/services/seek/ldh-deployment/docker-compose.env"
if [[ ! -f "$SEEK_ENV" ]]; then
    sed \
        "s|<db-password>|$(openssl rand -base64 21)|g; \
         s|<root-password>|$(openssl rand -base64 21)|g" \
        "${SEEK_ENV}.tpl" > "$SEEK_ENV"
fi

###############################################################################
# 9. Inject secrets into .env
###############################################################################
echo "==> Writing secrets to .env..."
ENV_FILE="$PLATFORM_DIR/.env"

set_env_line() {
    local key="$1" val="$2" file="$3"
    if grep -q "^${key}=" "$file" 2>/dev/null; then
        sed -i "s|^${key}=.*|${key}=${val}|g" "$file"
    else
        echo "${key}=${val}" >> "$file"
    fi
    chmod 600 "$file"
}

set_env_line "KEYCLOAK_CLIENT_SECRET"    "$KC_CLIENT_SECRET"           "$ENV_FILE"
set_env_line "KC_BOOTSTRAP_ADMIN_PASSWORD" "\"$KC_BOOTSTRAP_ADMIN_PASSWORD\"" "$ENV_FILE"
set_env_line "SEEK_API_TOKEN"            "dummy"                       "$ENV_FILE"

# KC_HTTPS_KEY_STORE_PASSWORD — update existing line, uncomment if commented
sed -i "s/KC_HTTPS_KEY_STORE_PASSWORD=.*/KC_HTTPS_KEY_STORE_PASSWORD=\"${KC_HTTPS_KEY_STORE_PASSWORD}\"/g" "$ENV_FILE"
sed -i "s/#KC_HTTPS_KEY_STORE_PASSWORD=/KC_HTTPS_KEY_STORE_PASSWORD=/g" "$ENV_FILE"

# CLIENT_SECRET
sed -i "s/CLIENT_SECRET=.*/CLIENT_SECRET=\"${KC_CLIENT_SECRET}\"/g" "$ENV_FILE"

###############################################################################
# 10. Create Docker volumes
###############################################################################
echo "==> Creating Docker volumes..."
(
    set -a; source "$ENV_FILE"; set +a
    docker volume create "${COMPOSE_PROJECT_NAME}_filestore" || true
    docker volume create "${COMPOSE_PROJECT_NAME}_db"        || true
)

###############################################################################
# 11. Initialise airflow.cfg then patch it
###############################################################################
echo "==> Initialising airflow.cfg..."
docker compose -f "$PLATFORM_DIR/docker-compose.yml" \
    --env-file "$ENV_FILE" \
    run --rm airflow-cli airflow config list

AIRFLOW_CFG="$PLATFORM_DIR/services/airflow/config/airflow.cfg"
echo "==> Patching airflow.cfg CORS settings..."
sed -i "s/^access_control_allow_headers.*$/access_control_allow_headers = origin, content-type, accept/" "$AIRFLOW_CFG"
sed -i "s/^access_control_allow_methods.*/access_control_allow_methods = POST, GET, OPTIONS, DELETE/"    "$AIRFLOW_CFG"
sed -i "s/^access_control_allow_origins.*/access_control_allow_origins = /"                              "$AIRFLOW_CFG"

###############################################################################
# 12. Run airflow-init
###############################################################################
echo "==> Running airflow-init..."
docker compose -f "$PLATFORM_DIR/docker-compose.yml" \
    --env-file "$ENV_FILE" \
    up airflow-init

###############################################################################
# 13. Fix seek docker-compose ${PWD} path references
###############################################################################
echo "==> Patching SEEK docker-compose.yml..."
sed -i 's/\${PWD}\//.\//g' "$PLATFORM_DIR/services/seek/ldh-deployment/docker-compose.yml"

###############################################################################
# 14. Bring everything down before replacing Keycloak config
###############################################################################
echo "==> Stopping all services..."
docker compose -f "$PLATFORM_DIR/docker-compose.yml" --env-file "$ENV_FILE" down || true

###############################################################################
# 15. Deploy production Keycloak config files
###############################################################################
echo "==> Deploying Keycloak production config..."
cp "$BUILDOUT_DIR/keycloak-docker-compose.yml" \
   "$PLATFORM_DIR/services/keycloak/docker-compose.yml"

cp "$BUILDOUT_DIR/server.jks" \
   "$PLATFORM_DIR/services/keycloak/server.jks"

cp "$BUILDOUT_DIR/../data/digitaltwins-realm.json" \
   "$PLATFORM_DIR/services/keycloak/import/digitaltwins-realm.json"

###############################################################################
# 16. Start SEEK and wait for it to be ready
###############################################################################
echo "==> Starting SEEK..."
docker compose \
    -f "$PLATFORM_DIR/services/seek/ldh-deployment/docker-compose.yml" \
    --env-file "$ENV_FILE" \
    up -d

echo "==> Waiting 60 s for SEEK to start..."
sleep 60

###############################################################################
# 17. SEEK post-setup: admin user, features, API token
###############################################################################
echo "==> Creating SEEK admin user..."
"$UTIL_DIR/create-admin-user.sh" admin "$SEEK_ADMIN_PASSWORD" matt.pestle@auckland.ac.nz

echo "==> Enabling SEEK features..."
"$UTIL_DIR/enable-features.sh"

echo "==> Generating SEEK API token..."
"$UTIL_DIR/generate-token.sh"

###############################################################################
# 18. Restart everything and configure auto-restart
###############################################################################
echo "==> Stopping all services one last time..."
docker compose -f "$PLATFORM_DIR/docker-compose.yml" --env-file "$ENV_FILE" down || true

echo "==> Starting all services..."
docker compose -f "$PLATFORM_DIR/docker-compose.yml" --env-file "$ENV_FILE" up -d

echo "==> Configuring containers to restart unless-stopped..."
docker update --restart unless-stopped \
    $(docker compose -f "$PLATFORM_DIR/docker-compose.yml" --env-file "$ENV_FILE" ps -q)

###############################################################################
# 19. Add COMPOSE_FILE alias
###############################################################################
echo "==> Adding COMPOSE_FILE to ~/.bash_aliases..."
ALIAS_LINE="export COMPOSE_FILE=~/digitaltwins-platform/docker-compose.yml"
if grep -q "^export COMPOSE_FILE=" "$HOME/.bash_aliases" 2>/dev/null; then
    sed -i "s|^export COMPOSE_FILE=.*|$ALIAS_LINE|" "$HOME/.bash_aliases"
else
    echo "$ALIAS_LINE" >> "$HOME/.bash_aliases"
fi
chmod 600 "$HOME/.bash_aliases"

###############################################################################
echo ""
echo "==> Setup complete."
echo "    Run 'source ~/.bash_aliases' or open a new shell to pick up COMPOSE_FILE."
echo "    If Docker permission errors occur, log out and back in (or run 'newgrp docker') and re-run from step 10."
