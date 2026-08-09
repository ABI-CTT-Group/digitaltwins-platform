#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# enable-features.sh — turn on the SEEK features the platform relies on and
# set the site base host.
#
# The site base host must be the PUBLIC address SEEK is served at, INCLUDING
# the /seek reverse-proxy prefix (SEEK runs with RAILS_RELATIVE_URL_ROOT=/seek
# behind the gateway). Pass it in SEEK_SITE_BASE_URL, e.g.
#
#   SEEK_SITE_BASE_URL=https://twins.example.org/seek ./enable-features.sh
#
# (The old version guessed the host with `curl ifconfig.me:8001`, which is
# both airgap-hostile and wrong for the domain/proxy layout.)
#
# Addresses SEEK by compose service name; run from the repo root.
# ---------------------------------------------------------------------------
set -euo pipefail

SEEK_SERVICE="${SEEK_SERVICE:-seek}"
: "${SEEK_SITE_BASE_URL:?set SEEK_SITE_BASE_URL to the public /seek URL (e.g. https://host/seek)}"

echo "Enabling SEEK features (service: $SEEK_SERVICE); site base host -> $SEEK_SITE_BASE_URL"

cat << RUBY_SCRIPT | docker compose exec -T "$SEEK_SERVICE" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -'
Seek::Config.omniauth_enabled     = true   # Keycloak SSO
Seek::Config.programmes_enabled   = true
Seek::Config.workflows_enabled    = true
Seek::Config.ga4gh_trs_api_enabled = true  # sub-option of Workflows
Seek::Config.git_support_enabled  = true
Seek::Config.site_base_host        = "$SEEK_SITE_BASE_URL"

puts "OK: features enabled (omniauth, programmes, workflows, GA4GH TRS, git)"
puts "    site_base_host = #{Seek::Config.site_base_host}"
RUBY_SCRIPT
