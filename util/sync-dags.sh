#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# sync-dags.sh — copy Airflow DAGs from one instance to another.
#
# DAGs are deliberately managed OUTSIDE the repo/buildout — the developers
# change them daily — so this is a standalone process, separate from
# stage-dump.sh / portal-restore.sh and from airgap_build_step3.yml (which
# excludes services/airflow/dags from its code sync so it never clobbers them).
#
# Run from a control machine that can ssh to BOTH hosts. The DAG tree is
# streamed as a tar over ssh (SRC -> here -> DST), so SRC and DST do not need
# to reach each other. Additive by default (no deletes); --mirror makes DST an
# exact copy of SRC.
#
#   util/sync-dags.sh <SRC_SSH_HOST> <DST_SSH_HOST> [--mirror]
#     e.g.  util/sync-dags.sh abi_staging abi_portal
#
# Airflow's dag-processor rescans the folder on its own interval, so no restart
# is needed — new/changed DAGs appear within a minute or two.
# ---------------------------------------------------------------------------
set -euo pipefail

SRC="${1:?usage: sync-dags.sh <SRC_SSH_HOST> <DST_SSH_HOST> [--mirror]}"
DST="${2:?usage: sync-dags.sh <SRC_SSH_HOST> <DST_SSH_HOST> [--mirror]}"
MODE="${3:-}"
DAGS_REL="${DAGS_REL:-digitaltwins-platform/services/airflow/dags}"

echo "sync-dags: $SRC:~/$DAGS_REL  ->  $DST:~/$DAGS_REL"
ssh "$SRC" "test -d ~/$DAGS_REL" || { echo "sync-dags: source dags dir missing on $SRC" >&2; exit 1; }
ssh "$DST" "mkdir -p ~/$DAGS_REL"

if [ "$MODE" = "--mirror" ]; then
  echo "  (--mirror: removing DST-only files first)"
  ssh "$DST" "rm -rf ~/$DAGS_REL/* ~/$DAGS_REL/.[!.]* 2>/dev/null || true"
elif [ -n "$MODE" ]; then
  echo "sync-dags: unknown option '$MODE' (only --mirror)" >&2; exit 2
fi

ssh "$SRC" "tar -C ~/$DAGS_REL -cf - ." | ssh "$DST" "tar -C ~/$DAGS_REL -xf -"

echo "sync-dags: done. $DST now has:"
ssh "$DST" "cd ~/$DAGS_REL && find . -name '*.py' | sort"
