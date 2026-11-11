# GPU inference for `workflow_39` — what was done and verified

Outcome of the plan in [implementation_plan.md](implementation_plan.md). Executed 2026-09-18 on
the portal host (`bn471493`).

**Result: `workflow_39` runs nnUNet inference on the local GPU.** A full DAG run finished
`success`, with `skin_inference` executing on `cuda:0` and outputs uploaded to MinIO.

## Changes made

| File | Change |
|---|---|
| `/etc/docker/daemon.json` (host) | `nvidia` runtime registered via `nvidia-ctk`. Backup at `daemon.json.bak`. |
| `services/airflow/docker-compose.yml` | GPU device reservation on the `airflow-worker` service only |
| `services/airflow/Dockerfile` | `boto3` moved out of the torch layer into its own trailing layer |
| `services/airflow/dags/tool/tool_inference.py` | New `_resolve_device()`; `device="auto"` default; fork patch now applies on CUDA; device line printed rather than logged |
| `services/airflow/dags/workflow_inference.py` | `resolve_conf` device default `"cpu"` → `"auto"` |
| `services/airflow/dags/tool/tests/test_tool_inference.py` | 3 new `_resolve_device` tests; CUDA fork test inverted |

> **The two DAG/tool files are gitignored** (`.gitignore:194` → `services/airflow/dags/*`), so
> those edits are not under version control. `git add -f` is needed to keep them.

## Verified

| Check | Result |
|---|---|
| `nvidia` runtime registered | `docker info` lists it; `data-root` and `default-address-pools` survived the `nvidia-ctk` rewrite |
| Platform intact after daemon restart | All 23 containers returned, none unhealthy |
| `torch.cuda.is_available()` in the worker | `True` — was `False` before (the red→green gate) |
| Blackwell kernel support | Device is `sm_120`; `sm_120` present in `torch.cuda.get_arch_list()`; a device matmul succeeded |
| Unit tests | 6 passed (4 were failing first) |
| `device="auto"` resolves to CUDA with **no** `device` conf key | Confirmed — the trigger conf deliberately omitted it, mirroring what the API sends |
| GPU actually used | `nnunet_venv/bin/python` held 7160 MiB at 100% utilisation |
| Fork, not spawn, on the CUDA path | Child processes share the parent's cmdline; no `spawn_main` bootstrap children |
| DAG run completes | `dag_run.state = success`; `skin_inference` `success` in **35 m 11 s** |
| Outputs in MinIO | `image.nii.gz` (37 KB) + `image.npz` (826 KB) + metadata, 6 objects under `workflow_39/gputest2/outputs/` |

The fork-on-CUDA change was the plan's one reasoned-but-unobserved assumption. It held: the run
passed pool creation and reached sustained GPU compute, and the documented subprocess fallback
was not needed.

## Deviations from the plan

**1. `boto3` was missing from `nnunet_venv` — the first trigger failed in 0.14 s.**

Not GPU-related. The image (built ~3 h earlier) came from a torch layer reading

```
pip install torch torchvision torchaudio --extra-index-url .../cu130;
```

while the working-tree Dockerfile had since appended `&& pip install boto3` to *that same
layer*, which was never rebuilt. Rebuilding as written would have invalidated the 5.8 GB torch
layer and the 6.78 GB private-repo layer.

Fix: `boto3` now installs in its own `RUN` **after** both heavy layers, so it can be added or
bumped without touching their cache. The rebuild hit cache and took 106 s instead of
re-downloading several GB. The earlier 45-minute CPU run presumably worked because `boto3` had
been pip-installed into the running container by hand; recreating the container for the GPU
reservation wiped that, which is exactly why baking it into the image was the right fix.

**2. The device confirmation line never reached the Airflow task log.**

`log.info("Running inference with device=...")` produced nothing, because
`ExternalPythonOperator` runs the callable in a subprocess with no logging configuration — only
stdout reaches the task log (which is why nnUNet's own `print()` calls were visible and this
line was not). Changed to `print(..., flush=True)`. Device confirmation for this run therefore
came from `nvidia-smi` and process inspection rather than the log.

## Corrections to the plan's assumptions

* **VRAM is tight, not comfortable.** The plan reasoned that `perform_everything_on_gpu=False`
  would keep GPU memory per-patch. It does — the log confirms `perform_everything_on_gpu: False`,
  and the parameter name is correct for this nnUNet version — but the run still sat at
  7160 MiB of 8151 MiB (88%) and emitted a non-fatal allocator warning on *every* iteration:

  ```
  expandable_segments: memory mapping failed with OOM on device 0
  while trying to map 20971520 bytes (free: 9175040, total: 8082423808)
  ```

  About 8.7 MiB free of 7.5 GiB. It completed successfully, but there is almost no headroom
  beside the desktop session's ~135 MiB.

* **No CPU speedup figure can be quoted.** The plan's third success criterion was "wall-clock
  materially below the CPU baseline". There is no successful CPU run to compare against — the
  prior CPU attempt ran 45 minutes and then failed. GPU wall-clock is 35 m 11 s; treat that as
  an absolute number, not a speedup.

## Open items

* **35 minutes per model is dominated by the 5-fold ensemble.** `use_folds=None`
  auto-detects every available fold (`[0, 1, 2, 3, 4]`), so the sliding window runs five times
  at ~6.5 s/iteration × 64 patches. Restricting to a single fold would be roughly 5× faster, but
  that is a model-semantics decision, not a configuration one.
* **`PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`** (set in `tool_inference.py`) is what
  emits the per-iteration warnings. On a GPU this close to its ceiling it may be doing more harm
  than good; worth measuring with it off.
* **Only `skin` runs.** The other three models remain commented out in `INFERENCE_MODELS`, and
  all four `assay_input` rows still point at the one `model_sds_skin` dataset. With the models
  running sequentially, enabling all four implies roughly 4× the wall-clock.
* **Untracked files** — see the note above about `.gitignore:194`.
* **Not done:** the airgap/ansible install path for `nvidia-container-toolkit`, and the remote
  GPU compute node. Both were out of scope.
