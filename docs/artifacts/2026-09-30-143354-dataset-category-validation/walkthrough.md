# Walkthrough: reject unknown dataset categories on POST /datasets

## Problem
`POST /datasets?category=tool` (a typo for `tools`) returned 200. The category is free text: only `category == "tools"` triggers the tool path (CWL check + SEEK registration), so `"tool"` fell through to `Uploader.upload_dataset`. That creates a MinIO bucket named after the category. The result was dataset `97f6e9ec-bc6d-11f1-92cf-4ab26f946f64` in a new `tool` bucket, with no SEEK Workflow. Resumable sessions (`/datasets/uploads`) were not affected: they already reject categories other than `measurements` / `tools`.

## Cleanup (done 2026-09-30)
- `Deleter().delete_dataset("97f6e9ec-bc6d-11f1-92cf-4ab26f946f64")` removed the Postgres row and 13 MinIO objects. It had no FHIR resources and no SEEK workflow.
- The now-empty `tool` bucket was removed.
- Postgres `dataset.category` now holds only `measurements`, `models`, `tools` and `workflows`, and the MinIO buckets match `services/minio/init-minio.sh`.

## Fix
- `app/routers/datasets.py` adds `DATASET_CATEGORIES = {"measurements", "models", "tools", "workflows"}`, the buckets `init-minio.sh` creates. `upload_dataset` returns `400 Unknown category 'tool'; use one of: measurements, models, tools, workflows` before anything is stored.
- Chosen over an enum-typed query parameter (a Swagger dropdown, but 422), because it keeps the existing test isolation: tests patch the set to a throwaway bucket, the same pattern as `INGEST_CATEGORIES` and `tools.CATEGORY`.
- **Follow-up, same day:** the `category` query's OpenAPI schema now carries `enum: [measurements, models, tools, workflows]` (`json_schema_extra`), so Swagger `/docs` shows a dropdown like `tool_type`. The parameter stays a plain string checked against `DATASET_CATEGORIES`, so a typo from other clients is still a 400 listing the valid values (not a 422), and tests can still patch the set. Test: `test_datasets_oneshot_api.py::test_category_is_offered_as_a_dropdown_in_the_api_docs`.
- Internal callers of `Uploader.upload_dataset` (for example workspace outputs in `assays.py`, which use `workflows`) are unchanged.
- The README notes the accepted categories.

## Tests
- New: `test_datasets_oneshot_api.py::test_unknown_category_is_rejected_before_anything_is_stored`. It sends a throwaway typo category and checks for a 400 naming both the typo and the valid category, no dataset row, and no bucket created.
- Fixtures in `test_datasets_oneshot_api.py` and `test_datasets_tools_api.py` patch `datasets.DATASET_CATEGORIES` to their throwaway bucket.
- `pytest services/api/tests`: **198 passed**, 2 failed, 1 error. These are the same pre-existing legacy failures as before. `test_upload_dataset_api.py` still posts `category="measurement"` (singular), but it already errored on a missing fixture.

## Follow-up (not done)
- `services/api/examples/query_postgres.py` / `query.py` filter `GET /datasets` with singular categories (`tool`, `model`, `workflow`, `measurement`), which match no rows.
