#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# rm-seek-project-member.sh — remove a person from a SEEK project. Companion
# to add-seek-project-member.sh.
#
# Destroys their GroupMembership row(s) for that project through a real
# ActiveRecord destroy (not raw SQL), because GroupMembership has its own
# after_destroy cleanup worth actually running:
#   - any now-dangling Project-scoped role the person holds for THIS project
#     (project_administrator, pal, asset_housekeeper, asset_gatekeeper) is
#     automatically stripped (Person#remove_dangling_project_roles) -- you do
#     not need transfer-seek-ownership.sh or a separate step for that;
#   - the underlying WorkGroup is destroyed too if it is left with no people.
# This does NOT touch item ownership (contributor_id) -- someone can be
# removed from a project while still shown as the creator of its assets; use
# transfer-seek-ownership.sh separately if that also needs to move.
#
# Addresses SEEK by COMPOSE SERVICE name, like the other seek util scripts.
# Run from the repo root (or with COMPOSE_FILE set; docker compose needs the
# RUNTIME checkout where .env/secrets.env are rendered).
#
# Usage:
#   ./util/rm-seek-project-member.sh <PERSON> <PROJECT_ID> [-y|--yes]
#     PERSON: a SEEK login, email:<address>, or sub:<keycloak-uuid>
#
#   ./util/rm-seek-project-member.sh sub:1afb2774-0277-494f-a976-34a72683d972 11
# ---------------------------------------------------------------------------
set -euo pipefail

BASE_DIR="${BASE_DIR:-$HOME/digitaltwins-platform}"
cd "$BASE_DIR"

SEEK_SERVICE="${SEEK_SERVICE:-seek}"

YES=false
ARGS=()
for a in "$@"; do
  case "$a" in
    -y|--yes) YES=true ;;
    *) ARGS+=("$a") ;;
  esac
done
PERSON="${ARGS[0]:-}"
PROJECT="${ARGS[1]:-}"
if [ -z "$PERSON" ] || [ -z "$PROJECT" ]; then
  echo "Usage: $0 <PERSON> <PROJECT_ID> [-y|--yes]" >&2
  echo "  PERSON: a SEEK login, email:<address>, or sub:<keycloak-uuid>" >&2
  exit 1
fi

run_ruby() {  # $1 = APPLY (true/false)
  docker compose exec -T \
    -e "RSPM_PERSON=$PERSON" -e "RSPM_PROJECT=$PROJECT" -e "RSPM_APPLY=$1" \
    "$SEEK_SERVICE" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -' <<'RUBY'
def resolve_person(spec)
  if spec.start_with?('sub:')
    sub = spec.sub('sub:', '')
    identity = Identity.find_by(provider: 'oidc', uid: sub)
    abort("rm-seek-project-member: no SEEK identity linked to sub '#{sub}'") unless identity
    identity.user.person
  elsif spec.start_with?('email:')
    email = spec.sub('email:', '')
    person = Person.find_by(email: email)
    abort("rm-seek-project-member: no SEEK person with email '#{email}'") unless person
    person
  else
    user = User.find_by(login: spec)
    abort("rm-seek-project-member: no SEEK user with login '#{spec}'") unless user
    user.person
  end
end

person  = resolve_person(ENV.fetch('RSPM_PERSON'))
project = Project.find_by(id: ENV.fetch('RSPM_PROJECT'))
abort("rm-seek-project-member: no SEEK project with id '#{ENV.fetch('RSPM_PROJECT')}'") unless project
apply = ENV.fetch('RSPM_APPLY') == 'true'

puts "PERSON:  #{person.name} <#{person.email}> (##{person.id})"
puts "PROJECT: #{project.title} (##{project.id})"

members = GroupMembership.joins(:work_group).where(person_id: person.id, work_groups: { project_id: project.id }).to_a
if members.empty?
  puts "OK: not a member of this project -- nothing to do"
  exit 0
end

scoped_roles = Role.where(person_id: person.id, scope_type: 'Project', scope_id: project.id).to_a
if scoped_roles.any?
  keys = scoped_roles.map { |r| RoleType.find_by_id(r.role_type_id).key }.join(', ')
  puts "Also holds role(s) here: #{keys} -- removed automatically as a consequence of leaving the project"
end

if apply
  Seek::Permissions::Authorization.disable_authorization_checks { members.each(&:destroy!) }
  puts "OK: removed #{person.name} from #{project.title} (#{members.size} membership row(s))"
else
  puts "DRY RUN: would remove #{members.size} membership row(s) from #{project.title}#{scoped_roles.any? ? ' and the role(s) above' : ''}."
end
RUBY
}

echo "rm-seek-project-member: resolving PERSON='$PERSON' PROJECT='$PROJECT' (service: $SEEK_SERVICE)"
run_ruby false

if [ "$YES" != true ]; then
  printf "Type 'yes' to apply: "; read -r ans
  [ "$ans" = "yes" ] || { echo "aborted."; exit 1; }
fi
run_ruby true
