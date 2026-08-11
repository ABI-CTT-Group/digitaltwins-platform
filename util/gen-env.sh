#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# gen-env.sh — render the platform .env from .env.template
#
#   .env.template  (${VAR} placeholders, committed)
#     + env         (non-secret host inputs: PLATFORM_DOMAIN, PLATFORM_PROTOCOL)
#     + secrets.env (secrets)
#     + derived     (NGINX_MODE / SSL / AIRFLOW_UID)
#     -> .env       (final, git-ignored)
#
# First time: copy env.template -> env and secrets.env.template -> secrets.env,
# fill both in, then run from the repo root:
#
#   util/gen-env.sh -e /path/to/env -s /path/to/secrets.env
# ---------------------------------------------------------------------------
set -euo pipefail

ENV_FILE=env
SECRETS_FILE=secrets.env
TEMPLATE=.env.template
OUT=.env

usage() {
  cat >&2 <<EOF
usage: util/gen-env.sh [-e ENV_FILE] [-s SECRETS_FILE] [-t TEMPLATE] [-o OUT]
  -e  non-secret host vars file   (default: $ENV_FILE)
  -s  secrets file                (default: $SECRETS_FILE)
  -t  template                    (default: $TEMPLATE)
  -o  output                      (default: $OUT)
Run from the repo root. ENV_FILE / SECRETS_FILE are created by copying
env.template / secrets.env.template and filling in the values.
EOF
  exit 2
}

while getopts ":e:s:t:o:h" opt; do
  case "$opt" in
    e) ENV_FILE=$OPTARG ;;
    s) SECRETS_FILE=$OPTARG ;;
    t) TEMPLATE=$OPTARG ;;
    o) OUT=$OPTARG ;;
    h) usage ;;
    *) usage ;;
  esac
done

for f in "$TEMPLATE" "$ENV_FILE" "$SECRETS_FILE"; do
  [ -f "$f" ] || { echo "gen-env.sh: missing input file: $f" >&2; exit 1; }
done

# A slashless path passed to `.`/source is resolved via PATH, not the cwd — so
# `-e env` would source /usr/bin/env (the binary!) and fail. Force a slash.
case "$ENV_FILE"     in */*) ;; *) ENV_FILE="./$ENV_FILE";;         esac
case "$SECRETS_FILE" in */*) ;; *) SECRETS_FILE="./$SECRETS_FILE";; esac

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"       # PLATFORM_PROTOCOL, PLATFORM_DOMAIN, KC_HOSTNAME_STRICT*, ...

# Gateway TLS mode + portal URL scheme derive from the protocol, so an operator
# sets it in ONE place. Override by exporting NGINX_MODE / SSL before running
# (e.g. TLS offloaded by an upstream LB: SSL=true with NGINX_MODE=http).
if [ "${PLATFORM_PROTOCOL:-http}" = "https" ]; then
  : "${NGINX_MODE:=ssl}"; : "${SSL:=true}"
else
  : "${NGINX_MODE:=http}"; : "${SSL:=false}"
fi

# Host UID owning Airflow's mounted files (override by exporting AIRFLOW_UID).
: "${AIRFLOW_UID:=$(id -u)}"

# MinIO strictly extracts the backend `token_endpoint` from Keycloak's discovery document.
# If PLATFORM_DOMAIN is localhost, Keycloak returns `http://localhost/...`, which MinIO's
# container resolves to itself, causing a Connection Refused error. To fix this locally,
# we point MinIO to a custom discovery document hosted on the NGINX gateway.
if [ "${PLATFORM_DOMAIN}" = "localhost" ]; then
  : "${MINIO_OIDC_CONFIG_URL:=http://gateway/minio-discovery.json}"
else
  : "${MINIO_OIDC_CONFIG_URL:=${PLATFORM_PROTOCOL:-http}://${PLATFORM_DOMAIN}/auth/realms/${KEYCLOAK_REALM:-digitaltwins}/.well-known/openid-configuration}"
fi

# Which compose files the stack merges — base always; add the remote-compute
# override when this deploy drives a remote worker. Emitted into .env so BOTH the
# systemd unit (docker compose up -d at boot, from its WorkingDirectory) and
# operators' manual `docker compose` commands read the SAME value — no .bashrc,
# no scattered -f flags. Flip REMOTE_COMPUTE in the env inputs file (or export
# COMPOSE_FILE directly) to change it.
if [ "${REMOTE_COMPUTE:-false}" = "true" ]; then
  : "${COMPOSE_FILE:=docker-compose.yml:services/airflow/remote-compute.override.yml}"
else
  : "${COMPOSE_FILE:=docker-compose.yml}"
fi

# DAG queue routing — DAGs read Variable.get("compute_queue", "default"); Airflow maps
# AIRFLOW_VAR_* env vars to Variables. Default local; set AIRFLOW_VAR_COMPUTE_QUEUE=remote
# in the env inputs to route DAGs to a remote node. Rendered into .env via the
# ${AIRFLOW_VAR_COMPUTE_QUEUE} placeholder in .env.template.
: "${AIRFLOW_VAR_COMPUTE_QUEUE:=default}"

# shellcheck disable=SC1090
. "$SECRETS_FILE"   # secrets referenced as ${...} in the template
set +a

# Placeholders that matter live in assignment VALUES, not comments — restrict
# to lines like `KEY=...${VAR}...` so a ${...} shown in a comment is ignored.
refs=$(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$TEMPLATE" \
         | grep -oE '\$\{[A-Za-z_][A-Za-z0-9_]*\}' | tr -d '${}' | sort -u)

# Fail LOUDLY if the template references anything we did not provide — envsubst
# would otherwise blank it silently and you'd debug an empty password later.
missing=""
for v in $refs; do
  eval "val=\${$v-__UNSET__}"
  if [ "$val" = "__UNSET__" ] || [ -z "$val" ]; then missing="$missing $v"; fi
done
if [ -n "$missing" ]; then
  echo "gen-env.sh: template needs these vars but they are unset/empty:$missing" >&2
  echo "            (define them in $ENV_FILE or $SECRETS_FILE)" >&2
  exit 1
fi

# Substitute ONLY the vars the template uses, so any unexpected shell-style
# \$token elsewhere is left untouched.
VARS=$(for v in $refs; do printf '$%s ' "$v"; done)
envsubst "$VARS" < "$TEMPLATE" > "$OUT"

echo "gen-env.sh: wrote $OUT ($(grep -cvE '^[[:space:]]*(#|$)' "$OUT") settings) from $TEMPLATE"
# Belt-and-braces: no literal placeholders should survive.
if grep -nE '<YOUR_|<root-password>|<db-password>' "$OUT"; then
  echo "gen-env.sh: ERROR — literal placeholders remain in $OUT" >&2
  exit 1
fi
