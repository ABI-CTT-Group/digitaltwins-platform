#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# issue-cert.sh — obtain a Let's Encrypt cert BEFORE the platform is installed.
#
# Uses certbot's **standalone** mode: certbot runs its own temporary web server
# on port 80 for the HTTP-01 challenge, so it needs NOTHING else running — no
# docker, no gateway, no platform. This breaks the chicken-and-egg where an SSL
# install needs a cert to boot the gateway, but renew-cert.sh (webroot) needs the
# gateway already up. Run this first; it drops the cert into the install bundle's
# data/ dir, then you install normally.
#
#   sudo util/issue-cert.sh <domain> [--data-dir DIR] [--email ADDR] [--dry-run]
#     <domain>       the FQDN to certify (e.g. staging.drai.auckland.ac.nz)
#     --data-dir DIR where to drop the cert (default: /mnt/install_src/data)
#     --email ADDR   LE account email (or $CERTBOT_EMAIL); else registers w/o email
#     --dry-run      LE staging, no cert written (test reachability/plumbing)
#
# Requirements: certbot installed; the box reachable from the Internet on :80 for
# <domain>; outbound to Let's Encrypt; and **port 80 free** (the platform gateway
# must NOT be running yet — that's the normal pre-install state).
#
# For RENEWALS once the platform is up, use util/renew-cert.sh (webroot, no outage).
# ---------------------------------------------------------------------------
set -euo pipefail

# certbot binds :80 and writes /etc/letsencrypt — needs root.
if [ "$(id -u)" -ne 0 ]; then exec sudo -E bash "$0" "$@"; fi

DOMAIN=""
DATA_DIR="/mnt/install_src/data"
EMAIL="${CERTBOT_EMAIL:-}"
DRY_RUN=0
while [ $# -gt 0 ]; do
  case "$1" in
    --data-dir) DATA_DIR="${2:?--data-dir needs a path}"; shift ;;
    --email)    EMAIL="${2:?--email needs an address}"; shift ;;
    --dry-run)  DRY_RUN=1 ;;
    -h|--help)  sed -n '2,25p' "$0"; exit 0 ;;
    -*)         echo "unknown argument: $1" >&2; exit 2 ;;
    *)          DOMAIN="$1" ;;
  esac
  shift
done
: "${DOMAIN:?usage: issue-cert.sh <domain> [--data-dir DIR] [--email ADDR] [--dry-run]}"

echo "domain    : $DOMAIN"
echo "data dir  : $DATA_DIR"
[ "$DRY_RUN" = 1 ] && echo "mode      : DRY RUN (LE staging, no cert written)"

command -v certbot >/dev/null || { echo "ERROR: certbot not installed (apt install certbot)." >&2; exit 1; }

# port 80 must be free — standalone can't bind it otherwise (stop the gateway first)
if command -v ss >/dev/null && ss -ltn 2>/dev/null | grep -q ':80 '; then
  echo "ERROR: something is already listening on :80 — certbot --standalone can't bind it." >&2
  echo "       Stop whatever holds it first (e.g. the platform gateway: docker compose down)." >&2
  exit 1
fi

# outbound to LE (issuance POSTs to the ACME API)
if ! timeout 8 bash -c 'cat < /dev/null > /dev/tcp/acme-v02.api.letsencrypt.org/443' 2>/dev/null; then
  echo "ERROR: no outbound to Let's Encrypt (acme-v02.api.letsencrypt.org:443) — airgapped/offline." >&2
  exit 1
fi
echo "preflight : :80 free, outbound to LE OK ✓"
echo "NOTE: LE must reach http://$DOMAIN/ from the Internet on :80 (DNS must point here)."

CB=(certbot certonly --standalone -d "$DOMAIN" --cert-name "$DOMAIN"
    --non-interactive --agree-tos --keep-until-expiring)
if [ -n "$EMAIL" ]; then CB+=(-m "$EMAIL"); else CB+=(--register-unsafely-without-email); fi
[ "$DRY_RUN" = 1 ] && CB+=(--dry-run)

echo "running: ${CB[*]}"
"${CB[@]}"

if [ "$DRY_RUN" = 1 ]; then
  echo "dry run OK — standalone validation succeeded. Re-run without --dry-run to issue."
  exit 0
fi

LIVE="/etc/letsencrypt/live/$DOMAIN"
[ -f "$LIVE/fullchain.pem" ] || { echo "ERROR: $LIVE/fullchain.pem missing after issue." >&2; exit 1; }

# Drop into the bundle's data/ under the domain name + point the generic symlinks
# the install reads (data/fullchain.pem / data/privkey.pem) at it.
if [ -d "$DATA_DIR" ]; then
  install -m 0644 "$LIVE/fullchain.pem" "$DATA_DIR/$DOMAIN.fullchain.pem"
  install -m 0600 "$LIVE/privkey.pem"   "$DATA_DIR/$DOMAIN.privkey.pem"
  ln -sfn "$DOMAIN.fullchain.pem" "$DATA_DIR/fullchain.pem"
  ln -sfn "$DOMAIN.privkey.pem"   "$DATA_DIR/privkey.pem"
  tar -C /etc -cf "$(dirname "$DATA_DIR")/letsencrypt.tar" letsencrypt 2>/dev/null \
    && echo "bundle    : $DATA_DIR/{fullchain,privkey}.pem → $DOMAIN.* ; letsencrypt.tar refreshed ✓" \
    || echo "bundle    : copied to $DATA_DIR (letsencrypt.tar refresh skipped)"
  # We ran as root (certbot needs it), so these are root-owned — hand them back to
  # the invoking user ($SUDO_USER; $USER is 'root' after the sudo re-exec) so the
  # non-root install step can read them.
  OWNER="${SUDO_USER:-$USER}"
  if [ -n "$OWNER" ] && [ "$OWNER" != root ]; then
    OWNER_GRP="$(id -gn "$OWNER" 2>/dev/null || echo "$OWNER")"
    chown -h "$OWNER:$OWNER_GRP" \
      "$DATA_DIR/$DOMAIN.fullchain.pem" "$DATA_DIR/$DOMAIN.privkey.pem" \
      "$DATA_DIR/fullchain.pem" "$DATA_DIR/privkey.pem" 2>/dev/null || true
    chown "$OWNER:$OWNER_GRP" "$(dirname "$DATA_DIR")/letsencrypt.tar" 2>/dev/null || true
    echo "owner     : cert files chowned to $OWNER:$OWNER_GRP"
  fi
else
  echo "NOTE: $DATA_DIR not found — cert is in $LIVE/. Copy fullchain.pem + privkey.pem into your install data/ dir." >&2
fi

echo
openssl x509 -in "$LIVE/fullchain.pem" -noout -subject -enddate
echo "done. Now run the SSL install (NGINX_MODE=ssl) — the gateway boots with this cert."
