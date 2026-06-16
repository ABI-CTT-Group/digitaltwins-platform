#!/usr/bin/env bash
# One-click measurement dataset import for macOS — double-click this file.
#
#   1) Drop your dataset folder into  clinical-dashboard/measurement-import/
#   2) Double-click this file (import-dataset.command). A Terminal window opens.
#   3) Sign in (admin) via your browser when prompted.
#
# (Same as import-dataset.sh, but pauses at the end so the window stays open.)
cd "$(dirname "$0")/.."   # -> clinical-dashboard/

if docker compose version >/dev/null 2>&1; then
  DC="docker compose"
else
  DC="docker-compose"
fi

$DC exec -it portal-backend python -m app.cli.import_measurement "$@"
status=$?

echo
read -r -p "Done (exit $status). Press Enter to close…" _
exit $status
