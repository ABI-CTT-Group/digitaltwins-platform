#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# set-seek-programme-activation.sh — activate or deactivate a SEEK programme.
#
# Programme (unlike Project) has one real visibility lever: is_activated.
# ProgrammesController exempts index/show from login_required entirely (every
# SEEK install lists every programme's title/description to anyone, member or
# not — that is not something this platform's config controls), but ordinary
# users only see ACTIVATED programmes in that listing, and direct
# /programmes/:id access to an unactivated one is blocked for anyone who is
# not a site admin or that programme's administrator.
#
# Deactivating is the non-destructive alternative to deleting a programme you
# do not want ordinary Keycloak-logged-in users to see: unlike delete (which
# SEEK refuses unless the programme has zero projects), deactivating touches
# nothing underneath — its projects and all their content are untouched and
# still governed by their own normal project-membership/policy checks — and
# it is trivially reversible by running this again with `true`.
#
# Addresses SEEK by COMPOSE SERVICE name, like the other seek util scripts.
# Run from the repo root (or with COMPOSE_FILE set; docker compose needs the
# RUNTIME checkout where .env/secrets.env are rendered).
#
# Usage:
#   ./util/set-seek-programme-activation.sh <PROGRAMME> <true|false>
#     PROGRAMME: numeric SEEK programme id, or its exact title
#
#   ./util/set-seek-programme-activation.sh "12 LABOURS" false
#   ./util/set-seek-programme-activation.sh 4 true
# ---------------------------------------------------------------------------
set -euo pipefail

BASE_DIR="${BASE_DIR:-$HOME/digitaltwins-platform}"
cd "$BASE_DIR"

SEEK_SERVICE="${SEEK_SERVICE:-seek}"

PROGRAMME="${1:-}"
VALUE="${2:-}"
if [ -z "$PROGRAMME" ] || { [ "$VALUE" != "true" ] && [ "$VALUE" != "false" ]; }; then
  echo "Usage: $0 <PROGRAMME> <true|false>" >&2
  echo "  PROGRAMME: numeric SEEK programme id, or its exact title" >&2
  exit 1
fi

echo "set-seek-programme-activation: PROGRAMME='$PROGRAMME' -> is_activated=$VALUE (service: $SEEK_SERVICE)"

docker compose exec -T -e "SPA_PROGRAMME=$PROGRAMME" -e "SPA_VALUE=$VALUE" "$SEEK_SERVICE" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -' <<'RUBY'
spec = ENV.fetch('SPA_PROGRAMME')
value = ENV.fetch('SPA_VALUE') == 'true'

programme = (spec =~ /\A\d+\z/ ? Programme.find_by(id: spec) : nil) || Programme.find_by(title: spec)
abort("set-seek-programme-activation: no SEEK programme matching '#{spec}'") unless programme

puts "PROGRAMME: #{programme.title} (##{programme.id}), currently is_activated=#{programme.is_activated?}, #{programme.projects.count} project(s)"

if programme.is_activated? == value
  puts "OK: already #{value ? 'activated' : 'deactivated'} -- nothing to do"
else
  Seek::Permissions::Authorization.disable_authorization_checks do
    programme.update_attribute(:is_activated, value)
  end
  puts "OK: #{value ? 'activated' : 'deactivated'} '#{programme.title}'"
end
RUBY
