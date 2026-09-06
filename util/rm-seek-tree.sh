#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# rm-seek-tree.sh — delete a SEEK Programme or Project and everything under
# it (Project -> Investigation -> Study -> Assay), bottom-up, in one shot.
#
# This is an ADMIN cleanup tool: it deletes unconditionally
# (Seek::Permissions::Authorization.disable_authorization_checks), regardless
# of who owns the content or whether the invoking account normally has rights
# to it -- unlike the SEEK UI/API, which would 403 if the caller isn't the
# contributor, an admin, or a project/programme administrator (hit this live
# cleaning up pre-existing content owned by a different account -- see
# util/transfer-seek-ownership.sh if you want ownership fixed permanently
# instead of just deleted).
#
# Also pre-emptively re-owns SEEK's RDF filestore cache
# (/seek/filestore/rdf) to the container's actual runtime user. A restored/
# migrated SEEK instance can have these files still owned by whatever uid
# the SOURCE system's SEEK ran as (docker cp preserves ownership, not the
# target's runtime user) -- confirmed live: deleting a migrated Study 500s
# with Errno::EACCES on its .rdf file until this is fixed. Harmless no-op
# on an instance that does not have this problem.
#
# Addresses SEEK by COMPOSE SERVICE name, like the other seek util scripts.
# Run from the repo root (or with COMPOSE_FILE set; docker compose needs the
# RUNTIME checkout where .env/secrets.env are rendered). Dry-run by default,
# -y to apply.
#
# Usage:
#   ./util/rm-seek-tree.sh programme <ID> [-y]
#   ./util/rm-seek-tree.sh project   <ID> [-y]
#
#   ./util/rm-seek-tree.sh programme 14 -y
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
KIND="${ARGS[0]:-}"
ID="${ARGS[1]:-}"
if { [ "$KIND" != "programme" ] && [ "$KIND" != "project" ]; } || [ -z "$ID" ]; then
  echo "Usage: $0 <programme|project> <ID> [-y|--yes]" >&2
  exit 1
fi

run_ruby() {  # $1 = APPLY (true/false)
  docker compose exec -T -e "RST_KIND=$KIND" -e "RST_ID=$ID" -e "RST_APPLY=$1" \
    "$SEEK_SERVICE" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -' <<'RUBY'
kind  = ENV.fetch('RST_KIND')
id    = ENV.fetch('RST_ID')
apply = ENV.fetch('RST_APPLY') == 'true'

klass = kind == 'programme' ? Programme : Project
root = klass.find_by(id: id)
abort("rm-seek-tree: no #{kind} with id '#{id}'") unless root
projects = kind == 'programme' ? root.projects.to_a : [root]

puts "#{kind.capitalize} ##{root.id} #{root.title.inspect} -- #{projects.size} project(s)"

total = 0
destroy = lambda do
  projects.each do |proj|
    proj.investigations.to_a.each do |inv|
      inv.studies.to_a.each do |study|
        study.assays.to_a.each do |assay|
          total += 1
          puts "#{apply ? 'destroying' : 'would destroy'} Assay ##{assay.id} #{assay.title.inspect}"
          Seek::Permissions::Authorization.disable_authorization_checks { assay.destroy! } if apply
        end
        total += 1
        puts "#{apply ? 'destroying' : 'would destroy'} Study ##{study.id} #{study.title.inspect}"
        Seek::Permissions::Authorization.disable_authorization_checks { study.destroy! } if apply
      end
      total += 1
      puts "#{apply ? 'destroying' : 'would destroy'} Investigation ##{inv.id} #{inv.title.inspect}"
      Seek::Permissions::Authorization.disable_authorization_checks { inv.destroy! } if apply
    end
    total += 1
    puts "#{apply ? 'destroying' : 'would destroy'} Project ##{proj.id} #{proj.title.inspect}"
    Seek::Permissions::Authorization.disable_authorization_checks { proj.destroy! } if apply
  end

  if kind == 'programme'
    total += 1
    puts "#{apply ? 'destroying' : 'would destroy'} Programme ##{root.id} #{root.title.inspect}"
    Seek::Permissions::Authorization.disable_authorization_checks { root.destroy! } if apply
  end
end
apply ? ActiveRecord::Base.transaction { destroy.call } : destroy.call

puts
puts apply ? "OK: destroyed #{total} record(s)." : "DRY RUN: #{total} record(s) would be destroyed. Re-run with -y/--yes to apply."
RUBY
}

echo "rm-seek-tree: re-owning SEEK's RDF filestore cache to its runtime user (best-effort)"
docker compose exec -u root -T "$SEEK_SERVICE" chown -R www-data:www-data /seek/filestore/rdf 2>/dev/null \
  || echo "  (skipped -- not needed, or exec -u root not permitted here)"

echo "rm-seek-tree: $KIND #$ID"
run_ruby false

if [ "$YES" != true ]; then
  printf "Type 'yes' to destroy the above: "; read -r ans
  [ "$ans" = "yes" ] || { echo "aborted."; exit 1; }
fi
run_ruby true
