#!/bin/sh
set -e  # Exit immediately if any command fails

# ----------------------------
# Set default values (can be overridden by environment variables)
# ----------------------------
: "${PORTAL_BACKEND_HOST_IP:=localhost}"       # Backend IP or hostname
: "${BACKEND_PORT:=8000}"                # PORT
: "${SSL:=false}"  # Full API URL

# ----------------------------
# Generate runtime-config.json
# ----------------------------
CONFIG_FILE="/usr/share/nginx/html/runtime-config.json"

cat > "$CONFIG_FILE" <<EOF
{
  "PORTAL_BACKEND_HOST_IP": "${PORTAL_BACKEND_HOST_IP}",
  "BACKEND_PORT": "${BACKEND_PORT}",
  "SSL": ${SSL}
}
EOF

echo "✅ runtime-config.json generated:"
cat "$CONFIG_FILE"

# ----------------------------
#  Optional: Replace placeholders in index.html
# ----------------------------
# Example: if your index.html contains %PORTAL_BACKEND_HOST_IP% placeholders
# sed -i "s|%PORTAL_BACKEND_HOST_IP%|${PORTAL_BACKEND_HOST_IP}|g" /usr/share/nginx/html/index.html

# ----------------------------
# Start Nginx in the foreground
# ----------------------------
# -g 'daemon off;' keeps Nginx running in the foreground so the container doesn't exit
echo "🚀 Starting Nginx..."
nginx -g "daemon off;"
