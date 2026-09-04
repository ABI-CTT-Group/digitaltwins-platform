#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# transfer-seek-ownership.sh — reassign ownership of every SEEK item
# (contributor_id) from one Person to another.
#
# Why this exists: a portal-restore.sh brings in the SOURCE system's SEEK
# database verbatim, contributor_id and all. If the source content was
# created by a local-only SEEK account (no Keycloak identity — e.g. a
# developer's laptop login) rather than a real Keycloak-backed user, that
# ownership is stuck on an account nobody can/should use on the target. This
# moves it onto a real target-side Person (typically the platform admin) in
# one pass, across every table that has a contributor_id column — found by
# introspecting the schema, not a hand-maintained list, so it stays correct
# as SEEK adds asset types.
#
# Two tables are handled specially, NOT blanket-reassigned:
#   - permissions: contributor_id here is POLYMORPHIC (contributor_type may
#     be Person/Project/Institution/FavouriteGroup/...) and means "who this
#     sharing grant targets", not "who owns this" — rewriting it would risk
#     clobbering unrelated Project/Institution rows that happen to share the
#     same numeric id. Left untouched; re-share explicitly if needed.
#   - file_template_versions: also has a contributor_type column, so only
#     rows where contributor_type='Person' are touched.
# Every other contributor_id column is a plain FK straight to people.id.
#
# By decision, this tool moves CURRENT ownership only — it does NOT rewrite
# history. Any table ending in "_versions" (sop_versions, workflow_versions,
# data_file_versions, ...) records who submitted THAT past revision, not who
# owns the item today, so those are left alone; same for git_annotations
# (per-git_version metadata, keyed to a specific historical git_version_id).
#
# A raw UPDATE bypasses SEEK's ActiveRecord callbacks, which is fine for the
# data itself but NOT for two caches those callbacks normally keep in sync:
#   - the authorization lookup tables (*_auth_lookup) — SEEK's actual runtime
#     permission checks read THESE, not a live policy evaluation
#     (auth_lookup_enabled defaults to true in production), so without a
#     rebuild the old owner's cached rights linger and the new owner's don't
#     appear;
#   - the Solr search index (contributor-based facets/results go stale).
# So after a real (-y/--yes) transfer this also runs SEEK's own official
# maintenance tasks to reconcile both: `rake seek:repopulate_auth_lookup_tables_sync`
# (synchronous, full rebuild from current data) and `rake seek:reindex_all`
# (queues a background reindex). These are supported, run-anytime SEEK admin
# tasks, not something bespoke to this script.
#
# Also transfers Project/Programme-SCOPED roles (pal, project_administrator,
# asset_housekeeper, asset_gatekeeper, programme_administrator — the `roles`
# table, NOT contributor_id): these are what SEEK actually shows as e.g. a
# project's "Project Administrator", entirely separate from item ownership,
# and are easy to miss — is_admin does not imply it, so promoting the
# platform admin to server admin does not make them appear as any project's
# administrator. The site-wide `admin` role (scope NULL) is deliberately
# EXCLUDED here — that one is managed by promote-seek-admin.sh /
# demote-seek-admin.sh, addressed by Keycloak sub, not by this FROM/TO
# transfer, so the two mechanisms do not fight over the same role.
# A Project-scoped role requires the holder to already be a member of that
# project (a real SEEK model validation), so if TO is not yet a member,
# this first mirrors FROM's own project membership (GroupMembership) onto
# TO before moving the role — through real ActiveRecord saves, not raw SQL,
# since membership/role creation has validations worth actually running
# (unlike the bulk contributor_id columns, which are plain FKs with no
# validation of their own).
#
# FROM/TO each accept one of:
#   <seek-login>        e.g. clin864
#   email:<address>     e.g. email:admin@example.com
#   sub:<keycloak-uuid>  the Person linked to that Keycloak sub via `identities`
#
# Addresses SEEK by COMPOSE SERVICE name, like the other seek util scripts.
# Run from the repo root (or with COMPOSE_FILE set). Destructive: prompts for
# confirmation unless -y/--yes is given.
#
# Usage:
#   ./util/transfer-seek-ownership.sh <FROM> <TO> [-y|--yes]
#   ./util/transfer-seek-ownership.sh clin864 sub:1afb2774-0277-494f-a976-34a72683d972
# ---------------------------------------------------------------------------
set -euo pipefail

