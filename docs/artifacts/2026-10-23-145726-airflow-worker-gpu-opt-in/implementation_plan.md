# Implementation plan: make the Airflow worker's GPU opt-in

- **Date:** 2026-10-23
- **Branch:** `feat/airflow-worker-gpu-opt-in`
- **ADR:** [2026-10-23-airflow-worker-gpu-opt-in](../../decisions/2026-10-23-airflow-worker-gpu-opt-in.md) (Accepted)
- **Status:** approved (Option B) and implemented

## Problem

Since `e0c43a24` (2026-09-28), `airflow-worker` in `services/airflow/docker-compose.yml` reserves one
NVIDIA GPU unconditionally. Docker refuses to start a container whose GPU reservation it can't satisfy:

```
Error response from daemon: could not select device driver "nvidia" with capabilities: [[gpu]]
```

So `docker compose up -d`, and with it the step-3 playbook, fails on any host without an NVIDIA GPU and
the NVIDIA Container Toolkit: staging VMs, fresh installs, laptops. This first showed up when a
deployment on pre-2026-09-28 code was upgraded to main.

## Approach (recommended: ADR Option B)

1. **Move the reservation into its own override file.**
   - New `services/airflow/gpu.override.yml` holds only the `airflow-worker` `deploy.resources.reservations.devices` block.
   - Remove that block from the base `services/airflow/docker-compose.yml`. `shm_size` stays in the base: it's harmless without a GPU, and nnUNet on CPU needs it too.
2. **A new setting, `AIRFLOW_WORKER_GPU`, in `env.template`:** `auto` (default), `true` or `false`.
3. **`util/gen-env.sh` resolves it and builds `COMPOSE_FILE`**, through a new sourced helper, `util/lib/compose-file.sh`:
   - `auto` becomes `true` when the host can run NVIDIA containers, otherwise `false`. The check is the same one Docker's `nvidia` device driver depends on: `nvidia-container-runtime-hook` on `PATH`, or an `nvidia` runtime in `docker info`.
   - `COMPOSE_FILE` = `docker-compose.yml`, plus `services/airflow/remote-compute.override.yml` when `REMOTE_COMPUTE=true`, plus `services/airflow/gpu.override.yml` when the resolved GPU setting is `true`.
   - An explicit `COMPOSE_FILE` in the env file still wins, as today.
   - Print the resolved value, e.g. `gen-env.sh: AIRFLOW_WORKER_GPU=auto -> false (no NVIDIA container runtime found)`.
4. **Docs:**
   - `env.template` comment.
   - `util/README.md` step 4 (configure the deployment), next to `REMOTE_COMPUTE`.
   - An upgrade note: a GPU host that should *not* use its GPU sets `AIRFLOW_WORKER_GPU=false`.

Out of scope: the remote compute-worker compose, whose GPU block is already commented out.

## Tests (written first)

`util/tests/test_compose_file.sh`: a plain bash test with no Docker needed. It sources
`util/lib/compose-file.sh` and checks the `COMPOSE_FILE` it resolves, against a stub `PATH` that does or
doesn't provide `nvidia-container-runtime-hook` and a stub `docker`. It also checks that the base Airflow
compose file has no GPU reservation and the override does.

*Changed during implementation:* the plan was to run all of `gen-env.sh` inside the test. The pinned CI
image has bash but no `envsubst`, so the `COMPOSE_FILE` logic moved into the helper, which the test sources
directly. `gen-env.sh` end to end was checked by hand instead (see below). The root `.gitignore`'s generic
Python `lib/` rule also matched `util/lib/`, so it gets a `!util/lib/` exception.

| Case | Expected `COMPOSE_FILE` |
|---|---|
| `auto`, no NVIDIA runtime | `docker-compose.yml` |
| `auto`, hook present | `docker-compose.yml:services/airflow/gpu.override.yml` |
| `auto`, `docker info` lists an `nvidia` runtime | includes the GPU override |
| `true` without a runtime | includes the GPU override (explicit wins) |
| `false` with the hook present | `docker-compose.yml` |
| `REMOTE_COMPUTE=true` + GPU `true` | `docker-compose.yml:services/airflow/remote-compute.override.yml:services/airflow/gpu.override.yml` |
| explicit `COMPOSE_FILE` in the env file | kept as is |
| unknown value (`yes`) | gen-env exits non-zero with a clear message |
| base `services/airflow/docker-compose.yml` | no `driver: nvidia` |
| `services/airflow/gpu.override.yml` | has the reservation |

The test is wired into the root `Makefile` as `test-util` (also part of `make test`) and run in the pinned
throwaway container with `--network none`. CI gets a new `util unit tests` job, filtered on `util/` and the two
Airflow compose files. It isn't one of the required checks.

## Verification beyond the unit test

- `docker compose config airflow-worker` through the root compose file, for `COMPOSE_FILE` = base,
  base + GPU, and base + remote + GPU: the GPU reservation appears only with the override.
- `util/gen-env.sh` run end to end with dummy inputs into a temporary output: `auto` resolves correctly,
  `true` adds the override, an invalid value exits 1 with the message.
- `make test` passes.

## Rollout notes

- A host without a GPU needs no change: `auto` resolves to `false`.
- A GPU host with the NVIDIA Container Toolkit needs no change: `auto` resolves to `true`.
- A host that set `COMPOSE_FILE` by hand, such as staging's temporary no-GPU override, can drop it after this lands.

## Open question for the reviewer

- Which deployments run GPU (nnUNet) inference today? With Option B they keep the GPU automatically if
  the NVIDIA Container Toolkit is installed. With Option A (explicit opt-in, default off) each of them
  must add `AIRFLOW_WORKER_GPU=true` before its next update.

## Checklist

- [x] Plan + ADR approved
- [x] Sync artifacts to docs/artifacts/
- [x] Failing test (`test-util`)
- [x] Implement override file + gen-env.sh logic
- [x] Docs (env.template, util/README.md, docs/testing.md) and CI job
- [x] Sync artifacts to docs/artifacts/
- [x] `make test` / gitleaks
- [x] ADR status → Accepted, task-end ADR check
