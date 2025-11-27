#!/bin/sh
set -e  # Exit immediately if any command fails

# ----------------------------
# Set default values (can be overridden by environment variables)
# ----------------------------
: "${API_URL:=http://localhost}"       # Backend API URL
: "${PORT:=8000}"                # Example feature flag

# ----------------------------
# Generate runtime-config.json
# ----------------------------
CONFIG_FILE="/usr/share/nginx/html/runtime-config.json"

cat > "$CONFIG_FILE" <<EOF
{
  "API_URL": "${API_URL}",
  "PORT": "${PORT}"
}
EOF

echo "✅ runtime-config.json generated:"
cat "$CONFIG_FILE"

# ----------------------------
#  Optional: Replace placeholders in index.html
# ----------------------------
# Example: if your index.html contains %API_URL% placeholders
# sed -i "s|%API_URL%|${API_URL}|g" /usr/share/nginx/html/index.html

# ----------------------------
# Start Nginx in the foreground
# ----------------------------
# -g 'daemon off;' keeps Nginx running in the foreground so the container doesn't exit
echo "🚀 Starting Nginx..."
nginx -g "daemon off;"
