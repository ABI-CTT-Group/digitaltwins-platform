#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# gen-realm.sh — render the Keycloak realm import from its committed template.
#
#   services/keycloak/digitaltwins-realm.json.template  (${VAR} placeholders)
#     + env (PLATFORM_DOMAIN/PROTOCOL)  + secrets.env (client secrets, realm admin pw)
#     + derived KC_SSL_REQUIRED
#     -> services/keycloak/import/digitaltwins-realm.json   (git-ignored)
#
# Substitutes ONLY the platform's own vars; Keycloak's built-in ${...} tokens
# (authBaseUrl, username, *ScopeConsentText, role_*) are left intact. Keycloak
# imports this on FIRST boot only (empty volume).
#
#   util/gen-realm.sh -e /path/to/env -s /path/to/secrets.env
# ---------------------------------------------------------------------------
set -euo pipefail

TEMPLATE="${TEMPLATE:-services/keycloak/digitaltwins-realm.json.template}"
OUT="${OUT:-services/keycloak/import/digitaltwins-realm.json}"
ENV_FILE=""; SECRETS_FILE=""

usage(){ echo "usage: util/gen-realm.sh -e ENV_FILE -s SECRETS_FILE [-t TEMPLATE] [-o OUT]" >&2; exit 2; }
while getopts ":e:s:t:o:h" o; do case "$o" in
  e) ENV_FILE=$OPTARG;; s) SECRETS_FILE=$OPTARG;; t) TEMPLATE=$OPTARG;; o) OUT=$OPTARG;; *) usage;;
esac; done
[ -n "$ENV_FILE" ] && [ -n "$SECRETS_FILE" ] || usage
for f in "$TEMPLATE" "$ENV_FILE" "$SECRETS_FILE"; do
  [ -f "$f" ] || { echo "gen-realm.sh: missing input: $f" >&2; exit 1; }
done

# A slashless path passed to `.`/source is resolved via PATH, not the cwd — so
# `-e env` would source /usr/bin/env (the binary!) and fail. Force a slash.
case "$ENV_FILE"     in */*) ;; *) ENV_FILE="./$ENV_FILE";;         esac
case "$SECRETS_FILE" in */*) ;; *) SECRETS_FILE="./$SECRETS_FILE";; esac

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
KC_SSL_REQUIRED=$([ "${PLATFORM_PROTOCOL:-http}" = "https" ] && echo external || echo none)
# shellcheck disable=SC1090
. "$SECRETS_FILE"
set +a

# ONLY our injected vars — Keycloak's own ${...} tokens are preserved.
VARS='${PLATFORM_DOMAIN} ${PLATFORM_PROTOCOL} ${KC_SSL_REQUIRED} ${KEYCLOAK_CLIENT_SECRET} ${JUPYTERHUB_CLIENT_SECRET} ${AIRFLOW_KEYCLOAK_CLIENT_SECRET} ${SEEK_KEYCLOAK_CLIENT_SECRET} ${KEYCLOAK_REALM_ADMIN_PASSWORD} ${GRAFANA_OAUTH_SECRET} ${MINIO_KEYCLOAK_CLIENT_SECRET}'
mkdir -p "$(dirname "$OUT")"
envsubst "$VARS" < "$TEMPLATE" > "$OUT"

python3 -c "import json; json.load(open('$OUT'))" || { echo "gen-realm.sh: ERROR — rendered $OUT is not valid JSON" >&2; exit 1; }
for v in PLATFORM_DOMAIN PLATFORM_PROTOCOL KC_SSL_REQUIRED KEYCLOAK_CLIENT_SECRET JUPYTERHUB_CLIENT_SECRET AIRFLOW_KEYCLOAK_CLIENT_SECRET SEEK_KEYCLOAK_CLIENT_SECRET KEYCLOAK_REALM_ADMIN_PASSWORD GRAFANA_OAUTH_SECRET MINIO_KEYCLOAK_CLIENT_SECRET; do
  if grep -Fq "\${$v}" "$OUT"; then echo "gen-realm.sh: ERROR — unresolved \${$v} in $OUT" >&2; exit 1; fi
done
echo "gen-realm.sh: wrote $OUT (valid JSON, all platform vars resolved)"
