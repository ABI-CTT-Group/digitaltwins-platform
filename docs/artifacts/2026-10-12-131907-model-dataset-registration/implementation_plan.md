# Model dataset registration (API + catalogue dashboard)

## Context

The platform registers measurement, tool and workflow datasets, but not models. Today "models" is only half wired:

- `POST /datasets?category=models` falls through to the bare `Uploader.upload_dataset` path ([datasets.py:391](services/api/app/routers/datasets.py#L391)). It does no validation, no session, no FHIR.
- Chunked upload sessions reject models ([dataset_uploads.py:51,141](services/api/app/routers/dataset_uploads.py#L51)). The example model `my_workspace/data/model_skin_test` is about 1.25 GB of nnUNet weights, so sessions are required.
- The catalogue dashboard shows Models as "Coming soon" ([catalogue-dashboard-view.vue:126-134](services/portal/frontend/src/views/catalogue/catalogue-dashboard-view.vue#L126-L134)).
- Inference (workflow_39) already consumes models by dataset UUID from the `models` MinIO bucket, and assay inputs with `category='models'` already pick from `models` datasets. So once a model is registered under `models`, it is usable by assays with no DAG change.

Goal: register model datasets like measurements, through the API (sessions, one-shot, client, CLI, listing) and through a Models wizard in the portal, with an optional FHIR Device.

## Decisions from the interview

| Topic | Decision |
|---|---|
| Portal pattern | Mirror measurements: portal frontend uploads chunks straight to the API session endpoints, `commit_mode=on_approve`, overview page with approval |
| SEEK | Not registered in SEEK |
| FHIR | Optional. One FHIR R4 **Device** per model, built in this repo (fhir-cda / digitaltwins-on-fhir have no model resource). Recorded as a current, revisable decision |
| Device fields | Server-owned: identifier = dataset UUID, deviceName = dataset name. Client: `description` (Device.note), `version` (Device.version) |
| Validation | Generic SDS only: `dataset_description.xlsx` or `.json` at root, and a `primary/` folder containing at least one file. No nnUNet-specific checks |
| Subjects/samples | Load `subjects.xlsx` / `samples.xlsx` rows like measurements, but **do not derive** subjects from `primary/` folders (that would turn `nnUNetTrainer__…` into a subject) |
| Model metadata column | None; no migration |
| Roles | admin + researcher (existing `UPLOAD_ROLES`) |
| API scope | Sessions, one-shot `POST /datasets` models path, Python client + CLI, `GET /models`, delete from portal |

## Design

### API: new package `services/api/src/digitaltwins/models/`

Mirrors `tools/` and `workflows/`.

- `__init__.py`: `CATEGORY = "models"`.
- `validation.py`: `validate_model_structure(staging) -> tuple[bool, str]`. Uses `resolve_project_root` from `measurements/validation.py`. Checks the dataset_description file and a non-empty `primary/` (any file, any depth).
- `pipeline.py`: `commit_model(root, dataset_name=None, descriptions=None) -> CommitResult`.
  - Calls `Uploader().upload_dataset(str(root), category="models", dataset_name=..., derive_from_primary=False)`. Subject/sample xlsx rows load normally.
  - If descriptions are given, stamps them with `fhir.build_descriptions(...)` and stores them with `measurements.pipeline.save_annotation`.
  - Reuses `CommitResult` from `measurements/pipeline.py`.
- `fhir.py`, shaped like [tools/fhir.py](services/api/src/digitaltwins/tools/fhir.py):
  - `build_descriptions(dataset_uuid, dataset_name, client=None) -> {"model": {uuid, name, description, version}}`. Raises `ValueError` for a malformed body or unknown fields.
  - `to_device(descriptions) -> dict`: the Device resource.
  - `push(descriptions, rest)`: delete existing Device(s) with the identifier, then create.
  - `delete(dataset_uuid, rest) -> int`.
- `HapiRest` in [fhir_service.py:196](services/api/src/digitaltwins/measurements/fhir_service.py#L196) gains `create(resource) -> dict` (POST). It has only `search` and `delete` today.

Device shape (identifier system to match what digitaltwins-on-fhir uses for tool ActivityDefinitions, so model UUIDs cited by tools line up):

```json
{"resourceType": "Device",
 "identifier": [{"system": "<same system as tools>", "value": "<dataset uuid>"}],
 "deviceName": [{"name": "<dataset name>", "type": "user-friendly-name"}],
 "type": {"text": "model"},
 "version": [{"value": "<version>"}],
 "note": [{"text": "<description>"}]}
```

### API: wiring into existing routers and jobs

Every branch below sits next to the existing `tools.CATEGORY` branch.

- [dataset_uploads.py](services/api/app/routers/dataset_uploads.py)
  - `create_upload`: accept `models`. If `fhir_descriptions` is given it must be `{"model": {...}}`.
  - `finalize_upload`: models use `validate_model_structure`. With `fhir_mode == "descriptions"`, validate with `models.fhir.build_descriptions("", "", ...)`. No `sampleless_subjects` warnings.
  - Staged FHIR endpoints (`/fhir/tree`, `/fhir/annotation` PUT, `/fhir/preview`): models branch returns default descriptions, validates model descriptions, previews the Device.
  - `GET /datasets/uploads` gains an optional `category` query filter. This fixes open model (and tool/workflow handoff) sessions leaking into the measurements overview.
- [jobs.py](services/api/src/digitaltwins/measurements/jobs.py)
  - `_commit`: models branch calls `commit_model`. `fhir_mode="auto"` means default descriptions (session description, no version).
  - `run_fhir_push_job`: models branch stores the Device as `models/<uuid>/fhir.json`, then `models.fhir.push`.
- [dataset_fhir.py](services/api/app/routers/dataset_fhir.py): `tree`, `annotation` PUT and `preview` get a models branch.
- [datasets.py](services/api/app/routers/datasets.py): `POST /datasets` routes `models` to a new `_ingest_model`. It validates, creates a session and runs the commit job synchronously, the same way `_ingest_measurements` does. The bare `uploader.upload_dataset` fallback then no longer serves any category in `DATASET_CATEGORIES`; leave the fallback in place.
- New `app/routers/models.py`: `GET /models` returns `{"models": querier.get_datasets(categories=["models"])}`. Registered in `app/main.py`.
- [deleter.py:146](services/api/src/digitaltwins/core/deleter.py#L146): `_delete_fhir_resources` gets a models branch that calls `models.fhir.delete`.
- [cli/import_dataset.py](services/api/src/digitaltwins/cli/import_dataset.py): models use `validate_model_structure` instead of `validate_sparc_structure`.
- [client.py](services/api/src/digitaltwins/client.py): no code change expected beyond the docstring, since it is category-agnostic once sessions accept models. Covered by a test.
- Docs: models section in `services/api/README.md` and `services/api/docs/import-dataset.md`.

### Portal frontend (Vue 3 + Vuetify)

- **Shared upload code, minimal change.**
  - [measurement_api.ts](services/portal/frontend/src/bootstrap/measurement_api.ts): `useUploadInit` takes an optional `category` (default `measurements`). `useMeasurement` requests `/datasets/uploads?category=measurements`.
  - [measurement_upload.ts](services/portal/frontend/src/bootstrap/measurement_upload.ts): `ChunkedUploader` meta gains optional `category`, passed through to `useUploadInit`. `PendingUpload` records the category, so resume offers only same-category uploads.
- **New `bootstrap/model_api.ts`:**
  - `useModels()` lists open sessions with `category=models` plus `/datasets?categories=models`, using the same `upload:` / `dataset:` id scheme.
  - `useGetModel(id)`, `useUpsertModelAnnotation(id, {model: {description, version}})`, `useApproveModel(id)`, `usePushModelFhir(id)`.
  - Cancel and delete reuse `useUploadCancel` and `platform_api.deletePlatformDataset`.
- **New views `views/upload-dataset/models/`:**
  - `index.vue` switches between overview and form, like measurements.
  - `ModelsOverallView.vue` lists models with status and FHIR status. Actions: Approve (staged/failed), Cancel (open session), Delete (committed; reuses `DeletePlatformDatasetDialog`), Push FHIR (committed with annotation).
  - `UploadModelForm.vue`: two-step stepper.
    1. `steps/ModelInformationStep.vue`: name, description, and the `MeasurementChunkedDropzone` driven by `ChunkedUploader` with `category: 'models'`. Pause/resume/cancel as in measurements. Copy text says "SDS model dataset".
    2. `steps/ModelFhirStep.vue`: "Publish to FHIR" toggle, off by default. When on, version + description fields, PUT to the staged annotation. Finish leaves the session staged and returns to the overview for approval.
- **Router** ([router/index.ts](services/portal/frontend/src/router/index.ts)): `/upload-dataset/models`, name `UploadModelDataset`, roles admin + researcher.
- **Catalogue card:** Models gets `herf: 'UploadModelDataset'`, `cta: 'Open'`, `requireRoles: ['admin','researcher']`, and loses `comingSoon`.

### Out of scope

- SEEK registration, nnUNet-specific validation, a model framework column, Airflow DAG changes.
- Linking tool ActivityDefinitions to model Devices.
- Unrelated issues seen during exploration, mentioned only: the broken "Workflow assembler" card route, and `downloader.py:72` testing `"measurement"` singular.

## ADRs to write on approval

1. `docs/decisions/2026-10-12-model-dataset-ingest.md`: models reuse the measurements session/approval pattern with their own `models/` package. Alternatives were the workflow-style portal-backend handoff and the bare one-shot uploader. Records no SEEK, generic SDS validation, and subjects loaded from xlsx but not derived from `primary/`.
2. `docs/decisions/2026-10-12-model-fhir-device.md`: FHIR Device built in-repo, chosen over DocumentReference and Library. **Status: Accepted, current decision, expected to be revisited** once a model representation is settled upstream.

## Implementation order (TDD: failing test first at each step)

1. `models/validation.py` → `tests/test_model_validation.py` (missing description, missing/empty `primary/`, wrapper folder, valid).
2. `models/fhir.py` + `HapiRest.create` → `tests/test_model_fhir.py` (bad body, unknown field, Device shape, push deletes then creates against a fake rest client).
3. `models/pipeline.py` + `jobs` branches → `tests/test_model_pipeline.py` (integration). Assert: dataset row `category='models'`, MinIO keys `models/<uuid>/primary/...`, no subjects derived from `primary/`, annotation stamped.
4. Session router → `tests/test_dataset_uploads_models_api.py`: create, finalize 400s, stage → approve → completed, `?category=` filter. Update `test_other_categories_are_rejected` in `test_dataset_uploads_api.py`, which posts `models` today, to use an unknown category.
5. `dataset_fhir.py` branches, one-shot `_ingest_model`, `GET /models`, deleter branch, CLI → extend `test_datasets_oneshot_api.py`, `test_dataset_fhir_api.py`, `test_delete_dataset_cleanup.py`, `test_import_dataset_cli.py`, `test_upload_client.py`, plus a new `tests/test_models_api.py`.
6. Small fixture `tests/data/model_minimal/`: copy an existing fixture's `dataset_description.xlsx`, plus `primary/model/dataset.json`. The real 1.25 GB dataset is used only for e2e.
7. Frontend: vitest for `model_api.ts` (session filter, `category: 'models'` sent), the `useMeasurement` category filter, `ChunkedUploader` passing category, and a `ModelFhirStep` spec. Then views, router and card.
8. Docs, ADRs, and artifact sync to `docs/artifacts/2026-10-12-<time>-model-dataset-registration/`, with this plan redacted and repo-relative paths only.

## Verification

- **API tests** in a throwaway container, never the live one:
  ```
  docker run --rm --network digitaltwins-platform --env-file .env -e MINIO_ENDPOINT=http://minio:9000 \
    -v $PWD/services/api:/digitaltwins-api -w /digitaltwins-api --entrypoint sh \
    digitaltwins-platform-digitaltwins-api -c "pip install -q pytest httpx; python -m pytest -q tests"
  ```
  Compare against the known pre-existing failures in `test_delete_dataset_api`, `test_*_workspace_dataset_api` and `test_upload_dataset_api`.
- **Frontend:** `docker run --rm -v $PWD/services/portal/frontend:/fe -w /fe node:20 npx vitest run`, then `npx vue-tsc --noEmit` the same way.
- **Rebuild and restart** the `digitaltwins-api` and `portal-frontend` services with `docker compose up -d --build`.
- **End to end with `my_workspace/data/model_skin_test`:**
  1. In the portal (http://localhost/catalogue-dashboard), open Models, upload the folder, enable FHIR with a version, then approve in the overview.
  2. Check `GET /digitaltwins-api/models` lists it, and MinIO has `models/<uuid>/primary/nnUNetTrainer__nnUNetPlans__3d_fullres/fold_0/checkpoint_final.pth`.
  3. Check HAPI `Device?identifier=<uuid>` returns one Device.
  4. Check the measurements overview does not show the model session.
  5. In assay 39, the new model appears in a model input picker.
  6. Upload the same folder through the CLI with `--category models`, and through the one-shot endpoint with a tiny model.
  7. Delete from the Models overview and confirm the Postgres rows, MinIO prefix and Device are gone.
