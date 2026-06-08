#!/bin/sh
set -e

# Ensure plugin nginx config directory exists
mkdir -p /etc/nginx/conf.d/plugins

# Choose template based on whether SSL certs are present
PORTAL_BACKEND_HOST="${PORTAL_BACKEND_HOST:-localhost}"
CERT_FILE="/etc/nginx/certs/${PORTAL_BACKEND_HOST}.crt"
KEY_FILE="/etc/nginx/certs/${PORTAL_BACKEND_HOST}.key"

if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
    echo "SSL certs found for ${PORTAL_BACKEND_HOST}, using HTTPS mode."
    TEMPLATE=/etc/nginx/conf.d/nginx.ssl.conf.template
else
    echo "No SSL certs found for ${PORTAL_BACKEND_HOST}, using HTTP mode (local development)."
    TEMPLATE=/etc/nginx/conf.d/nginx.http.conf.template
fi

# Upload ceiling — keep in sync with portal-backend's MAX_UPLOAD_MB.
# Default chosen to be generous for measurement DICOM datasets without
# being so large that a malformed upload fills disk.
export MAX_UPLOAD_MB="${MAX_UPLOAD_MB:-20480}"

# Per-chunk body cap for the measurement chunked-upload PUTs. Each part is one
# small request, so this is intentionally tiny vs MAX_UPLOAD_MB (the whole-zip
# sync path). Must stay >= backend MEASUREMENT_PART_SIZE_BYTES (default 8 MiB);
# default 16m leaves comfortable headroom.
export MAX_PART_SIZE_MB="${MAX_PART_SIZE_MB:-16}"

# Substitute environment variables into nginx config
envsubst '${BACKEND_PORT} ${PORTAL_BACKEND_HOST} ${MAX_UPLOAD_MB} ${MAX_PART_SIZE_MB}' < "$TEMPLATE" > /etc/nginx/conf.d/default.conf

echo "Starting Nginx..."
nginx -g "daemon off;"
