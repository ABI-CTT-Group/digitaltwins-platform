# Task: model dataset registration

Plan: [implementation_plan.md](implementation_plan.md)

## Planning
- [x] Interview and plan approved
- [x] Sync artifacts to docs/artifacts/ (implementation_plan.md)
- [x] ADRs: `docs/decisions/2026-10-12-model-dataset-ingest.md`, `docs/decisions/2026-10-12-model-fhir-device.md`
- [x] Sync artifacts to docs/artifacts/ (ADR copies)

## API (`services/api`), test first at each step
- [x] `models/validation.py`: `tests/test_model_validation.py`
- [x] `models/fhir.py` + `HapiRest.create`: `tests/test_model_fhir.py`
- [x] `models/pipeline.py` + commit/FHIR job branches: `tests/test_model_pipeline.py`
- [x] Session router: accept models, validate, staged FHIR endpoints, `?category=` filter: `tests/test_dataset_uploads_models_api.py`
- [x] Committed FHIR endpoints, one-shot `POST /datasets`, `GET /models`, delete removes Device: `tests/test_models_api.py`
- [x] CLI and Python client: `tests/test_import_dataset_cli.py`, `tests/test_upload_client.py`
- [x] Full API suite: only the known pre-existing failures (same as a clean checkout of HEAD)
- [x] Docs: `services/api/README.md`, `services/api/docs/import-dataset.md`

## Portal frontend (`services/portal/frontend`)
- [x] Shared upload code: `useUploadInit` category, `ChunkedUploader` category, pending uploads per category, measurements overview lists only measurement sessions (vitest)
- [x] `bootstrap/model_api.ts` (vitest)
- [x] Information step takes a `category` prop, reused for models instead of a copied `ModelInformationStep` (deviation from plan, less duplicated code)
- [x] Models views: index, overview, upload form, FHIR step (vitest for FHIR step)
- [x] Router `/upload-dataset/models` and catalogue card enabled
- [x] `DeletePlatformDatasetDialog` supports models (vitest)
- [x] vitest pass and `vite build` succeeds; type check with vue-tsc 2.2.10 (the pinned vue-tsc 1.8 cannot run with TypeScript 5.9)

## Wrap-up
- [x] Rebuild and restart `digitaltwins-api` and `portal-frontend`
- [x] End to end: real model through the Python client; approval flow, one-shot and delete through the live API (see walkthrough; the browser wizard was not clicked through)
- [x] Walkthrough written
- [x] Sync artifacts to docs/artifacts/ (walkthrough and task.md live in the folder; ADR copies match docs/decisions)
- [x] Secret check: gitleaks found no leaks in this folder or docs/decisions; no local paths
