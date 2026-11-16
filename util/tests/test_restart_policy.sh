#!/usr/bin/env bash
# Every long-running service uses `restart: unless-stopped`, so it comes back after a crash or a
# reboot but stays down if an operator stopped it. One-shot jobs must not: unless-stopped restarts a
# container that exits cleanly, so an init job would re-run forever.
# See docs/decisions/2026-11-17-restart-policy-unless-stopped.md.
# Run from the repo root (make test-util). Needs only bash, find and awk.
set -uo pipefail

ONE_SHOTS=" airflow-init airflow-cli minio-init minio-logs-init singleuser "

# Override files only patch services defined elsewhere; the SEEK submodule is a separate repo.
files=$(find services -name '*compose*.yml' ! -name '*override*' ! -path 'services/seek/ldh-deployment/*' | sort)
if [ -z "$files" ]; then echo "FAIL no compose files found under services/"; exit 1; fi

fails=0
while IFS=$'\t' read -r file svc policy; do
  if [[ "$ONE_SHOTS" == *" $svc "* ]]; then
    if [ "$policy" = "unless-stopped" ]; then
      echo "FAIL $file $svc: one-shot job must not use unless-stopped"; fails=$((fails + 1))
    fi
  elif [ "$policy" = "unless-stopped" ]; then
    echo "ok   $file $svc"
  else
    echo "FAIL $file $svc: want restart: unless-stopped, got '$policy'"; fails=$((fails + 1))
  fi
done < <(for f in $files; do
  # Print "file<TAB>service<TAB>restart" for each service under the top-level services: key.
  awk -v F="$f" '
    function emit() { if (svc != "") printf "%s\t%s\t%s\n", F, svc, (pol == "" ? "none" : pol) }
    /^services:/ { in_s = 1; next }
    /^[^ #]/     { if (in_s) emit(); in_s = 0; svc = ""; next }
    in_s && /^  [A-Za-z0-9_.-]+:[[:space:]]*$/ { emit(); svc = $1; sub(/:$/, "", svc); pol = ""; next }
    in_s && /^    restart:/ { pol = $2; gsub(/"/, "", pol) }
    END { if (in_s) emit() }
  ' "$f"
done)

echo "$fails failure(s)"
[ "$fails" -eq 0 ]