# docker compose needs the RUNTIME checkout (where .env/secrets.env are
# rendered), which is not necessarily the caller's cwd -- e.g. on an airgapped
# install the git source lives at /mnt/install_src/clean_src/... while the
# actual running stack is at ~/digitaltwins-platform. Match portal-restore.sh.
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
FROM="${ARGS[0]:-}"
TO="${ARGS[1]:-}"
if [ -z "$FROM" ] || [ -z "$TO" ]; then
  echo "Usage: $0 <FROM> <TO> [-y|--yes]" >&2
  echo "  FROM/TO: a SEEK login, email:<address>, or sub:<keycloak-uuid>" >&2
  exit 1
fi

run_ruby() {  # $1 = APPLY (true/false)
  docker compose exec -T \
    -e "TSO_FROM=$FROM" -e "TSO_TO=$TO" -e "TSO_APPLY=$1" \
    "$SEEK_SERVICE" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -' <<'RUBY'
def resolve(spec)
  if spec.start_with?('sub:')
    sub = spec.sub('sub:', '')
    identity = Identity.find_by(provider: 'oidc', uid: sub)
    abort("transfer-seek-ownership: no SEEK identity linked to sub '#{sub}'") unless identity
    identity.user.person
  elsif spec.start_with?('email:')
    email = spec.sub('email:', '')
    person = Person.find_by(email: email)
    abort("transfer-seek-ownership: no SEEK person with email '#{email}'") unless person
    person
  else
    user = User.find_by(login: spec)
    abort("transfer-seek-ownership: no SEEK user with login '#{spec}'") unless user
    user.person
  end
end

from_person = resolve(ENV.fetch('TSO_FROM'))
to_person   = resolve(ENV.fetch('TSO_TO'))
apply       = ENV.fetch('TSO_APPLY') == 'true'

if from_person == to_person
  abort("transfer-seek-ownership: FROM and TO resolve to the same person (##{from_person.id}, #{from_person.email}) -- nothing to do")
end

puts "FROM: person ##{from_person.id} #{from_person.name} <#{from_person.email}>"
puts "TO:   person ##{to_person.id} #{to_person.name} <#{to_person.email}>"
puts

conn = ActiveRecord::Base.connection
# Excludes historical/version-scoped tables (anything ending in "_versions",
# plus git_annotations, which is per-git_version metadata) — by decision this
# tool moves CURRENT ownership only and does not rewrite who submitted a past
# version. permissions is excluded for the separate polymorphic reason above.
HISTORY_EXCLUDED = ->(t) { t.end_with?('_versions') || t == 'git_annotations' }
tables = conn.tables.select { |t| conn.columns(t).any? { |c| c.name == 'contributor_id' } }
tables = tables.reject { |t| t == 'permissions' || HISTORY_EXCLUDED.call(t) }

total = 0
role_total = 0
transfer = lambda do
  tables.sort.each do |t|
    has_type = conn.columns(t).any? { |c| c.name == 'contributor_type' }
    qt = conn.quote_table_name(t)
    where_sql = has_type ? ['contributor_id = ? AND contributor_type = ?', from_person.id, 'Person']
                         : ['contributor_id = ?', from_person.id]

    count_sql = ActiveRecord::Base.sanitize_sql_array(["SELECT COUNT(*) FROM #{qt} WHERE #{where_sql.first}", *where_sql[1..]])
    count = conn.select_value(count_sql).to_i
    next if count.zero?
    total += count

    if apply
      update_sql = ActiveRecord::Base.sanitize_sql_array(
        ["UPDATE #{qt} SET contributor_id = ? WHERE #{where_sql.first}", to_person.id, *where_sql[1..]]
      )
      conn.execute(update_sql)
    end
    puts "#{apply ? 'moved' : 'would move'} %5d  %s" % [count, t]
  end

  # Project/Programme-scoped roles (see the header comment) -- deliberately
  # excludes the site-wide "admin" role (scope nil), owned by
  # promote/demote-seek-admin.sh.
  scoped_type_ids = RoleType.all.reject { |rt| rt.scope.nil? }.map(&:id)
  Role.where(person_id: from_person.id, role_type_id: scoped_type_ids).each do |role|
    role_type = RoleType.find_by_id(role.role_type_id)
    label = "#{role_type.key} on #{role.scope_type}/#{role.scope_id}"

    if role.scope_type == 'Project' && role.scope && !role.scope.people.include?(to_person)
      from_memberships = GroupMembership.joins(:work_group).where(person_id: from_person.id, work_groups: { project_id: role.scope_id })
      if from_memberships.none?
        puts "SKIPPED #{label}: FROM has no project membership to mirror onto TO"
        next
      end
      from_memberships.each do |gm|
        next if GroupMembership.exists?(person_id: to_person.id, work_group_id: gm.work_group_id)
        if apply
          Seek::Permissions::Authorization.disable_authorization_checks { GroupMembership.create!(person: to_person, work_group: gm.work_group) }
        end
        puts "#{apply ? 'added' : 'would add'} membership: ##{to_person.id} -> project #{role.scope_id} (work_group #{gm.work_group_id})"
      end
    end

    already_has_it = Role.exists?(person_id: to_person.id, role_type_id: role.role_type_id, scope_type: role.scope_type, scope_id: role.scope_id)
    role_total += 1
    if apply
      Seek::Permissions::Authorization.disable_authorization_checks do
        Role.create!(person: to_person, role_type_id: role.role_type_id, scope_type: role.scope_type, scope_id: role.scope_id) unless already_has_it
        role.destroy!
      end
    end
    puts "#{apply ? 'moved' : 'would move'} role: #{label}#{already_has_it ? ' (TO already had it -- just removed from FROM)' : ''}"
  end
end
# All-or-nothing when actually applying, so a mid-loop failure can't leave
# ownership half-migrated across tables.
apply ? ActiveRecord::Base.transaction { transfer.call } : transfer.call

puts
if total.zero? && role_total.zero?
  puts "Nothing to do: person ##{from_person.id} owns nothing and holds no scoped roles."
elsif apply
  puts "OK: moved #{total} item(s) and #{role_total} role(s) from ##{from_person.id} to ##{to_person.id}."
else
  puts "DRY RUN: #{total} item(s) and #{role_total} role(s) would move. Re-run with -y/--yes to apply."
end
RUBY
}

echo "transfer-seek-ownership: resolving FROM='$FROM' TO='$TO' (service: $SEEK_SERVICE)"
run_ruby false

if [ "$YES" != true ]; then
  printf "Type 'yes' to apply the above transfer: "; read -r ans
  [ "$ans" = "yes" ] || { echo "aborted."; exit 1; }
fi
run_ruby true

echo
echo "== rebuilding authorization lookup cache (rake seek:repopulate_auth_lookup_tables_sync) =="
docker compose exec -T "$SEEK_SERVICE" bash -c 'cd /seek && RAILS_ENV=production bundle exec rake seek:repopulate_auth_lookup_tables_sync'

echo
echo "== queuing a search reindex (rake seek:reindex_all) =="
docker compose exec -T "$SEEK_SERVICE" bash -c 'cd /seek && RAILS_ENV=production bundle exec rake seek:reindex_all'
