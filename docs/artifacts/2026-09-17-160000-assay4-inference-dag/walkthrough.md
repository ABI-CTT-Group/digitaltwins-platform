# Walkthrough — Assay 4 Initial Inference DAG

## Summary

This session covered two phases:
1. **DAG & tool implementation** (previous session): Created `workflow_39` Airflow DAG and `tool_inference.py` for nnUNet segmentation inference, based on the CWL workflow in [assay_4_initial_inference](file:///home/clin864/Projects/digitaltwins-platform/my_workspace/pilot-2/Breast/assay_4_initial_inference).
2. **Deployment & build setup** (this session): Resolved the Airflow Docker build so it can install the `nnunet_venv` with private GitHub dependencies.

---

## Files Created / Modified

### [NEW] [tool_inference.py](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/tool/tool_inference.py)

Reusable tool module following the same MinIO download/upload pattern as existing tools:

- **MinIO helpers**: `_get_s3_client()`, `_download_prefix()`, `_upload_file()`, `_upload_directory()`
- **`_find_source_bucket()`**: Locates which MinIO bucket contains a model dataset by UUID
- **`_download_model()`**: Downloads model weights from SDS dataset, using hardcoded trainer subpath `primary/nnUNetTrainer__nnUNetPlans__3d_fullres`
- **`_run_inference()`**: Core inference logic adapted from [inference.py](file:///home/clin864/Projects/digitaltwins-platform/my_workspace/pilot-2/Breast/assay_4_initial_inference/inference.py) — sets up nnUNet env vars, instantiates `nnUNetPredictor`, auto-detects checkpoint, handles single-file and directory input modes
- **`run()`**: Main entry-point: downloads NIfTI input → downloads model → runs inference → uploads all outputs (`.nii.gz` + `.npz`)

### [NEW] [workflow_inference.py](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/workflow_inference.py)

Airflow DAG mirroring the structure of [workflow_image_conversion.py](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/workflow_image_conversion.py):

- **`resolve_conf`** task: Extracts standard + inference-specific fields from `dag_run.conf`
- **`download_samples`** task: Downloads NIfTI input via `cwl_venv`
- **4 sequential inference tasks**: `skin_inference` → `outer_rib_inference` → `sternum_inference` → `lesion_inference`, each using `nnunet_venv`
- Model dataset UUIDs passed via conf keys: `skin_model_dataset_uuid`, `outer_rib_model_dataset_uuid`, `sternum_model_dataset_uuid`, `lesion_model_dataset_uuid`

### [MODIFIED] [Dockerfile](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/Dockerfile)

- Updated commit SHA for `nnUNet-ranking-inference-extension` from `2405c74...` → `1cb0b4b...` (the previous commit was force-pushed off the remote)

### [MODIFIED] [services/airflow/docker-compose.yml](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/docker-compose.yml)

- Changed `build: .` to a full `build:` block with `context` and `secrets` so Docker Compose can inject the `github_token` secret at build time
- Added a top-level `secrets:` definition using `environment: "GITHUB_TOKEN"` — this means the secret is optional (skipped gracefully if `GITHUB_TOKEN` is unset), so standard builds without `INSTALL_NNUNET=true` continue to work for all developers

### [NEW] [build_airflow_nnunet.md](file:///home/clin864/Projects/digitaltwins-platform/docs/artifacts/2026-09-17-160000-assay4-inference-dag/build_airflow_nnunet.md)

Step-by-step instructions for building the Airflow image with the `nnunet_venv` installed.

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Sequential model execution | GPU memory safety — nnUNet is memory-intensive |
| Separate `nnunet_venv` | Isolates heavy ML deps (torch, nnunetv2) from `cwl_venv` |
| `download_samples` uses `cwl_venv` | Only needs boto3, no ML deps |
| `environment: "GITHUB_TOKEN"` for secret | Token is optional — standard builds without nnUNet don't need it |
| Hardcoded trainer subpath | Simplifies initial implementation; can be parameterised later |
| Upload both `.nii.gz` + `.npz` | Preserves probability maps for downstream uncertainty analysis |

---

## Build Command (with nnUNet)

```bash
# One-time setup
mkdir -p ~/.secrets
echo "ghp_your_token_here" > ~/.secrets/github_token
chmod 600 ~/.secrets/github_token

# Build
GITHUB_TOKEN=$(cat ~/.secrets/github_token) DOCKER_BUILDKIT=1 docker compose build \
  --build-arg INSTALL_NNUNET=true

# Restart services
docker compose up -d
```

---

## Verification

- ✅ `tool_inference.py` — syntax check passed
- ✅ `workflow_inference.py` — syntax check passed
- ✅ Docker build (without `INSTALL_NNUNET`) — passes cleanly for all developers
- ✅ Docker build (with `INSTALL_NNUNET=true`) — completed successfully
- ✅ `docker compose up -d` — services restarted with `nnunet_venv` available
- ⏳ End-to-end test requires valid model/input datasets uploaded to MinIO and DAG triggered with correct conf

---

## Next Session

- **`assays.py` changes**: Pass model dataset UUIDs in the DAG `conf` payload when the assay is triggered from the portal. This removes the need to manually specify the 4 model UUIDs in the DAG trigger conf.
