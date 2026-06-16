#!/usr/bin/env bash
# One-click measurement dataset import for macOS — double-click this file.
#
# A Terminal window opens and asks for the dataset path (folder or .zip, anywhere
# on this Mac). It copies it into the portal-backend container (progress bar if
# `pv` is installed: `brew install pv`), then runs the importer. Sign in (admin)
# via your browser when prompted.
cd "$(dirname "$0")/.."   # -> clinical-dashboard/

if [ "$#" -ge 1 ] && [ "${1#-}" = "$1" ]; then
  SRC="$1"; shift
else
  read -r -p "Dataset folder or .zip (full path): " SRC
fi
SRC="${SRC%/}"
if [ ! -e "$SRC" ]; then
  echo "  ✗ No such path: $SRC"
  read -r -p "Press Enter to close…" _
  exit 1
fi

if docker compose version >/dev/null 2>&1; then DC="docker compose"; else DC="docker-compose"; fi
BASE="$(basename "$SRC")"
STAGE_DIR="/portal_workspace/import-staging"
STAGE="$STAGE_DIR/$BASE"

$DC exec -T portal-backend sh -c "rm -rf '$STAGE'; mkdir -p '$STAGE_DIR'"

_src_bytes() {
  if du -sb "$1" >/dev/null 2>&1; then du -sb "$1" | cut -f1
  else du -sk "$1" | awk '{print $1*1024}'; fi
}

if command -v pv >/dev/null 2>&1 && $DC exec -T portal-backend sh -c 'command -v tar >/dev/null 2>&1'; then
  echo "  Copying '$BASE' into the container…"
  tar -C "$(dirname "$SRC")" -cf - "$BASE" | pv -s "$(_src_bytes "$SRC")" | $DC exec -T portal-backend tar -C "$STAGE_DIR" -xf -
else
  echo "  Copying '$BASE' ($(du -sh "$SRC" 2>/dev/null | cut -f1)) into the container… (brew install pv for a progress bar)"
  $DC cp "$SRC" "portal-backend:$STAGE"
fi

$DC exec -it portal-backend python -m app.cli.import_measurement "$STAGE" "$@"
status=$?

echo
read -r -p "Done (exit $status). Press Enter to close…" _
exit $status
