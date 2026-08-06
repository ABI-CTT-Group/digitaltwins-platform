#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# renew-cert.sh — renew the platform's Let's Encrypt TLS cert, zero-downtime.
#
# Renews the cert for $PLATFORM_DOMAIN using the HTTP-01 *webroot* method: the
# gateway serves /.well-known/acme-challenge/ on port 80 from a bind-mounted
# dir (services/nginx/acme -> /var/www/certbot), so the gateway keeps running
# throughout — no outage. Then it copies the fresh cert into SSL_CERT_DIR as
# server.crt / server.key and reloads nginx in place.
#
#   Run ON THE PLATFORM host (the box that answers :80 from the Internet):
#     util/renew-cert.sh                 # renew if within --days of expiry
#     util/renew-cert.sh --force         # renew regardless of remaining days
#     util/renew-cert.sh --dry-run       # LE staging + no deploy (test plumbing)
#     util/renew-cert.sh -d my.domain    # override PLATFORM_DOMAIN
#
# Requirements:
#   * certbot installed on the host (apt: `certbot`)
#   * this host reachable from the Internet on port 80 for $PLATFORM_DOMAIN
#   * the gateway already recreated once to pick up the ACME bind-mount
#     (docker compose up -d gateway) — the script checks and tells you if not
#   * run as root (the script re-execs itself under sudo if needed)
#
# The domain comes from -d, else $PLATFORM_DOMAIN, else .env's PORTAL_BACKEND_HOST
# (the bare domain gen-env writes — PLATFORM_DOMAIN itself is a gen-env *input*, not
# an .env variable). REQUIRED — the script aborts if none resolve.
#
# Optional: CERTBOT_EMAIL (LE expiry notices; only needed at first registration),
#           RENEW_DAYS (default 30), SSL_CERT_DIR (from .env).
# ---------------------------------------------------------------------------
set -euo pipefail

# certbot + the /etc/letsencrypt writes need root; re-exec under sudo, keeping
# the caller's environment (so an exported PLATFORM_DOMAIN survives) and args.
if [ "$(id -u)" -ne 0 ]; then
  exec sudo -E bash "$0" "$@"
fi

# --- args --------------------------------------------------------------------
FORCE=0
DRY_RUN=0
DOMAIN_OVERRIDE=""
RENEW_DAYS="${RENEW_DAYS:-30}"
while [ $# -gt 0 ]; do
  case "$1" in
    --force)   FORCE=1 ;;
    --dry-run) DRY_RUN=1 ;;
    --days)    RENEW_DAYS="${2:?--days needs a number}"; shift ;;
    -d|--domain) DOMAIN_OVERRIDE="${2:?-d needs a domain}"; shift ;;
    -h|--help) sed -n '2,40p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

# --- locate the repo + read config from .env (without sourcing it) -----------
REPO_ROOT="$(cd "$(dirname "$(readlink -f "$0")")/.." && pwd)"
cd "$REPO_ROOT"
ENV_FILE="$REPO_ROOT/.env"

# env_get VAR -> value from .env (last wins), quotes stripped; empty if absent.
env_get() {
  [ -f "$ENV_FILE" ] || return 0
  sed -nE "s/^(export[[:space:]]+)?$1=(.*)$/\2/p" "$ENV_FILE" | tail -1 \
    | sed -E 's/^"(.*)"$/\1/; s/^'\''(.*)'\''$/\1/'
}

# Domain resolution: -d flag > caller env > .env PLATFORM_DOMAIN (usually ABSENT —
# it's a gen-env *input*, not emitted to .env) > .env PORTAL_BACKEND_HOST (the bare
# domain gen-env DOES write, from ${PLATFORM_DOMAIN}). REQUIRED.
PLATFORM_DOMAIN="${DOMAIN_OVERRIDE:-${PLATFORM_DOMAIN:-$(env_get PLATFORM_DOMAIN)}}"
[ -z "$PLATFORM_DOMAIN" ] && PLATFORM_DOMAIN="$(env_get PORTAL_BACKEND_HOST)"
: "${PLATFORM_DOMAIN:?could not resolve the domain. Pass -d <domain>, or set PLATFORM_DOMAIN in data/env and re-run util/gen-env.sh (it lands in .env as PORTAL_BACKEND_HOST).}"

