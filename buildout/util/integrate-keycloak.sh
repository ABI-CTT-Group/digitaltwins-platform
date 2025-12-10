#!/bin/bash
# Script to integrate SEEK with Keycloak via Omniauth
#    Note: This doesn't quite work yet. Still work to do.
# This configures SEEK to use Keycloak as an OAuth2 provider
# Usage: ./integrate-keycloak.sh <keycloak_host> <keycloak_port> <realm> <client_id> <client_secret> [scheme]

CONTAINER_NAME="digitaltwins-platform-seek-1"
KEYCLOAK_HOST=${1:-keycloak}
KEYCLOAK_PORT=${2:-8080}
REALM=${3:-master}
CLIENT_ID=${4:-}
CLIENT_SECRET=${5:-}
SCHEME=${6:-http}

if [ -z "$CLIENT_ID" ] || [ -z "$CLIENT_SECRET" ]; then
  echo "Usage: $0 <keycloak_host> <keycloak_port> <realm> <client_id> <client_secret> [scheme]"
  echo ""
  echo "Example (using Docker network, http):"
  echo "  $0 keycloak 8080 master my-seek-client my-client-secret http"
  echo ""
  echo "Example (using external Keycloak, https):"
  echo "  $0 130.216.216.179 8009 digitaltwins my-seek-client my-client-secret https"
  echo ""
  echo "Scheme defaults to 'http' if not specified"
  exit 1
fi

echo "Configuring SEEK to integrate with Keycloak"
echo "SEEK Container: $CONTAINER_NAME"
echo "Keycloak Host: $KEYCLOAK_HOST:$KEYCLOAK_PORT"
echo "Scheme: $SCHEME"
echo "Realm: $REALM"
echo "Client ID: $CLIENT_ID"
echo ""

KEYCLOAK_URL="$SCHEME://$KEYCLOAK_HOST:$KEYCLOAK_PORT/auth"

cat << 'RUBY_SCRIPT' | docker exec -i "$CONTAINER_NAME" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -'
# Enable Omniauth
Seek::Config.omniauth_enabled = true

puts "✓ Omniauth enabled successfully"
puts ""
puts "Next steps to configure Keycloak:"
puts "  1. Log in to SEEK as an administrator"
puts "  2. Go to Server admin > Enable/disable features"
puts "  3. Configure the Keycloak OAuth2 provider with these details:"
puts "     - Name: keycloak"
puts "     - Strategy: openid_connect"
puts "     - Discovery: enabled"
puts "     - Client ID: $CLIENT_ID"
puts "     - Client Secret: $CLIENT_SECRET"
puts "     - Keycloak URL: $KEYCLOAK_URL"
puts "     - Realm: $REALM"
puts "  4. Save the configuration"
puts ""
puts "Then in Keycloak:"
puts "  1. Create or select the '$CLIENT_ID' client in the '$REALM' realm"
puts "  2. Set the redirect URI to: http://SEEK_HOST:8001/users/auth/keycloak/callback"
puts "  3. Enable the client"
RUBY_SCRIPT
