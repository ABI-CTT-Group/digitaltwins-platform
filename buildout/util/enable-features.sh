#!/bin/bash
# Script to enable SEEK features via podman container Rails console
# Usage: ./enable-features.sh

CONTAINER_NAME="seek"

IP=$(curl -s ifconfig.me)

echo "Enabling desired SEEK features in container: $CONTAINER_NAME"

cat << RUBY_SCRIPT | podman exec -i "$CONTAINER_NAME" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -'
# Enable Omniauth
Seek::Config.omniauth_enabled = true

# Enable Programmes
Seek::Config.programmes_enabled = true

# Enable Workflows
Seek::Config.workflows_enabled = true

# Enable GA4GH TRS API (sub-option of Workflows)
Seek::Config.ga4gh_trs_api_enabled = true

# Enable Git support
Seek::Config.git_support_enabled = true

puts "✓ All features enabled successfully:"
puts "  - Omniauth enabled"
puts "  - Programmes enabled"
puts "  - Workflows enabled"
puts "  - GA4GH TRS API enabled"
puts "  - Git support enabled"

Seek::Config.site_base_host = "http://$IP:8001"
puts "Site base hostname set to: #{Seek::Config.site_base_host}"

RUBY_SCRIPT
