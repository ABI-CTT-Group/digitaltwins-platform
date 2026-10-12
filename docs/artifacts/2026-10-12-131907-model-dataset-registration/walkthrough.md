# Walkthrough: model dataset registration

Model datasets (e.g. trained nnUNet weights in an SDS folder) can now be uploaded and registered like measurements, through the API and through a Models page on the catalogue dashboard. A registered model can optionally be published to FHIR as a Device.

Design decisions: [ADR model dataset ingest](../../decisions/2026-10-12-model-dataset-ingest.md) and [ADR model FHIR Device](../../decisions/2026-10-12-model-fhir-device.md). Plan: [implementation_plan.md](implementation_plan.md).

## What changed

### API (`services/api`)

- **New package `src/digitaltwins/models/`.**
  - `validation.py`: a model needs `dataset_description.xlsx`/`.json` at its root and at least one file under `primary/`.
  - `pipeline.py`: `commit_model` stores the dataset in the `models` bucket and Postgres. Subjects and samples load from the spreadsheets only, never from `primary/` folders.
  - `fhir.py`: `{"model": {description, version}}` descriptions and the Device built from them. Push deletes any Device with the same identifier, then creates it.
- **`HapiRest.create`** posts a resource. No FHIR library builds a model resource.
- **Upload sessions** accept `category=models`, with model validation at finalize and model branches in the staged FHIR endpoints. `GET /datasets/uploads?category=` filters open sessions by category.
- **Commit and FHIR jobs** have model branches. `fhir=auto` pushes a default Device. The stored `fhir.json` is the Device as HAPI returned it.
- **Committed FHIR endpoints** (`/datasets/{uuid}/fhir/tree`, `annotation`, `preview`) handle models.
- **One-shot `POST /datasets?category=models`** now validates and commits through a session, instead of the bare uploader.
- **`GET /models`** lists model datasets.
- **Delete** removes the model's Device.
- **CLI** `import_dataset --category models` uses the model validator. The Python client docstring documents models.
- **Docs**: `services/api/README.md` gains "Uploading a model dataset". `services/api/docs/import-dataset.md` gains "Model datasets".

### Portal frontend (`services/portal/frontend`)

- **Catalogue card** "Models" opens `/upload-dataset/models` for admin and researcher.
- **Models page** (`views/upload-dataset/models/`): an overview of open uploads and registered models, and a two-step wizard. The steps are Information (chunked, resumable upload) and FHIR (optional; version and description).
- **Card actions** depend on state:
  - Uploading: resume or cancel.
  - Staged: approve, edit FHIR details or cancel.
  - Registered: edit or publish FHIR, retry FHIR, or delete with a confirmation dialog.
- **Shared upload code** takes a category:
  - `useUploadInit`, `ChunkedUploader` and the resume index in localStorage are per category.
  - The measurements Information step takes a `category` prop and is reused for models. This replaces the planned separate `ModelInformationStep`, to avoid copying about 400 lines.
  - The measurements overview now lists only measurement sessions. Before, it listed every open session, including tool and workflow handoffs.
- **`DeletePlatformDatasetDialog`** supports `kind="model"`.

## Verification

### Automated tests

| Suite | Result |
|---|---|
| API, model and touched tests | all pass |
| API, full suite | 389 passed; 6 failed, 1 error, all pre-existing |
| Portal vitest | 94 passed (23 files) |
| `vite build` | succeeds |

The pre-existing failures are in `test_delete_dataset_api`, `test_*_workspace_dataset_api` and `test_upload_dataset_api`. The same subset fails identically on a clean checkout of HEAD.

- **Type checking.** `vue-tsc` 1.8 in `package.json` cannot run with the installed TypeScript 5.9. With `vue-tsc` 2.2.10 and TypeScript 5.9.3 in a throwaway container, the touched files have no errors except one. `ModelsOverallView` has the same `RegistryView` slot-typing error that `MeasurementsOverallView` and `WorkflowsOverallView` already have.

### Live, after rebuilding `digitaltwins-api` and `portal-frontend`

1. **Real model through the Python client.** `my_workspace/data/model_skin_test` (about 1.26 GB) went through chunked sessions with `fhir_descriptions={"model": {"version": "e2e-1"}}`. It was committed in about 10 s.
   - MinIO has 36 objects: 35 files and `fhir.json`, with byte counts matching the source.
   - The dataset row has `category=models` and `fhir_status=completed`. No subject rows were created.
   - HAPI has one Device with the name, version and note set.
   - The dataset is left registered as "model_skin_test (e2e client)" for checking in the portal.
2. **Portal approval flow, through the API.** A tiny model was uploaded with `commit_mode=on_approve`.
   - Finalize returned `staged`.
   - The session was listed under `?category=models` and not under `measurements`.
   - The tree returned the default descriptions. The draft PUT worked, and the preview returned a Device.
   - Approve led to `completed`, with `fhir_status=completed`.
   - The model was listed in `/models`. Delete removed 3 MinIO objects and 1 Device.
3. **One-shot.** `POST /datasets?category=models&fhir=auto` with a tiny model committed it and pushed the Device. Delete then removed it. A package without `primary/` returned 400.
4. **Portal.** `/catalogue-dashboard` serves, and the rebuilt bundle contains the Models route and page. The assay page loads each input's datasets by category, so registered models appear in model input pickers.

## Not verified

- I did not click through the Models wizard in a browser. The components are covered by vitest, and the API calls they make were run live as described above.
- The CLI was tested by integration tests, not live, because it needs an interactive Keycloak login.
