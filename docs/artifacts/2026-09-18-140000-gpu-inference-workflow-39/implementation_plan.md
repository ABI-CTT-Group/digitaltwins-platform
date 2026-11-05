# Run `workflow_39` inference on the local GPU

SEEK assay 39 (`workflow_39` / `workflow_inference`) currently runs nnUNet segmentation on
CPU. This plan moves it onto this host's GPU, on the local Airflow Celery worker.

Scope agreed in the interview: **one-off dev validation** — the smallest set of changes that
gets a GPU run working and verified on this box. Deployment/airgap packaging is explicitly out
of scope.

## Decisions

| Decision | Choice |
|---|---|
| Where inference runs | Local `digitaltwins-platform-airflow-worker-1` on this host |
| How `device=cuda` is selected | Auto-detect inside `tool_inference.py` (`device="auto"` default) |
| Host changes | Yes — install `nvidia-container-toolkit`, restart the Docker daemon |
| Scope | One-off dev validation |

### Why auto-detect rather than a conf key

The API's DAG-run conf is a **closed key set**. `payload_conf` in
`services/api/digitaltwins-api/app/routers/assays.py` is hardcoded; the only dynamic keys are
`{name}_dataset_uuid` from model-category assay inputs. There is no free-form params column on
the `assay` table and no pass-through from SEEK, so a portal-triggered run of assay 39 can
never carry `"device": "cuda"` without an API + schema change.

