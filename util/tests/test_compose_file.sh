#!/usr/bin/env bash
# Tests util/lib/compose-file.sh: which compose files gen-env.sh writes into COMPOSE_FILE.
# Run from the repo root (make test-util). Needs only bash and grep. The NVIDIA runtime check
# runs against a stub PATH, so the result doesn't depend on whether this host has a GPU.
set -uo pipefail

LIB=util/lib/compose-file.sh
BASE=docker-compose.yml
REMOTE=services/airflow/remote-compute.override.yml
GPU=services/airflow/gpu.override.yml

T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
mkdir -p "$T/none" "$T/hook" "$T/runtime" "$T/plain-docker"
printf '#!/bin/sh\nexit 0\n' > "$T/hook/nvidia-container-runtime-hook"
printf '#!/bin/sh\necho '"'"'{"io.containerd.runc.v2":{},"nvidia":{"path":"nvidia-container-runtime"}}'"'"'\n' > "$T/runtime/docker"
printf '#!/bin/sh\necho '"'"'{"io.containerd.runc.v2":{},"runc":{}}'"'"'\n' > "$T/plain-docker/docker"
chmod +x "$T/hook/nvidia-container-runtime-hook" "$T/runtime/docker" "$T/plain-docker/docker"

fails=0
# check NAME STUB_DIR EXPECTED [VAR=VALUE ...] — resolve with those settings, compare COMPOSE_FILE.
check() {
  local name=$1 stub=$2 want=$3; shift 3
  local got
  got=$(env -i PATH="$T/$stub" "$@" "$BASH" -c ". $LIB && resolve_compose_file >/dev/null && echo \"\$COMPOSE_FILE\"" 2>&1)
  if [ "$got" = "$want" ]; then echo "ok   $name"; else echo "FAIL $name: want '$want', got '$got'"; fails=$((fails + 1)); fi
}

check "auto, no NVIDIA runtime"                none         "$BASE"
check "auto, no NVIDIA runtime in docker info" plain-docker "$BASE"
check "auto, runtime hook on PATH"             hook         "$BASE:$GPU"
check "auto, nvidia runtime in docker info"    runtime      "$BASE:$GPU"
check "auto set explicitly"                    hook         "$BASE:$GPU"   AIRFLOW_WORKER_GPU=auto
check "true without a runtime"                 none         "$BASE:$GPU"   AIRFLOW_WORKER_GPU=true
check "false with the hook present"            hook         "$BASE"        AIRFLOW_WORKER_GPU=false
check "remote compute, no GPU"                 none         "$BASE:$REMOTE" REMOTE_COMPUTE=true
check "remote compute + GPU"                   none         "$BASE:$REMOTE:$GPU" REMOTE_COMPUTE=true AIRFLOW_WORKER_GPU=true
check "explicit COMPOSE_FILE is kept"          hook         "custom.yml"   COMPOSE_FILE=custom.yml

# An unknown value must fail, not silently pick a default.
out=$(env -i PATH="$T/none" AIRFLOW_WORKER_GPU=yes "$BASH" -c ". $LIB && resolve_compose_file" 2>&1)
if [ $? -ne 0 ] && grep -q 'AIRFLOW_WORKER_GPU' <<<"$out"; then
  echo "ok   unknown AIRFLOW_WORKER_GPU value is rejected"
else
  echo "FAIL unknown AIRFLOW_WORKER_GPU value: want a non-zero exit naming the setting, got '$out'"; fails=$((fails + 1))
fi

# The GPU reservation lives only in the override, so the base stack starts without a GPU.
if grep -q 'driver: nvidia' services/airflow/docker-compose.yml; then
  echo "FAIL services/airflow/docker-compose.yml still reserves an NVIDIA GPU"; fails=$((fails + 1))
else
  echo "ok   base airflow compose has no GPU reservation"
fi
if grep -q 'driver: nvidia' "$GPU" 2>/dev/null; then
  echo "ok   $GPU reserves the GPU"
else
  echo "FAIL $GPU missing or has no GPU reservation"; fails=$((fails + 1))
fi

echo "$fails failure(s)"
[ "$fails" -eq 0 ]
