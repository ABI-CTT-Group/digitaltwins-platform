#!/usr/bin/env bash
# Every secret in secrets.env.template is required wherever a compose file uses it: `${VAR:?message}`.
# `${VAR}` runs blank when the variable is unset, and `${VAR:-default}` runs on a public default.
# See docs/decisions/2026-11-19-require-compose-secrets.md.
# Run from the repo root (make test-util). Needs only bash, grep and find. Prints names, never values.
set -uo pipefail

# KEYCLOAK_DB_PASSWORD never reaches .env: every host runs on its compose default, which matches the
# role services/postgres/keycloak_init.sql creates. Requiring it needs a rotation first; see
# "Keycloak's database password is a public default" in docs/future_refactoring.md.
ALLOWED=" KEYCLOAK_DB_PASSWORD "

secrets=$(grep -oE '^[A-Z0-9_]+=' secrets.env.template | tr -d '=')
if [ -z "$secrets" ]; then echo "FAIL no secret names read from secrets.env.template"; exit 1; fi

# The SEEK submodule is a separate repo.
files=$( { echo docker-compose.yml; find services -name '*compose*.yml' ! -path 'services/seek/ldh-deployment/*'; } | sort)

fails=0
required=0
for f in $files; do
  for v in $secrets; do
    [[ "$ALLOWED" == *" $v "* ]] && continue
    required=$((required + $(grep -oE "\\\$\{$v:\?" "$f" | wc -l)))
    # Anything but `:?` after the name: `}`, `-`, `:-` or a bare `?`. Only the line number is kept.
    while IFS=: read -r line _; do
      echo "FAIL $f:$line $v: use \${$v:?...}"; fails=$((fails + 1))
    done < <(grep -noE "\\\$\{$v(\}|:?-|\?)" "$f")
  done
done

echo "ok   $required secret reference(s) are required"
echo "$fails failure(s)"
[ "$fails" -eq 0 ]
