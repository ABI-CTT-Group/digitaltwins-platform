# shellcheck shell=bash
# ---------------------------------------------------------------------------
# compose-file.sh — which compose files the stack merges. Sourced by
# util/gen-env.sh, which writes the result into .env as COMPOSE_FILE, so the
# systemd unit, the playbook and operators' `docker compose` all merge the same
# files. Tested by util/tests/test_compose_file.sh.
#
#   REMOTE_COMPUTE=true       adds services/airflow/remote-compute.override.yml
#   AIRFLOW_WORKER_GPU=auto   adds services/airflow/gpu.override.yml when this
#                             host can run NVIDIA containers (default)
#   AIRFLOW_WORKER_GPU=true   always adds it; false never does
#
# A COMPOSE_FILE already set in the env inputs file wins over both.
# See docs/decisions/2026-10-23-airflow-worker-gpu-opt-in.md.
# ---------------------------------------------------------------------------

# Docker registers its `nvidia` device driver only when nvidia-container-runtime-hook
# is on PATH; `nvidia-ctk runtime configure` instead adds an `nvidia` runtime.
nvidia_container_runtime_available() {
  command -v nvidia-container-runtime-hook >/dev/null 2>&1 && return 0
  local runtimes
  runtimes=$(docker info --format '{{json .Runtimes}}' 2>/dev/null) || return 1
  [[ $runtimes == *'"nvidia"'* ]]
}

resolve_compose_file() {
  local gpu=${AIRFLOW_WORKER_GPU:-auto} why
  case "$gpu" in
    auto)
      if nvidia_container_runtime_available; then
        gpu=true; why="NVIDIA container runtime found"
      else
        gpu=false; why="no NVIDIA container runtime found"
      fi ;;
    true|false) why="set explicitly" ;;
    *)
      echo "gen-env.sh: AIRFLOW_WORKER_GPU must be auto, true or false (got '$gpu')" >&2
      return 1 ;;
  esac

  if [ -n "${COMPOSE_FILE:-}" ]; then
    echo "gen-env.sh: COMPOSE_FILE is set in the env inputs; using it as is"
    return 0
  fi
  COMPOSE_FILE=docker-compose.yml
  if [ "${REMOTE_COMPUTE:-false}" = "true" ]; then
    COMPOSE_FILE="$COMPOSE_FILE:services/airflow/remote-compute.override.yml"
  fi
  if [ "$gpu" = "true" ]; then
    COMPOSE_FILE="$COMPOSE_FILE:services/airflow/gpu.override.yml"
  fi
  echo "gen-env.sh: AIRFLOW_WORKER_GPU=${AIRFLOW_WORKER_GPU:-auto} -> $gpu ($why)"
}
