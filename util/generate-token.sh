#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# generate-token.sh — mint a SEEK API token and write it back to secrets.env.
#
# The platform's .env is GENERATED (util/gen-env.sh) from .env.template +
# secrets.env, so SEEK_API_TOKEN cannot just be sed'd into .env — the next
# render would wipe it. Instead we write the token into secrets.env (the single
# source of truth) and let the caller re-run gen-env.sh. A copy is also dropped
# in ~/keys for the operator.
#
# The token is only known AFTER SEEK is up, so the buildout seeds a placeholder
# SEEK_API_TOKEN first (so the first render validates), then calls this and
# regenerates .env.
#
# Usage:
#   SECRETS_FILE=/mnt/install_src/data/secrets.env ./generate-token.sh [username]
#     username defaults to "admin".
#
# Addresses SEEK by compose service name; run from the repo root.
# ---------------------------------------------------------------------------
set -euo pipefail

SEEK_SERVICE="${SEEK_SERVICE:-seek}"
SEEK_TOKEN_FILE_NAME="${SEEK_TOKEN_FILE_NAME:-$HOME/keys/seek_api_token.txt}"
USERNAME=${1:-admin}
: "${SECRETS_FILE:?set SECRETS_FILE to the secrets.env path the token should be written to}"
[ -f "$SECRETS_FILE" ] || { echo "generate-token.sh: no secrets file: $SECRETS_FILE" >&2; exit 1; }

# Rails prints ONLY the raw token on success (see the runner script), so any
# other output means failure — guarded below.
API_TOKEN=$(cat << RUBY_SCRIPT | docker compose exec -T "$SEEK_SERVICE" bash -c 'cd /seek && RAILS_ENV=production bundle exec rails runner -'
user = User.find_by(login: "$USERNAME")
abort "user not found: $USERNAME" unless user
token = ApiToken.new(user: user, title: "API token")
abort "failed to create token: #{token.errors.full_messages.join(', ')}" unless token.save
print token.token
RUBY_SCRIPT
)

if [ -z "$API_TOKEN" ]; then
  echo "generate-token.sh: SEEK returned an empty token" >&2
  exit 1
fi

# Replace SEEK_API_TOKEN in place (position-preserving), appending if absent.
# awk keeps the token out of any regex, so tokens with special chars are safe.
tmpf=$(mktemp)
awk -v tok="$API_TOKEN" '
  /^SEEK_API_TOKEN=/ { print "SEEK_API_TOKEN=" tok; done=1; next }
  { print }
  END { if (!done) print "SEEK_API_TOKEN=" tok }
' "$SECRETS_FILE" > "$tmpf"
chmod --reference="$SECRETS_FILE" "$tmpf" 2>/dev/null || chmod 600 "$tmpf"
mv "$tmpf" "$SECRETS_FILE"

mkdir -p "$(dirname "$SEEK_TOKEN_FILE_NAME")"
printf '%s\n' "$API_TOKEN" > "$SEEK_TOKEN_FILE_NAME"
chmod 600 "$SEEK_TOKEN_FILE_NAME"

echo "generate-token.sh: wrote SEEK_API_TOKEN to $SECRETS_FILE and $SEEK_TOKEN_FILE_NAME"
echo "generate-token.sh: re-run util/gen-env.sh to fold it into .env"
