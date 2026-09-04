#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# demote-seek-admin.sh — remove SEEK server-admin rights from the Person
# linked to a given Keycloak `sub`. Companion to promote-seek-admin.sh.
#
# Addresses SEEK by COMPOSE SERVICE name, like the other seek util scripts.
# Run from the repo root (or with COMPOSE_FILE set; docker compose needs the
# RUNTIME checkout where .env/secrets.env are rendered).
#
# Refuses to demote the LAST remaining server admin (would lock everyone out
# of administering SEEK -- unlike promote, SEEK has no built-in recovery for
# that beyond a brand-new, single-person instance) unless -f/--force is given.
#
# Usage:
#   ./util/demote-seek-admin.sh <SUB> [-f|--force]
#     SUB must be given explicitly -- no default, same reasoning as
#     promote-seek-admin.sh: who gets demoted should be visible at the call
#     site, not implied.
# ---------------------------------------------------------------------------
set -euo pipefail

BASE_DIR="${BASE_DIR:-$HOME/digitaltwins-platform}"
cd "$BASE_DIR"

SEEK_SERVICE="${SEEK_SERVICE:-seek}"

FORCE=false
ARGS=()
for a in "$@"; do
  case "$a" in
    -f|--force) FORCE=true ;;
    *) ARGS+=("$a") ;;
  esac
done
SUB="${ARGS[0]:-}"
if [ -z "$SUB" ]; then
  echo "Usage: $0 <SUB> [-f|--force]" >&2
  echo "  SUB: the Keycloak user id (sub) to remove SEEK server-admin rights from." >&2
  exit 1
fi

echo "demote-seek-admin: demoting SEEK user linked to Keycloak sub '$SUB' (service: $SEEK_SERVICE)"

docker compose exec -T -e "SEEK_ADMIN_SUB=$SUB" -e "SEEK_DEMOTE_FORCE=$FORCE" "$SEEK_SERVICE" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -' <<'RUBY'
sub   = ENV.fetch('SEEK_ADMIN_SUB')
force = ENV.fetch('SEEK_DEMOTE_FORCE') == 'true'

identity = Identity.find_by(provider: 'oidc', uid: sub)
if identity.nil?
  puts "WARN: no SEEK identity linked to sub '#{sub}' -- nothing to demote."
  exit 0
end
person = identity.user.person

unless person.is_admin?
  puts "OK: '#{identity.user.login}' is not a server admin -- nothing to do"
  exit 0
end

other_admins = Person.where.not(id: person.id).to_a.count(&:is_admin?)
if other_admins.zero? && !force
  abort "REFUSED: '#{identity.user.login}' is the ONLY SEEK server admin. Demoting them would leave nobody able to administer SEEK (project membership, site settings, ...). Re-run with -f/--force if you really mean this."
end

Seek::Permissions::Authorization.disable_authorization_checks do
  person.is_admin = false
  if person.save(validate: false)
    puts "OK: demoted '#{identity.user.login}' (#{other_admins} other admin(s) remain)"
  else
    abort "FAILED: #{person.errors.full_messages.join(', ')}"
  end
end
RUBY
