#!/bin/sh
set -e  # Exit immediately if any command fails

# ----------------------------
# Ensure plugin nginx config directory exists
# ----------------------------
mkdir -p /etc/nginx/conf.d/plugins

# ----------------------------
# Substitute environment variables into nginx config
# ----------------------------
# Only substitute BACKEND_PORT to avoid breaking nginx's own $variables
envsubst '${BACKEND_PORT}' < /etc/nginx/conf.d/default.conf.template > /etc/nginx/conf.d/default.conf

# ----------------------------
# Start Nginx in the foreground
# ----------------------------
# -g 'daemon off;' keeps Nginx running in the foreground so the container doesn't exit
echo "Starting Nginx..."
nginx -g "daemon off;"
