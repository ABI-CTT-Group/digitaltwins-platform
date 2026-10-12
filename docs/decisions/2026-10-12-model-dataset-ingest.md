# Model dataset ingest reuses the measurements session pattern

- **Date:** 2026-10-12
- **Status:** Accepted

## Context

Model datasets (e.g. trained nnUNet weights packed as an SDS folder) could only be
stored through the bare one-shot `POST /datasets?category=models` path: no
validation, no upload session, no FHIR, and no portal page. Model datasets are
large (the example `model_skin_test` is ~1.25 GB), so they need the resumable
chunked upload sessions. The inference DAG already consumes a model by its
dataset UUID from the `models` MinIO bucket, so registration only has to put a
model under that category.

## Alternatives Considered

### Option A: Measurements-style sessions with a `models` package (chosen)
- Pros: the portal frontend uploads chunks straight to the API (no portal-backend
  state); reuses staging, approval, delete and FHIR status machinery; same entry
  points (sessions, one-shot, client, CLI).
- Cons: one more category branch in the session router, jobs and FHIR router.

### Option B: Workflow-style portal-backend handoff
- Pros: matches tools/workflows, which need a build step.
- Cons: models have no build step; the extra hop and token relay add moving
  parts for nothing.

### Option C: Keep the bare one-shot uploader
- Pros: no work.
- Cons: no validation, no resumable upload for multi-GB weights, no portal.

## Decision

Option A. A new `digitaltwins.models` package (validation, pipeline, FHIR) plugs
into the existing session router, commit/FHIR jobs, dataset FHIR router, deleter,
one-shot endpoint and CLI, next to the tool branches. Also:

- **No SEEK registration** for models.
- **Generic SDS validation only:** `dataset_description.xlsx`/`.json` at the root
  and a `primary/` folder holding at least one file. No framework-specific checks.
- **Subjects/samples** load from `subjects.xlsx`/`samples.xlsx` like measurements,
  but are **not derived from `primary/` folders** (a model's `primary/` holds
  model files such as `nnUNetTrainer__…`, not patients).
- No model-specific column on `dataset`; no migration.
- `GET /models` lists model datasets; `GET /datasets/uploads?category=` filters
  open sessions so each portal overview shows only its own category.

## Consequences

- Models are registered, listed, approved and deleted the same way as measurements.
- Nothing records the model framework or the trainer sub-path; the inference
  tool keeps its hard-coded nnUNet sub-path. A framework column can be added
  later if pickers need to filter by it.
- See [2026-10-12-model-fhir-device.md](2026-10-12-model-fhir-device.md) for the optional FHIR resource.
