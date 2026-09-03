#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# promote-seek-admin.sh — make the platform admin's Keycloak identity a SEEK
# server admin, addressed by Keycloak `sub` rather than by guessing the SEEK
# login.
#
# SEEK's OIDC login auto-provisions a SEEK user the first time a Keycloak
# user logs in interactively, deriving a login (e.g. Keycloak "admin1" ->
# SEEK "admin1186") that does NOT match PLATFORM_ADMIN_USERNAME. A restore
# replaces SEEK's whole user set, so any previously-promoted user is gone —
# but the realm template pins the platform admin's Keycloak user id, so the
# `identities.uid` <-> Keycloak `sub` link survives every restore regardless
# of what SEEK login gets derived.
#
# Looks up the SEEK Identity (provider oidc, uid = sub) and sets is_admin on
# its Person. If no such Identity exists yet (the admin has never logged in
# via Keycloak on this instance), this is a no-op WARN, not a failure.
#
# Addresses SEEK by COMPOSE SERVICE name, like set-seek-password.sh /
# create-admin-user.sh. Run from the repo root (or with COMPOSE_FILE set).
#
# Usage:
#   ./util/promote-seek-admin.sh [SUB]
#     SUB defaults to the platform admin's pinned Keycloak user id, read from
#     the committed realm template.
# ---------------------------------------------------------------------------
set -euo pipefail

# docker compose needs the RUNTIME checkout (where .env/secrets.env are
# rendered), which is not necessarily the caller's cwd -- e.g. on an airgapped
# install the git source lives at /mnt/install_src/clean_src/... while the
# actual running stack is at ~/digitaltwins-platform. Match portal-restore.sh.
BASE_DIR="${BASE_DIR:-$HOME/digitaltwins-platform}"
cd "$BASE_DIR"

SEEK_SERVICE="${SEEK_SERVICE:-seek}"
TEMPLATE="${TEMPLATE:-services/keycloak/digitaltwins-realm.json.template}"

SUB="${1:-}"
if [ -z "$SUB" ]; then
  [ -f "$TEMPLATE" ] || { echo "promote-seek-admin: no SUB given and template '$TEMPLATE' not found" >&2; exit 1; }
  # The admin's pinned "id" is the line immediately before its
  # "username": "${PLATFORM_ADMIN_USERNAME}" placeholder in the users[] block.
  SUB=$(grep -A1 '"id":' "$TEMPLATE" | grep -B1 'PLATFORM_ADMIN_USERNAME' | grep '"id":' | head -1 | sed -E 's/.*"id": *"([^"]+)".*/\1/')
  [ -n "$SUB" ] || { echo "promote-seek-admin: could not find the platform admin's pinned id in $TEMPLATE" >&2; exit 1; }
fi

echo "promote-seek-admin: promoting SEEK user linked to Keycloak sub '$SUB' (service: $SEEK_SERVICE)"

docker compose exec -T -e "SEEK_ADMIN_SUB=$SUB" "$SEEK_SERVICE" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -' <<'RUBY'
sub = ENV.fetch('SEEK_ADMIN_SUB')
identity = Identity.find_by(provider: 'oidc', uid: sub)
if identity.nil?
  puts "WARN: no SEEK identity linked to sub '#{sub}' yet -- the admin hasn't logged in via Keycloak on this instance. It will self-link on first login (but won't auto-promote); re-run this afterwards."
  exit 0
end
person = identity.user.person
if person.is_admin?
  puts "OK: '#{identity.user.login}' is already a server admin"
else
  Seek::Permissions::Authorization.disable_authorization_checks do
    person.is_admin = true
    if person.save(validate: false)
      puts "OK: promoted '#{identity.user.login}' to server admin"
    else
      abort "FAILED: #{person.errors.full_messages.join(', ')}"
    end
  end
end
RUBY
