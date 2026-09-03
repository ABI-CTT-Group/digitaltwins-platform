#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# add-seek-project-member.sh — add a person directly to a SEEK project,
# instead of them submitting a join request and a project administrator
# approving it. Same end state (a GroupMembership row), skips the workflow.
#
# A membership is really (person, project, institution) — SEEK models this
# as a WorkGroup(project, institution) with GroupMemberships hanging off it.
# This tool only ever REUSES an existing institution (by id or exact title
# match, or the project's sole existing one if unambiguous) — it never
# creates a new Institution, since Institution has real validations of its
# own (a unique title, a valid country) that are not this tool's business to
# improvise answers for. If the project has no institution yet, or more than
# one, you must say which to use.
#
# Addresses SEEK by COMPOSE SERVICE name, like the other seek util scripts.
# Run from the repo root (or with COMPOSE_FILE set; docker compose needs the
# RUNTIME checkout where .env/secrets.env are rendered).
#
# Usage:
#   ./util/add-seek-project-member.sh <PERSON> <PROJECT_ID> [INSTITUTION] [-y|--yes]
#     PERSON: a SEEK login, email:<address>, or sub:<keycloak-uuid>
#     PROJECT_ID: numeric SEEK project id
#     INSTITUTION: numeric institution id or exact title (optional if the
#       project already has exactly one institution via an existing member)
#
#   ./util/add-seek-project-member.sh sub:1afb2774-0277-494f-a976-34a72683d972 11
#   ./util/add-seek-project-member.sh email:someone@example.com 7 "Te Whatu Ora"
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
INSTITUTION="${ARGS[2]:-}"
if [ -z "$PERSON" ] || [ -z "$PROJECT" ]; then
  echo "Usage: $0 <PERSON> <PROJECT_ID> [INSTITUTION] [-y|--yes]" >&2
  echo "  PERSON: a SEEK login, email:<address>, or sub:<keycloak-uuid>" >&2
  echo "  INSTITUTION: numeric institution id or exact title (optional if unambiguous)" >&2
  exit 1
fi

run_ruby() {  # $1 = APPLY (true/false)
  docker compose exec -T \
    -e "ASPM_PERSON=$PERSON" -e "ASPM_PROJECT=$PROJECT" -e "ASPM_INSTITUTION=$INSTITUTION" -e "ASPM_APPLY=$1" \
    "$SEEK_SERVICE" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -' <<'RUBY'
def resolve_person(spec)
  if spec.start_with?('sub:')
    sub = spec.sub('sub:', '')
    identity = Identity.find_by(provider: 'oidc', uid: sub)
    abort("add-seek-project-member: no SEEK identity linked to sub '#{sub}'") unless identity
    identity.user.person
  elsif spec.start_with?('email:')
    email = spec.sub('email:', '')
    person = Person.find_by(email: email)
    abort("add-seek-project-member: no SEEK person with email '#{email}'") unless person
    person
  else
    user = User.find_by(login: spec)
    abort("add-seek-project-member: no SEEK user with login '#{spec}'") unless user
    user.person
  end
end

person  = resolve_person(ENV.fetch('ASPM_PERSON'))
project = Project.find_by(id: ENV.fetch('ASPM_PROJECT'))
abort("add-seek-project-member: no SEEK project with id '#{ENV.fetch('ASPM_PROJECT')}'") unless project
apply = ENV.fetch('ASPM_APPLY') == 'true'
inst_spec = ENV['ASPM_INSTITUTION'].to_s

puts "PERSON:  #{person.name} <#{person.email}> (##{person.id})"
puts "PROJECT: #{project.title} (##{project.id})"

if project.people.include?(person)
  puts "OK: already a member of this project -- nothing to do"
  exit 0
end

existing_institutions = project.work_groups.includes(:institution).map(&:institution).uniq

institution =
  if inst_spec.present?
    (inst_spec =~ /\A\d+\z/ ? Institution.find_by(id: inst_spec) : nil) || Institution.find_by(title: inst_spec)
  elsif existing_institutions.size == 1
    existing_institutions.first
  end

if institution.nil?
  if inst_spec.present?
    abort("add-seek-project-member: no institution matching '#{inst_spec}'")
  elsif existing_institutions.empty?
    abort("add-seek-project-member: project ##{project.id} has no existing institution -- specify one (id or exact title)")
  else
    list = existing_institutions.map { |i| "#{i.id}:#{i.title}" }.join(', ')
    abort("add-seek-project-member: project ##{project.id} has multiple institutions (#{list}) -- specify which one")
  end
end

puts "INSTITUTION: #{institution.title} (##{institution.id})"

work_group = WorkGroup.find_by(project: project, institution: institution)
if work_group.nil? && apply
  Seek::Permissions::Authorization.disable_authorization_checks { work_group = WorkGroup.create!(project: project, institution: institution) }
end

if apply
  Seek::Permissions::Authorization.disable_authorization_checks { GroupMembership.create!(person: person, work_group: work_group) }
  puts "OK: added #{person.name} to #{project.title} via #{institution.title}"
else
  puts "#{work_group ? 'DRY RUN: would add' : 'DRY RUN: would create a work_group and add'} membership."
end
RUBY
}

echo "add-seek-project-member: resolving PERSON='$PERSON' PROJECT='$PROJECT' (service: $SEEK_SERVICE)"
run_ruby false

if [ "$YES" != true ]; then
  printf "Type 'yes' to apply: "; read -r ans
  [ "$ans" = "yes" ] || { echo "aborted."; exit 1; }
fi
run_ruby true
