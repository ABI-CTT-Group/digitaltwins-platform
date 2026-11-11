# Inject Model Dataset UUIDs into DAG Conf from Assay Config

When the portal triggers `workflow_39` (or any future model-based workflow), the API should automatically look up model dataset UUIDs from the assay's `assay_input` rows and inject them into the DAG conf — so users don't need to manually provide them.

## Step 0 — Category value: VERIFIED against the live database

Checked `digitaltwins-platform-database-1` on 2026-09-18. The category is **`models`** (plural).
The provisional constant was correct; no change needed.

```
 assay_seek_id |      name       | category     | sample_type |             dataset_uuid
---------------+-----------------+--------------+-------------+--------------------------------------
            39 | mri_nifti       | measurements | nifti       | 199eeb0e-a7fe-11f1-afdc-ee55ba67a387
            39 | skin_model      | models       | (empty)     | de56869e-a800-11f1-8c94-ee55ba67a387
            39 | outer_rib_model | models       | (empty)     | de56869e-a800-11f1-8c94-ee55ba67a387
            39 | sternum_model   | models       | (empty)     | de56869e-a800-11f1-8c94-ee55ba67a387
            39 | lesion_model    | models       | (empty)     | de56869e-a800-11f1-8c94-ee55ba67a387
```

Input names map cleanly onto the DAG's conf keys (`skin_model` → `skin_model_dataset_uuid`), so the
`{name}_dataset_uuid` convention works as designed.

### Findings from the check

**(a) All four model rows point at one dataset — deliberate, temporary scaffolding.**

```
 dataset_uuid                         | category | dataset_name
--------------------------------------+----------+----------------
 de56869e-a800-11f1-8c94-ee55ba67a387 | models   | model_sds_skin
```

Only the skin model exists so far, so the `outer_rib_model`, `sternum_model` and `lesion_model` rows
are placeholders pointing at it. This is why three of the four entries in `INFERENCE_MODELS` are
commented out ([workflow_inference.py:62-67](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/workflow_inference.py))
— the two are paired stand-ins that get lifted together once the remaining models are trained. The
workflow is intended to run all four.

The relevance to this change is only that it confirms the design holds: `MODEL_TRAINER_SUBPATH` is a
fixed constant ([tool_inference.py:33](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/tool/tool_inference.py)),
so the dataset UUID is the sole discriminator between models — which is exactly what the
`{name}_dataset_uuid` conf keys carry. Repointing the three rows at real datasets and uncommenting
`INFERENCE_MODELS` is then the entire activation step; no API change required.

**(b) Pre-existing inconsistency in the measurement category — not fixed by this change.**

`assay_input.category` holds all three spellings across the table: `models` (4 rows),
`measurements` (2 rows), and `measurement` (1 row). The consumer at
[downloader.py:72](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/src/digitaltwins/core/downloader.py)
tests `category == "measurement"`, so it matches only the single assay-24 row and skips assay 38's
and assay 39's inputs. That looks like a latent bug, but it is unrelated to model injection and
outside this change's scope — noting it for a separate ticket.

## Design Decisions

| Decision | Choice |
|---|---|
| Where to store model UUIDs | Reuse existing `assay_input` table — no schema change |
| How to distinguish models from data | Filter by `category == "models"` (verified in Step 0) |
| How to map input → DAG conf key | Input `name` → conf key `{name}_dataset_uuid` |
| Scope | Generic — applies to all script-based workflows |
| Missing model UUID handling | **Fail fast: HTTP 400 from `run_assay`** (see rationale below) |
| Injection location | Pure helper `_model_conf_overrides()`, called once in `run_assay()` |
| Testing | Unit tests for the helper, written first; then manual portal verification |

### Why fail fast instead of passing an empty string

The earlier draft proposed logging a warning and passing `""`, on the assumption the DAG would
"fail gracefully". It does not — it fails late and obscurely:

1. `resolve_conf` coerces a missing *or* empty key to `""` with no warning
   ([workflow_inference.py:233-235](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/workflow_inference.py)).
2. `download_samples` then runs to completion — a full NIfTI fetch from MinIO.
3. Only then does `_find_source_bucket(s3_client, "")` scan every bucket for prefix `/`, return
   `None`, and raise `FileNotFoundError: No bucket found containing model dataset ''`
   ([tool_inference.py:139-143](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/tool/tool_inference.py)).

A 400 from `/assays/{id}/run` is cheaper, clearer, and lands in the same error path the endpoint
already uses for other config problems.

## Proposed Changes

### API Router

#### [MODIFY] [assays.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/assays.py)

**1. Add the constant and a pure helper** (module level, near `_fetch_assay_configs`)