`resolve_conf` already reads `device`/`gpu_id`
([workflow_inference.py:229-230](../../../services/airflow/dags/workflow_inference.py#L229-L230)),
but nothing ever sends them, so it always falls back to `cpu`. Auto-detection in the tool
sidesteps the whole API change: the worker's hardware decides, and the same DAG still runs on a
CPU-only worker.

## Verified starting state (2026-09-18)

| Item | State |
|---|---|
| Host GPU | NVIDIA RTX PRO 2000 Blackwell, 8151 MiB, driver 580.178.04, CUDA 13.0 |
| Docker runtimes | `runc` only — **no `nvidia` runtime registered** |
| `/etc/docker/daemon.json` | Custom `data-root: /home/clin864/docker`, `default-address-pools: 100.64.0.0/16`. No runtime config. |
| `nnunet_venv` in the worker | Present; `torch 2.14.0+cu130` (CUDA 13.0) |
| `torch.cuda.is_available()` in the worker | **False** — this is the gate to flip |
| Worker `shm_size` | Already `2gb` ([docker-compose.yml:252](../../../services/airflow/docker-compose.yml#L252)) |
| Models active | Only `skin`; the other three are commented out at [workflow_inference.py:62-67](../../../services/airflow/dags/workflow_inference.py#L62-L67) |

### The non-obvious blocker: `spawn` on the CUDA path

[`_use_fork_for_nnunet_pools`](../../../services/airflow/dags/tool/tool_inference.py#L162)
redirects nnUNet's hardcoded `spawn` pools to `fork`, because `ExternalPythonOperator`'s
generated wrapper script has no `if __name__ == "__main__":` guard and `spawn`'s bootstrap check
therefore refuses to start a worker. Line 178 **skips that patch when the device is CUDA**, on
the general principle that forking after CUDA initialisation is unsafe. The consequence is that
the CUDA path reinstates the exact `spawn` failure the patch exists to prevent. The CPU path has
been exercised; the CUDA path has not.

Evidence gathered for this plan (all read from the running worker's installed nnUNet):

* The Airflow wrapper template invokes the callable at module top level — confirmed, no
  `__main__` guard.
* nnUNet creates spawn pools at `inference/data_iterators.py:69`, `:268`, and
  `inference/predict_from_raw_data.py:349`.
* The first CUDA primary context is created at `predict_from_raw_data.py:587`
  (`self.network = self.network.to(self.device)`), which runs **after** all three pool
  creations — and the pool children only do CPU preprocessing and segmentation export; they
  never touch CUDA.

So forking on the CUDA path should be safe here, and the early return at line 178 should go.
This is an argument from code ordering, not an observation, so Phase 3 treats it as a
hypothesis with a documented fallback.

---

## Phase 1 — Register the NVIDIA container runtime with Docker (host, sudo)

**1.1** Install the toolkit:

```bash
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
  | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
  | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
  | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update && sudo apt-get install -y nvidia-container-toolkit
```

**1.2** Back up `daemon.json`, then register the runtime. `nvidia-ctk` rewrites the file, and
this host's copy carries a non-default `data-root` and address pools that must survive:

```bash
sudo cp /etc/docker/daemon.json /etc/docker/daemon.json.bak
sudo nvidia-ctk runtime configure --runtime=docker
sudo cat /etc/docker/daemon.json     # confirm data-root + default-address-pools still present
```

> **Verify:** `data-root` is still `/home/clin864/docker` and `default-address-pools` still
> `100.64.0.0/16`. If either is gone, restore from `.bak` and merge the `runtimes` block by hand
> before restarting. Losing `data-root` would point Docker at a different image store.

**1.3** Restart the daemon. **This stops every container on this box, including the whole
platform.** Bring it back afterwards:

```bash
sudo systemctl restart docker
docker info | grep -iA2 -i runtimes    # expect: nvidia
```

> **Verify:** `docker info` lists `nvidia` under Runtimes.

## Phase 2 — Give the Airflow worker the GPU

**2.1** Edit `services/airflow/docker-compose.yml`, in the `airflow-worker` service only —
alongside the existing `shm_size` at line 252, *not* in the `x-airflow-common` anchor. The
scheduler, apiserver, triggerer and dag-processor don't execute tasks and don't need a GPU.

```yaml
  airflow-worker:
    <<: *airflow-common
    command: celery worker
    shm_size: '2gb'
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

**2.2** Recreate the worker (no image rebuild needed — `nnunet_venv` with `cu130` torch is
already in the image):

```bash
docker compose up -d airflow-worker
```

> **Verify — this is the red→green gate.** The same command returns `False` today:
> ```bash
> docker exec digitaltwins-platform-airflow-worker-1 \
>   /opt/airflow/venvs/nnunet_venv/bin/python -c \
>   "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name(0))"
> ```
> Expect `True NVIDIA RTX PRO 2000 Blackwell ...`.
>
> Blackwell is `sm_120`; if torch reports a "no kernel image" or unsupported-capability
> warning here, the `cu130` wheel lacks `sm_120` kernels and the venv needs rebuilding against
> a newer wheel. Check before moving on.

## Phase 3 — Auto device selection in the tool (TDD)

Tests live in
[`services/airflow/dags/tool/tests/test_tool_inference.py`](../../../services/airflow/dags/tool/tests/test_tool_inference.py).

**3.1 — Red.** Write the failing tests first:

* `_resolve_device("auto")` → `"cuda"` when `torch.cuda.is_available()` is monkeypatched True,
  `"cpu"` when False.
* `_resolve_device("cpu")` and `_resolve_device("cuda")` pass through unchanged.
* **Invert the existing `test_use_fork_for_nnunet_pools_leaves_cuda_untouched`** into
  `test_use_fork_for_nnunet_pools_patches_get_context_on_cuda`. That test currently asserts the
  behaviour this plan removes, so it must be rewritten, not merely added to.

**3.2 — Green.** In `tool_inference.py`:

* Add `_resolve_device(device: str) -> str`, resolving `"auto"` against
  `torch.cuda.is_available()`.
* Default `device="auto"` on both
  [`_run_inference`](../../../services/airflow/dags/tool/tool_inference.py#L186) and
  [`run`](../../../services/airflow/dags/tool/tool_inference.py#L294), and call the resolver
  before the existing `if device == "cuda":` branch so the explicit-CUDA
  `RuntimeError("CUDA was requested but no CUDA device is available.")` still fires when a
  caller asks for CUDA by name. `"auto"` must degrade to CPU, never raise.
* Delete the `if device_type == "cuda": return` early return at
  [line 178](../../../services/airflow/dags/tool/tool_inference.py#L178) and replace the
  docstring's fork-safety paragraph with the ordering argument recorded above.

**3.3** In `workflow_inference.py`, change the default at
[line 229](../../../services/airflow/dags/workflow_inference.py#L229) from `"cpu"` to
`"auto"`. An explicit `{"device": "cpu"}` in a manual trigger conf still wins.

> **Verify:** `pytest services/airflow/dags/tool/tests/test_tool_inference.py` passes.

**Fallback if Phase 4 shows the fork change was wrong.** If the run dies with a CUDA
initialisation or fork error rather than the `spawn` bootstrap error, restore the early return
and instead have the operator shell out: `tool_inference.py` already carries a
`__main__`-guarded CLI at the bottom of the file, and running it as a subprocess makes `spawn`
legal. That CLI currently covers only `_run_inference`, so it would need a mode that does the
MinIO download/upload too. Larger change — only take it if the simple one fails.

## Phase 4 — Run assay 39 end to end

**4.1** Trigger from the portal (`POST /assays/39/run`). No conf change is needed: `device`
now defaults to `auto` and the worker resolves it to CUDA.

**4.2** While it runs:

```bash
watch -n1 nvidia-smi
docker compose logs -f airflow-worker
```

> **Verify:** `nvidia-smi` shows a `python` process holding VRAM, and the `skin_inference` task
> log prints `Running inference with device=cuda:0`.

**4.3** Confirm `.nii.gz` and `.npz` outputs land in MinIO under the resolved output prefix for
assay 39's SDS output dataset.

### Success criteria

1. `torch.cuda.is_available()` is `True` inside the worker container.
2. `pytest services/airflow/dags/tool/tests/test_tool_inference.py` passes.
3. `skin_inference` completes on `cuda:0`, with wall-clock materially below the CPU baseline.
4. Outputs are present in MinIO.

## Risks

* **8 GB of VRAM, shared with your desktop.** Xorg and `gnome-remote-desktop-daemon` hold about
  135 MiB. `perform_everything_on_gpu=False`
  ([tool_inference.py:239](../../../services/airflow/dags/tool/tool_inference.py#L239)) keeps
  the aggregated logits on CPU, so GPU memory is per-patch and should fit comfortably. If it
  OOMs anyway, fall back to an explicit `{"device": "cpu"}` conf for that run rather than
  tuning nnUNet.
* **The Docker daemon restart takes the whole platform down** for the duration.
* **`nvidia-ctk` rewriting `daemon.json`** — mitigated by the backup and the explicit check in
  step 1.2.
* **The fork-on-CUDA change is reasoned, not observed.** Phase 4 is where it gets tested;
  Phase 3 records the fallback.

## Explicitly out of scope

* Sending `device`/`gpu_id` from the API or SEEK assay config. That needs a schema change
  (a `params jsonb` column on `assay`, or a dedicated field threaded through
  `AssayDataModel` → `configure_assay` → `_fetch_assay_configs` → `payload_conf`).
* The remote GPU compute node. `services/airflow/compute-worker/docker-compose.yml` already has
  a commented-out GPU block and would work the same way, driven by the `compute_queue` Airflow
  Variable — but that is a second machine and a separate exercise.
* Installing `nvidia-container-toolkit` through the airgap/ansible path
  (`util/airgap_build_step3.yml`).
* Re-enabling the `outer_rib`, `sternum` and `lesion` models. Only `skin` runs today; that is
  unrelated to GPU work.
