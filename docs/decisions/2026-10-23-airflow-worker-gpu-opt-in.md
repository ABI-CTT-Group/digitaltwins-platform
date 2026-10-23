# Airflow worker GPU is opt-in, detected automatically

- **Date:** 2026-10-23
- **Status:** Accepted

## Context

`e0c43a24` (2026-09-28) gave `airflow-worker` an unconditional reservation of one NVIDIA GPU, so that
nnUNet inference tasks can use it. Docker refuses to start a container whose device reservation it
can't satisfy (`could not select device driver "nvidia"`). Since then the platform no longer starts on
any host without an NVIDIA GPU and the NVIDIA Container Toolkit: staging VMs, fresh installs, laptops.
The base compose file can't express "use a GPU if there is one".

The platform already chooses optional compose files in one place: `util/gen-env.sh` writes
`COMPOSE_FILE` into `.env` from `REMOTE_COMPUTE`, so the playbook, the systemd unit and operators all
merge the same files.

## Alternatives Considered

### Option A: explicit opt-in flag, default off
`AIRFLOW_WORKER_GPU=true|false` (default `false`). `gen-env.sh` adds `services/airflow/gpu.override.yml`
to `COMPOSE_FILE` when it's `true`.
- Pros: simplest; no host probing; behaviour is visible in the env file.
- Cons: every GPU host silently loses its GPU on its next update until someone sets the flag. nnUNet
  then runs on CPU or fails.

### Option B: opt-in flag with automatic detection (default `auto`)
As Option A, but the default `auto` resolves to `true` when the host can run NVIDIA containers:
`nvidia-container-runtime-hook` on `PATH`, which is what Docker's `nvidia` device driver needs, or an
`nvidia` runtime listed by `docker info`. `true`/`false` override the detection.
- Pros: no configuration on either kind of host; GPU hosts keep their GPU across the upgrade; still
  explicit when needed.
- Cons: about 10 lines of detection in `gen-env.sh`. The result depends on the host `gen-env.sh` runs
  on, which is the deployment host itself in the playbook (`-c local`). A host with the toolkit but no
  working GPU would resolve to `true` and fail as before; `false` fixes that.

### Option C: opt-out flag, default on
Keep the GPU by default; hosts without one set `AIRFLOW_WORKER_GPU=false`.
- Pros: no change for existing GPU hosts.
- Cons: the common case (no GPU) needs configuration, and every fresh install fails first.

### Option D: per-host compose override, no repo change
Each host without a GPU keeps its own override that resets the reservation (`devices: !reset []`) and
sets `COMPOSE_FILE` in its env file.
- Pros: no code change.
- Cons: every non-GPU host has to discover the failure and repeat the workaround; the repo default
  stays broken for them.

## Decision

Option B. It fixes non-GPU hosts without breaking GPU hosts, and it follows the existing
`REMOTE_COMPUTE` → `COMPOSE_FILE` pattern. An explicit `COMPOSE_FILE` in the env file still takes
precedence, so existing hand-set values keep working.

## Consequences

- The GPU reservation lives in `services/airflow/gpu.override.yml`; the base compose no longer
  mentions NVIDIA. `shm_size` stays in the base.
- Running `docker compose -f docker-compose.yml …` by hand on a GPU host skips the GPU; `.env`'s
  `COMPOSE_FILE` is the supported path, as it already is for remote compute.
- `gen-env.sh` must run on the host that will run the stack for `auto` to mean anything. That's true
  for the playbook and for the documented manual steps.
- The `COMPOSE_FILE` logic lives in `util/lib/compose-file.sh`, sourced by `gen-env.sh`, so it can be
  unit-tested (`make test-util`) without `envsubst`. The next optional compose file is another branch there.