```python
# Verified against live assay_input rows, 2026-09-18.
MODEL_INPUT_CATEGORY = "models"


def _model_conf_overrides(inputs: list[dict]) -> dict[str, str]:
    """Map model-category assay inputs to their `{name}_dataset_uuid` DAG conf keys."""
    overrides: dict[str, str] = {}
    for inp in inputs:
        if inp.get("category") != MODEL_INPUT_CATEGORY:
            continue
        name = inp.get("name") or ""
        dataset_uuid = inp.get("dataset_uuid") or ""
        if not name:
            raise ValueError("A model assay input is missing its name.")
        if not dataset_uuid:
            raise ValueError(f"Model input '{name}' has no dataset_uuid.")
        overrides[f"{name}_dataset_uuid"] = dataset_uuid
    return overrides
```

**2. Filter model inputs out of `_discover_samples`** ([line 142](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/assays.py))

Correcting the first draft twice over. Model inputs do not error: their `sample_type` is the empty
string (verified — not `NULL`), so `get_dataset_samples` builds `... AND sample.sample_type=''`
([querier.py:240-244](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/src/digitaltwins/postgres/querier.py))
and matches nothing. The model dataset also has **zero** `dataset_mapping` rows, so it contributes no
samples by either route.

The filter is therefore a **no-op against today's data** — a cheap guard, not a load-bearing fix.
It earns its place because nothing in the schema prevents a future model input from carrying a
`sample_type` whose dataset *does* have mappings, which would emit model rows as measurement samples
and spawn spurious DAG runs. Add it, but do not expect it to change current behaviour.

```diff
     for inp in inputs:
+        if inp.get("category") == MODEL_INPUT_CATEGORY:
+            continue
         dataset_uuid = inp.get("dataset_uuid")
```

**3. Build the overrides once, in the existing prepare block** ([line 449](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/assays.py))

Reusing this `try` gives the 400 behaviour for free.

```diff
         try:
             configs = _fetch_assay_configs(querier, assay_id)
             samples = _discover_samples(querier, configs)
+            model_conf = _model_conf_overrides(configs.get("inputs", []))
         except Exception as e:
             raise HTTPException(
                 status_code=status.HTTP_400_BAD_REQUEST,
                 detail=f"Failed to prepare assay: {str(e)}",
             )
```

**4. Splat into `payload_conf`** ([line 485](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/assays.py))

The first draft placed the extraction loop immediately before `_trigger_dag`, which sits *inside*
`for idx, sample in enumerate(samples)` ([line 474](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/app/routers/assays.py)) —
rebuilding an identical dict for every sample.

```diff
                 "run_id": run_id,
                 "run_index": idx,
+                **model_conf,
             }
```

> [!IMPORTANT]
> The four `assay_input` rows for assay 39 already carry the required names and the `models`
> category, so no config change is needed to make this work.
>
> **Only `skin_model` is consumed today**, while the other three models are still to be trained.
> `outer_rib_model_dataset_uuid`, `sternum_model_dataset_uuid` and `lesion_model_dataset_uuid` are
> injected into the conf but ignored until those entries are uncommented in `INFERENCE_MODELS`
> ([workflow_inference.py:62-67](file:///home/clin864/Projects/digitaltwins-platform/services/airflow/dags/workflow_inference.py)).
> Injecting all four unconditionally is intentional: when the models land, activation is a DB
> repoint plus uncommenting those lines, with no change to the API.

## Verification Plan

### Unit tests (write first — Red, then Green)

New file `tests/test_assay_model_conf.py` — **not** appended to
[test_assay_api.py](file:///home/clin864/Projects/digitaltwins-platform/services/api/digitaltwins-api/tests/test_assay_api.py).
That file builds a `TestClient(app)` at module scope and its one test asserts nothing (it prints and
passes regardless), so it is an integration smoke script needing a live DB. Importing it would drag
those dependencies into a pure unit test.

`app.routers.assays` imports cleanly on its own with no DB connection (verified), and
`_model_conf_overrides` is pure, so the new file needs only `from app.routers.assays import
_model_conf_overrides`. Run with `python3 -m pytest tests/test_assay_model_conf.py` from
`services/api/digitaltwins-api/`.

| Case | Expected |
|---|---|
| `[]` | `{}` |
| Only non-model inputs | `{}` |
| One model input, name + uuid present | `{"skin_model_dataset_uuid": "<uuid>"}` |
| Mixed model and measurement inputs | Only model keys returned |
| Model input with empty `dataset_uuid` | `ValueError` |
| Model input with missing `name` | `ValueError` |
| Model input with `category` absent/`None` | Treated as non-model, `{}` |

Plus one test for `_discover_samples` confirming a model input is skipped even when it carries a
`sample_type` whose dataset would otherwise yield sample rows.

### Manual verification

1. No config change needed — assay 39's model rows are already correct (Step 0).
2. Trigger via `POST /assays/39/run` from the portal.
3. Verify in the Airflow UI that the DAG run conf contains `skin_model_dataset_uuid` with the
   correct UUID.
4. Confirm `skin_inference` resolves and downloads the model.
5. Negative case: blank one model input's `dataset_uuid` and confirm the endpoint returns 400
   *without* triggering any DAG run.
