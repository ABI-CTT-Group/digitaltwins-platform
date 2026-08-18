#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# set-seek-password.sh — set (reset) an EXISTING SEEK user's local password.
#
# Companion to create-admin-user.sh, which SKIPS a user that already exists.
# After portal-restore.sh replaces SEEK's user DB with the source system's, the
# local `admin` password is the source's (a hash you can't read) — use this to
# set it back to your own SEEK_ADMIN_PASSWORD.
#
# Addresses SEEK by COMPOSE SERVICE name (docker compose exec seek), so it works
# under the platform project. Run from the repo root (or with COMPOSE_FILE set).
#
# Usage:
#   ./util/set-seek-password.sh <username> <password>       # both required
#
#   # e.g. set the admin's password to your secrets.env value:
#   ./util/set-seek-password.sh admin "$SEEK_ADMIN_PASSWORD"
#
# The username/password are handed to the container via the ENVIRONMENT and read
# with ENV.fetch in the Ruby runner (not string-interpolated), so passwords with
# quotes / $ / spaces are safe and can't break or inject into the script.
# ---------------------------------------------------------------------------
set -euo pipefail

SEEK_SERVICE="${SEEK_SERVICE:-seek}"
LOGIN="${1:-}"
PASSWORD="${2:-}"

if [ -z "$LOGIN" ] || [ -z "$PASSWORD" ]; then
  echo "Usage: $0 <username> <password>" >&2
  echo "  e.g.  $0 admin \"\$SEEK_ADMIN_PASSWORD\"" >&2
  exit 1
fi

echo "set-seek-password: updating local password for SEEK user '$LOGIN' (service: $SEEK_SERVICE)"

docker compose exec -T \
  -e "SEEK_SET_LOGIN=$LOGIN" \
  -e "SEEK_SET_PASSWORD=$PASSWORD" \
  "$SEEK_SERVICE" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -' <<'RUBY'
login = ENV.fetch('SEEK_SET_LOGIN')
pw    = ENV.fetch('SEEK_SET_PASSWORD')
u = User.find_by(login: login)
abort("set-seek-password: no SEEK user with login '#{login}'") unless u
u.password = pw
u.password_confirmation = pw
if u.save
  puts "OK: password updated for '#{login}'"
else
  abort("FAILED: #{u.errors.full_messages.join(', ')}")
end
RUBY
