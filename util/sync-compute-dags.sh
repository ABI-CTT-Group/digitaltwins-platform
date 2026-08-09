#!/usr/bin/env bash
# Sync the Airflow DAGs (+ plugins + config) from the portal to a remote compute
# node, so the node's Celery worker runs the SAME code the portal's scheduler
# parses. Run this ON THE PORTAL whenever the DAGs change — they're managed
# outside the repo and edited often, and a remote worker only sees what's in its
# own dags/ folder.
#
#   util/sync-compute-dags.sh <node_ssh_dest> [--delete]
#     e.g.  util/sync-compute-dags.sh 10.2.0.14
#           util/sync-compute-dags.sh ubuntu@10.2.0.14 --delete
#
# --delete MIRRORS the node to the portal (removes node files no longer present
# on the portal) — OFF by default, since it also prunes anything the node kept
# locally. Use it when you want a DAG deleted on the portal to disappear on the
# node too.
#
# Paths are overridable via env:
#   SRC_AIRFLOW  portal-side airflow dir   (default ~/digitaltwins-platform/services/airflow)
#   DST_COMPUTE  node-side compute dir     (default digitaltwins-compute, i.e. the node's ~/digitaltwins-compute)
#
# The worker re-parses each DAG file per task run, so NO worker restart is needed
# after a sync — but new DAGs still boot PAUSED; un-pause them to run.
set -euo pipefail

NODE="${1:?usage: sync-compute-dags.sh <node_ssh_dest> [--delete]}"
DELETE=""
if [ "${2:-}" = "--delete" ]; then
  DELETE="--delete"
elif [ -n "${2:-}" ]; then
  echo "sync-compute-dags: unknown arg '$2' (only --delete is accepted)" >&2
  exit 2
fi

SRC_AIRFLOW="${SRC_AIRFLOW:-$HOME/digitaltwins-platform/services/airflow}"
DST_COMPUTE="${DST_COMPUTE:-digitaltwins-compute}"   # relative -> the node's home

[ -d "$SRC_AIRFLOW" ] || { echo "sync-compute-dags: no such dir: $SRC_AIRFLOW" >&2; exit 1; }

for sub in dags plugins config; do
  src="$SRC_AIRFLOW/$sub/"
  if [ ! -d "$src" ]; then
    echo "-- skip $sub (no $src)"
    continue
  fi
  echo ">> $sub -> $NODE:$DST_COMPUTE/$sub/"
  # Trailing slashes matter: copy the CONTENTS of each subdir into the matching
  # node subdir (never flatten them all into one dir).
  rsync -a $DELETE \
    --exclude='__pycache__/' --exclude='*.pyc' \
    "$src" "$NODE:$DST_COMPUTE/$sub/"
done

echo "done — worker re-parses per task (no restart); remember to un-pause any new DAGs."
