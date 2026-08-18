#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# freeze_images.sh — save every docker image the platform uses into a gzipped
# archive for airgap transfer (the digitaltwins-images-all.tar.gz that
# airgap_build_step3.yml loads).
#
# Run it on a CONNECTED host once the stack is built and up
# (util/airgap_build_step3.yml -e load_frozen_images=false), then copy the
# archive onto the install-source drive of the airgapped machine.
#
#   util/freeze_images.sh [OUTPUT.tar.gz]
#     OUTPUT defaults to $INSTALL_SRC_DIR/digitaltwins-images-all.tar.gz
#     (INSTALL_SRC_DIR defaults to /mnt/install_src).
#
# Runs from the platform dir so `docker compose` resolves the merged config with
# the live .env. Override with PLATFORM_DIR=.
# ---------------------------------------------------------------------------
set -euo pipefail

PLATFORM_DIR="${PLATFORM_DIR:-$HOME/digitaltwins-platform}"
INSTALL_SRC_DIR="${INSTALL_SRC_DIR:-/mnt/install_src}"
OUT="${1:-$INSTALL_SRC_DIR/digitaltwins-images-all.tar.gz}"

# Helper images used by util/stage-dump.sh & util/portal-restore.sh via
# `docker run --rm` (ephemeral — NOT in the compose stack, so the compose-based
# union below never sees them). Without these in the archive, a restore on the
# airgapped box has no alpine/mc to run. Keep MC_IMAGE in sync with those scripts.
MC_IMAGE="${MC_IMAGE:-quay.io/minio/mc:latest}"
# Override the whole set with e.g. EXTRA_IMAGES="alpine:latest quay.io/minio/mc:latest"
read -r -a extra_imgs <<< "${EXTRA_IMAGES:-alpine:latest $MC_IMAGE}"

cd "$PLATFORM_DIR"

# Union of two sources so nothing is missed:
#   config --images : every image DECLARED in the merged compose (incl. the
#                     jupyter singleuser image, which is a build service).
#   ps -aq → inspect: every image ACTUALLY used by a container, including
#                     exited one-shots (minio-init, singleuser's echo, etc.)
#                     and whatever tag a pull actually resolved.
mapfile -t imgs < <(
  {
    docker compose config --images 2>/dev/null || true
    docker compose ps -aq 2>/dev/null | xargs -r docker inspect --format '{{.Config.Image}}' 2>/dev/null || true
  } | grep -v '^[[:space:]]*$' | sort -u
)

if [ "${#imgs[@]}" -eq 0 ]; then
  echo "freeze_images.sh: found no images — build and start the stack first" >&2
  exit 1
fi

# Fold in the ephemeral helper images. Pull any that are missing (connected
# host), and only include what's actually present so `docker save` can't fail on
# an unavailable tag — warn instead so the freeze still completes.
for im in "${extra_imgs[@]}"; do
  [ -n "$im" ] || continue
  docker image inspect "$im" >/dev/null 2>&1 || docker pull "$im" || true
  if docker image inspect "$im" >/dev/null 2>&1; then
    imgs+=("$im")
  else
    echo "freeze_images.sh: WARNING — helper image '$im' unavailable, skipping (a restore that needs it will fail on the airgapped box)" >&2
  fi
done
mapfile -t imgs < <(printf '%s\n' "${imgs[@]}" | grep -v '^[[:space:]]*$' | sort -u)

echo "freeze_images.sh: saving ${#imgs[@]} images -> $OUT"
printf '  %s\n' "${imgs[@]}"

tmp="$OUT.partial"
docker save "${imgs[@]}" | gzip > "$tmp"
mv "$tmp" "$OUT"

echo "freeze_images.sh: wrote $OUT ($(du -h "$OUT" | cut -f1))"