# SSL_CERT_DIR: where the gateway reads server.crt/server.key (root .env).
SSL_CERT_DIR="$(env_get SSL_CERT_DIR)"; SSL_CERT_DIR="${SSL_CERT_DIR:-./services/nginx/certs}"
case "$SSL_CERT_DIR" in /*) ;; *) SSL_CERT_DIR="$REPO_ROOT/${SSL_CERT_DIR#./}" ;; esac

WEBROOT="$REPO_ROOT/services/nginx/acme"          # host side of the :ro bind-mount
DEPLOYED_CRT="$SSL_CERT_DIR/server.crt"
LIVE="/etc/letsencrypt/live/$PLATFORM_DOMAIN"

echo "domain        : $PLATFORM_DOMAIN"
echo "cert dir      : $SSL_CERT_DIR  (server.crt / server.key)"
echo "acme webroot  : $WEBROOT"
[ "$DRY_RUN" = 1 ] && echo "mode          : DRY RUN (LE staging, no deploy)"

# --- preflight: tools --------------------------------------------------------
command -v certbot >/dev/null || { echo "ERROR: certbot not installed (apt install certbot)." >&2; exit 1; }
command -v docker  >/dev/null || { echo "ERROR: docker not found." >&2; exit 1; }

# --- skip if the deployed cert is still healthy (unless --force) -------------
if [ "$FORCE" = 0 ] && [ -f "$DEPLOYED_CRT" ]; then
  if openssl x509 -in "$DEPLOYED_CRT" -noout -checkend "$((RENEW_DAYS * 86400))" 2>/dev/null; then
    echo "cert has more than $RENEW_DAYS days left — nothing to do (use --force to renew anyway)."
    exit 0
  fi
fi

# --- the gateway must be up and serving the ACME webroot ---------------------
GW="$(docker compose ps -q gateway 2>/dev/null || true)"
if [ -z "$GW" ]; then
  echo "gateway not running — starting it…"
  docker compose up -d gateway
  GW="$(docker compose ps -q gateway 2>/dev/null || true)"
fi
[ -n "$GW" ] || { echo "ERROR: could not find/start the 'gateway' service." >&2; exit 1; }

if ! docker exec "$GW" test -d /var/www/certbot 2>/dev/null; then
  echo "ERROR: the gateway isn't serving the ACME webroot yet." >&2
  echo "       Recreate it once to pick up the bind-mount, then re-run:" >&2
  echo "         docker compose up -d gateway" >&2
  exit 1
fi

# --- local self-test of the challenge path (catches misconfig before LE) -----
mkdir -p "$WEBROOT/.well-known/acme-challenge"
TOKEN=".renew-preflight-$$"
echo "ok" > "$WEBROOT/.well-known/acme-challenge/$TOKEN"
cleanup_token() { rm -f "$WEBROOT/.well-known/acme-challenge/$TOKEN" 2>/dev/null || true; }
trap cleanup_token EXIT
code="$(curl -s -o /dev/null -w '%{http_code}' -H "Host: $PLATFORM_DOMAIN" \
         "http://127.0.0.1/.well-known/acme-challenge/$TOKEN" || echo 000)"
cleanup_token; trap - EXIT
if [ "$code" != 200 ]; then
  echo "ERROR: local challenge self-test returned HTTP $code (expected 200)." >&2
  echo "       nginx isn't serving $WEBROOT on :80. Recreate the gateway and check" >&2
  echo "       the acme-challenge location in services/nginx/conf/ssl/default.conf." >&2
  exit 1
fi
echo "preflight     : challenge path served locally (HTTP 200) ✓"
echo "NOTE: this only tests LOCAL serving — Let's Encrypt must also reach"
echo "      http://$PLATFORM_DOMAIN/ from the Internet on port 80."

# --- issue / renew -----------------------------------------------------------
CB=(certbot certonly --webroot -w "$WEBROOT" -d "$PLATFORM_DOMAIN"
    --cert-name "$PLATFORM_DOMAIN" --non-interactive --agree-tos --keep-until-expiring)
if [ -n "${CERTBOT_EMAIL:-}" ]; then CB+=(-m "$CERTBOT_EMAIL"); else CB+=(--register-unsafely-without-email); fi
[ "$DRY_RUN" = 1 ] && CB+=(--dry-run)

echo "running: ${CB[*]}"
"${CB[@]}"

if [ "$DRY_RUN" = 1 ]; then
  echo "dry run OK — webroot validation succeeded. Re-run without --dry-run to issue."
  exit 0
fi

# --- deploy: copy into the gateway's cert dir + reload -----------------------
[ -f "$LIVE/fullchain.pem" ] || { echo "ERROR: $LIVE/fullchain.pem missing after renew." >&2; exit 1; }
install -m 0644 "$LIVE/fullchain.pem" "$DEPLOYED_CRT"
install -m 0600 "$LIVE/privkey.pem"   "$SSL_CERT_DIR/server.key"
# keep ownership matching the cert dir so ubuntu-level tooling stays happy
own="$(stat -c '%U:%G' "$SSL_CERT_DIR" 2>/dev/null || echo root:root)"
chown "$own" "$DEPLOYED_CRT" "$SSL_CERT_DIR/server.key" 2>/dev/null || true

echo "reloading gateway…"
docker exec "$GW" nginx -t
docker exec "$GW" nginx -s reload

# --- persist into the install bundle so it survives a VM rebuild -------------
DATA="/mnt/install_src/data"
if [ -d "$DATA" ]; then
  install -m 0644 "$LIVE/fullchain.pem" "$DATA/$PLATFORM_DOMAIN.fullchain.pem"
  install -m 0600 "$LIVE/privkey.pem"   "$DATA/$PLATFORM_DOMAIN.privkey.pem"
  ln -sfn "$PLATFORM_DOMAIN.fullchain.pem" "$DATA/fullchain.pem"
  ln -sfn "$PLATFORM_DOMAIN.privkey.pem"   "$DATA/privkey.pem"
  if tar -C /etc -cf /mnt/install_src/letsencrypt.tar letsencrypt 2>/dev/null; then
    echo "bundle        : refreshed $DATA/*.pem + /mnt/install_src/letsencrypt.tar ✓"
  else
    echo "bundle        : copied certs to $DATA (letsencrypt.tar refresh skipped)"
  fi
fi

# --- report ------------------------------------------------------------------
echo
echo "done. deployed cert:"
openssl x509 -in "$DEPLOYED_CRT" -noout -subject -issuer -enddate
