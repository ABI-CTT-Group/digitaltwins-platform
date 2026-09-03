#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# seek-user-report.sh — read-only dump of SEEK's Users/People: SEEK login,
# name, email, whether they're linked to a Keycloak identity (and its sub),
# server-admin status, and project/programme membership.
#
# Useful after a portal-restore or when sorting out who owns what — SEEK
# splits "can this account log in" (User), "who are they" (Person), and
# "which Keycloak account are they" (Identity) across three tables that
# don't always line up the way you'd expect (see util/promote-seek-admin.sh
# for why). This just reports the current state; it changes nothing.
#
# Addresses SEEK by COMPOSE SERVICE name, like the other seek util scripts.
# Run from the repo root (or with COMPOSE_FILE set).
#
# Usage:
#   ./util/seek-user-report.sh
# ---------------------------------------------------------------------------
set -euo pipefail

SEEK_SERVICE="${SEEK_SERVICE:-seek}"

docker compose exec -T "$SEEK_SERVICE" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -' <<'RUBY'
rows = Person.order(:id).map do |p|
  u = p.user
  sub = u&.identities&.where(provider: 'oidc')&.pick(:uid)
  {
    person: p.id,
    login: u&.login || '(no user)',
    name: p.name,
    email: p.email,
    keycloak_sub: sub || '-',
    admin: p.is_admin? ? 'yes' : 'no',
    projects: p.projects.map(&:title).join(', '),
    programmes: p.programmes.map(&:title).join(', ')
  }
end

widths = { person: 6, login: 12, name: 20, email: 30, keycloak_sub: 38, admin: 5 }
header = "%-#{widths[:person]}s %-#{widths[:login]}s %-#{widths[:name]}s %-#{widths[:email]}s %-#{widths[:keycloak_sub]}s %-#{widths[:admin]}s %s" %
         ['PERSON', 'LOGIN', 'NAME', 'EMAIL', 'KEYCLOAK SUB', 'ADMIN', 'PROJECTS (PROGRAMMES)']
puts header
puts '-' * header.length
rows.each do |r|
  proj = r[:projects]
  proj += " (#{r[:programmes]})" unless r[:programmes].empty?
  puts "%-#{widths[:person]}s %-#{widths[:login]}s %-#{widths[:name]}s %-#{widths[:email]}s %-#{widths[:keycloak_sub]}s %-#{widths[:admin]}s %s" %
       [r[:person], r[:login], r[:name], r[:email], r[:keycloak_sub], r[:admin], proj]
end
RUBY
