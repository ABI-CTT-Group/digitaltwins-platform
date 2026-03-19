#!/bin/sh
set -e  # Exit immediately if any command fails

# ----------------------------
# Ensure plugin nginx config directory exists
# ----------------------------
mkdir -p /etc/nginx/conf.d/plugins

# ----------------------------
# Start Nginx in the foreground
# ----------------------------
# -g 'daemon off;' keeps Nginx running in the foreground so the container doesn't exit
echo "Starting Nginx..."
nginx -g "daemon off;"
