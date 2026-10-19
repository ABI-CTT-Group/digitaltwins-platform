#!/usr/bin/env bash
# One-click dataset import (Linux / macOS terminal): measurements, models, tools
# or workflows.
#
# The dataset can live ANYWHERE on this host — just give its path:
#   ./scripts/import-dataset.sh /path/to/mydataset --category measurements            # folder
#   ./scripts/import-dataset.sh /path/to/mydataset.zip --category measurements        # zip
#   ./scripts/import-dataset.sh /path/to/mydataset --category measurements --name X --fhir auto
#   ./scripts/import-dataset.sh /path/to/mymodel --category models --fhir auto
#   ./scripts/import-dataset.sh /path/to/mytool --category tools --tool-type script --seek-project-id 1
#   ./scripts/import-dataset.sh /path/to/myworkflow --category workflows --workflow-type script --seek-project-id 1
#
# The script copies it into the running digitaltwins-api container (with a
# progress bar if `pv` is installed), then runs the importer. You'll sign in
# (admin or researcher). Without --category, it asks for the category first.
set -euo pipefail

# First non-flag arg is the dataset path; the rest pass through to the CLI.
if [ "$#" -ge 1 ] && [ "${1#-}" = "$1" ]; then
  SRC="$1"; shift
else
  read -r -p "Dataset folder or .zip (full path on this machine): " SRC
fi
SRC="${SRC%/}"
[ -e "$SRC" ] || { echo "  ✗ No such path: $SRC" >&2; exit 1; }

CID="$(docker ps -q --filter "label=com.docker.compose.service=digitaltwins-api" | head -n1)"
[ -n "$CID" ] || { echo "  ✗ The digitaltwins-api container is not running." >&2; exit 1; }

# --category is required; ask for it (and a tool's or workflow's options) before the copy.
case " $* " in
  *" --category "*|*" --category="*) ;;
  *)
    read -r -p "Category (measurements, models, tools, workflows): " CATEGORY
    set -- "$@" --category "$CATEGORY"
    if [ "$CATEGORY" = tools ] || [ "$CATEGORY" = workflows ]; then
      read -r -p "Type (script, notebook, gui): " KIND
      read -r -p "SEEK project ID: " PROJECT
      set -- "$@" "--${CATEGORY%s}-type" "$KIND" --seek-project-id "$PROJECT"
    fi ;;
esac

BASE="$(basename "$SRC")"
STAGE_DIR="/dataset_staging/import-staging"
STAGE="$STAGE_DIR/$BASE"

# Fresh staging slot inside the container.
docker exec "$CID" sh -c "rm -rf '$STAGE'; mkdir -p '$STAGE_DIR'"

_src_bytes() {  # GNU du has -b; BSD/macOS du uses -k (KiB)
  if du -sb "$1" >/dev/null 2>&1; then du -sb "$1" | cut -f1
  else du -sk "$1" | awk '{print $1*1024}'; fi
}

if command -v pv >/dev/null 2>&1 && docker exec "$CID" sh -c 'command -v tar >/dev/null 2>&1'; then
  echo "  Copying '$BASE' into the container…"
  tar -C "$(dirname "$SRC")" -cf - "$BASE" \
    | pv -s "$(_src_bytes "$SRC")" \
    | docker exec -i "$CID" tar -C "$STAGE_DIR" -xf -
else
  echo "  Copying '$BASE' ($(du -sh "$SRC" 2>/dev/null | cut -f1)) into the container… (install 'pv' for a live progress bar)"
  docker cp "$SRC" "$CID:$STAGE"
fi

exec docker exec -it "$CID" python -m digitaltwins.cli.import_dataset "$STAGE" --move "$@"
