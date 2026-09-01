#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# create-admin-user.sh — create a SEEK server-admin user.
#
# Addresses SEEK by COMPOSE SERVICE name (docker compose exec seek), not by a
# fixed container name, so it works under the platform project where the
# container is ${PROJECT_NAME}-seek-1. Run it from the repo root (so
# `docker compose` finds docker-compose.yml) or with COMPOSE_FILE exported.
#
# Usage:
#   Local password : ./create-admin-user.sh <username> <password> <email>
#   Keycloak (SSO) : ./create-admin-user.sh <username> -keycloak <email>
# ---------------------------------------------------------------------------
set -euo pipefail

SEEK_SERVICE="${SEEK_SERVICE:-seek}"
USERNAME=${1:-}
PASSWORD=${2:-}
EMAIL=${3:-}

if [ -z "$USERNAME" ]; then
  echo "Usage: $0 <username> [password|'-keycloak'] <email>" >&2
  echo "  local user   : $0 admin mypassword admin@example.com" >&2
  echo "  keycloak user: $0 admin -keycloak admin@example.com" >&2
  exit 1
fi

# A "-keycloak" password means the user logs in via Keycloak Omniauth, so no
# local password is set on the SEEK account.
KEYCLOAK_MODE=false
if [ "$PASSWORD" = "-keycloak" ]; then
  KEYCLOAK_MODE=true
  PASSWORD=""
fi

echo "Creating SEEK admin user '$USERNAME' (service: $SEEK_SERVICE, email: $EMAIL)"
[ "$KEYCLOAK_MODE" = true ] && echo "Mode: Keycloak (no local password)" || echo "Mode: local password"

cat << RUBY_SCRIPT | docker compose exec -T "$SEEK_SERVICE" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -'
user   = User.find_by(login: "$USERNAME")
person = Person.find_by(email: "$EMAIL")
if user || person
  # Idempotent: a re-run over a persisted SEEK volume finds the login OR the
  # email already taken. Either means the admin was provisioned before — skip,
  # don't abort the whole deploy on the unique-email constraint.
  puts "SEEK admin already provisioned (login present: #{!user.nil?}, email present: #{!person.nil?}) — skipping"
else
  user = User.new
  user.login = "$USERNAME"

  # Only set a local password when not in Keycloak mode.
  unless "$KEYCLOAK_MODE" == "true"
    user.password = "$PASSWORD"
    user.password_confirmation = "$PASSWORD"
  end

  person = Person.new
  person.email = "$EMAIL"
  person.first_name = "$USERNAME"
  person.last_name = "User"
  person.user = user

  Seek::Permissions::Authorization.disable_authorization_checks do
    if person.save
      person.is_admin = true
      person.save

      # Activate immediately so we skip the email-confirmation step.
      user.activated_at = Time.current
      user.activation_code = nil
      user.save

      puts "OK: '$USERNAME' created as administrator (email: $EMAIL)"
    else
      abort "FAILED to create user: #{person.errors.full_messages.join(', ')}"
    end
  end
end
RUBY_SCRIPT
