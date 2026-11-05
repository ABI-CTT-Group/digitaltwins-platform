# Airflow DAG for Assay 4 — Initial Inference

Create an Airflow 3 DAG (`workflow_39`) that runs nnUNet segmentation inference on a NIfTI MRI image using 4 pre-trained models (skin, outer_rib, sternum, lesion), following the patterns established by `workflow_image_conversion` (workflow_38).

## Design Decisions (from interview)

| Decision | Choice |
|---|---|
| DAG ID | `workflow_39` (SEEK workflow ID 39, assay ID 39) |
| Model execution order | **Sequential** (GPU memory safety) |
| Model provisioning | Downloaded from MinIO via model dataset UUIDs (passed in conf) |
| Model trainer subpath | Hardcoded for now: `primary/nnUNetTrainer__nnUNetPlans__3d_fullres` |
| NIfTI input source | Downloaded from measurement dataset via `download_samples` step |
| Execution strategy | `ExternalPythonOperator` with `nnunet_venv` (`/opt/airflow/venvs/nnunet_venv/bin/python`) |
| Default device | `cpu` (GPU configurable via conf) |
| Uncertainty ranking | Not included (deferred) |
| Output uploads | Both `.nii.gz` segmentation and `.npz` probability files |
| Tool structure | Single `tool_inference.py` called 4× with different model params |
| Scope | DAG + tool module only (`assays.py` changes separate) |

## Proposed Changes

### Tool Module

#### [NEW] [tool_inference.py](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/tool/tool_inference.py)

A reusable tool module following the same pattern as `tool_dicom_to_nifti.py`:

1. **MinIO helpers**: Reuses the same `_get_s3_client()`, `_download_prefix()`, `_upload_file()` pattern
2. **`_download_model()`**: Downloads model weights from a model dataset in MinIO. Locates the source bucket by UUID (like `tool_download_samples._find_source_bucket()`), downloads the trainer directory (at the hardcoded subpath `primary/nnUNetTrainer__nnUNetPlans__3d_fullres`)
3. **`_run_inference()`**: Core inference logic adapted from [inference.py](file:///home/clin864/Projects/digitaltwins-platform/my_workspace/pilot-2/Breast/assay_4_initial_inference/inference.py):
   - Sets up nnUNet dummy env vars (lines 23-37 of inference.py)
   - Instantiates `nnUNetPredictor` with the same parameters
   - Auto-detects checkpoint (`checkpoint_best.pth` → `checkpoint_final.pth` fallback)
   - Handles both single-file and directory input modes
   - Saves probabilities (`save_probabilities=True`)
4. **`_upload_directory()`**: Uploads all output files (`.nii.gz` + `.npz`) from the output directory to MinIO
5. **`run()`**: Main entry-point called by `ExternalPythonOperator`:
   - Params: `bucket`, `nifti_prefix`, `model_dataset_uuid`, `run_id`, `output_key_prefix`, `device`, `gpu_id`
   - Downloads NIfTI input from MinIO → local temp dir
   - Downloads model from model dataset UUID → local temp dir
   - Runs inference
   - Uploads all outputs (`.nii.gz` + `.npz`) to MinIO
   - Returns the output prefix via XCom

---

### DAG Module

#### [NEW] [workflow_inference.py](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/workflow_inference.py)

Structure mirrors [workflow_image_conversion.py](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/workflow_image_conversion.py):

1. **`resolve_conf` task**: Extracts from `dag_run.conf`:
   - Standard fields: `bucket`, `subject_id`, `sample_id`, `dataset_uuid`, `sample_type`, `run_id`, `run_index`, `output_prefixes`, `output_name_by_sample_type`
   - Inference-specific: `device` (default `cpu`), `gpu_id` (default `0`)
   - Model dataset UUIDs: `skin_model_dataset_uuid`, `outer_rib_model_dataset_uuid`, `sternum_model_dataset_uuid`, `lesion_model_dataset_uuid`

2. **`download_samples` task**: Same `ExternalPythonOperator` pattern as image conversion — downloads NIfTI input from measurement dataset to staging area

3. **4 sequential inference tasks**: `skin_inference` → `outer_rib_inference` → `sternum_inference` → `lesion_inference`
   - Each is an `ExternalPythonOperator` calling `_run_inference` wrapper
   - Each receives: bucket, NIfTI prefix (from download_samples), model dataset UUID, run_id, output_key_prefix, device, gpu_id
   - Output prefix per model resolved via `_resolve_output_prefix` (same pattern as nifti/nrrd output prefix resolution)

4. **Dependency chain**:
   ```
   resolve_conf → download_samples → skin_inference → outer_rib_inference → sternum_inference → lesion_inference
   ```

**Expected DAG conf** (when triggered by preprocessor):
```json
{
    "bucket": "airflow-workspace",
    "subject_id": "sub-1",
    "sample_id": "sam-1",
    "dataset_uuid": "...",
    "sample_type": "nifti",
    "run_id": "workflow_39/run_0",
    "run_index": 0,
    "skin_model_dataset_uuid": "...",
    "outer_rib_model_dataset_uuid": "...",
    "sternum_model_dataset_uuid": "...",
    "lesion_model_dataset_uuid": "...",
    "device": "cpu",
    "gpu_id": 0,
    "output_prefixes": { ... },
    "output_name_by_sample_type": { ... }
}
```

> [!IMPORTANT]
> The `download_samples` task uses `cwl_venv` (which has `boto3`). The inference tasks use `nnunet_venv` (which has `torch`, `nnunetv2`, `dynamic-network-architectures`, and `boto3`). The `nnunet_venv` is built optionally — the Dockerfile requires `--build-arg INSTALL_NNUNET=true`.

## Verification Plan

### Automated Tests
- `python -c "import ast; ast.parse(open('workflow_inference.py').read())"` — syntax check
- `python -c "import ast; ast.parse(open('tool/tool_inference.py').read())"` — syntax check

### Manual Verification
- Deploy to the Airflow environment with nnUNet installed in cwl_venv
- Trigger `workflow_39` with a test conf containing valid NIfTI input and model dataset UUIDs
- Verify all 4 inference outputs appear in MinIO under the expected prefixes
