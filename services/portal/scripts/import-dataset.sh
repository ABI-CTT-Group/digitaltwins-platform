#!/usr/bin/env bash
# One-click measurement dataset import (Linux / macOS terminal).
#
#   1) Drop your dataset folder into  clinical-dashboard/measurement-import/
#   2) Run:  ./scripts/import-dataset.sh   (add a folder name to skip the picker)
#
# You'll be asked to sign in (admin) via your browser, then it imports the dataset
# end-to-end (upload + push to FHIR) and shows it in the portal as completed.
set -euo pipefail
cd "$(dirname "$0")/.."   # -> clinical-dashboard/

# Use `docker compose` (v2); fall back to `docker-compose` if that's what's installed.
if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
else
  DC="docker-compose"
fi

exec $DC exec -it portal-backend python -m app.cli.import_measurement "$@"
