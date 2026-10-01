# Walkthrough: Approved GUI Tool Content-Type Fix

Plan: [plan.md](plan.md). Date: 2026-10-01. Branch: `dev_chinchien` (uncommitted at time of writing).

## Problem

Once approved, a GUI tool loaded from `tools/<dataset_uuid>/primary/…` in MinIO. The digitaltwins-api had uploaded that copy with no `Content-Type`, so MinIO served it as `binary/octet-stream` with `X-Content-Type-Options: nosniff`. Browsers refuse to execute such scripts and workers. The `/tool-view` page then showed only the portal shell, without the plugin UI.

## Code change

- `services/api/src/digitaltwins/minio/uploader.py`: `Uploader.upload_file` now passes `ExtraArgs={"ContentType": mimetypes.guess_type(path)[0] or "application/octet-stream"}`. `upload_folder` goes through `upload_file`, so every API upload is covered, for all dataset categories.
- `services/api/tests/test_minio_content_type.py` (new):
  - `test_upload_file_sets_content_type` (6 cases): a unit test with a fake S3 client covering `.js`, worker `.js`, `.css`, `.ico`, no extension, and an unknown extension.
  - `test_upload_folder_content_type_round_trips_through_minio`: an integration test that uploads a bundle-shaped folder to a throwaway MinIO bucket and checks `head_object` for each file.

## Verification

| Check | Result |
|---|---|
| New tests before the fix | 6 unit FAIL (`upload_file passed no ExtraArgs`). Integration test FAIL (`'binary/octet-stream'` for `my-app.umd.js`) |
| New tests after the fix | 7 passed (host venv, MinIO on `localhost:8011`) |
| Full API suite, baseline (fix stashed) | 230 passed, 11 failed, 1 error. The failures are the 7 new tests plus 4 pre-existing |
| Full API suite, with the fix | 237 passed, 4 failed, 1 error, all pre-existing (see below) |

The pre-existing failures are identical with and without the fix:
- `test_delete_nonexistent_dataset`
- `test_delete_existing_dataset`
- `test_download_dataset` ("Missing Downloader")
- `test_upload_workspace_datasets_jupyter`
- `test_upload_zip` (error: fixture `bucket_name` not found)

The suite was run in a throwaway `--rm` container built from the `digitaltwins-api` image on the `digitaltwins-platform` network. `services/api` was mounted at `/work` and `services/postgres` at `/postgres`, and `pytest rocrate httpx` were pip-installed in the throwaway container only. The host `.venv` lacks `fhir_cda`.

## Deployment and data repair (local stack)

1. `docker compose build digitaltwins-api && docker compose up -d digitaltwins-api`. The fix was confirmed present in the running container.
2. The repair snippet from plan Task 2 was run in the API container against bucket `tools`:
   - Dry run: would change **755** objects, all under `0c57cce8-bd3b-11f1-8870-2a34b780cc74/` (`tool_volview`), all currently `binary/octet-stream`. The new types were 553 `application/octet-stream`, 96 `application/javascript`, 47 `image/jpeg`, 19 `text/x-python`, 14 `image/png`, 7 `application/json`, 5 `text/css`, 4 `image/svg+xml`, 4 `application/wasm`, 3 `image/vnd.microsoft.icon`, 2 `text/plain` and 1 `text/html`.
   - Apply: changed 755. Second apply: changed 0 (idempotent).
3. Headers after the repair: `my-app.umd.js`, `assets/histogram.worker-Dk1Y0_vM.js` and `itk/itk-wasm-pipeline.min.worker.js` are served as `application/javascript`, and `favicon.ico` as `image/vnd.microsoft.icon`. The `my-app.umd.js` md5 is unchanged (`4703b655…`), so only metadata was rewritten.
4. Headless Chrome gate check: the repaired `my-app.umd.js` **LOADED** as a `<script>` and injected the VolView CSS. The control (`CHANGES`, `application/octet-stream`) was **REFUSED**.

## Not done

- **Logged-in browser check of `/tool-view` for `tool_volview`** (plan Task 2, Step 5). This needs a Keycloak session and is left for the user. Use DevTools with "Disable cache" turned on.
- **Re-approving `tool_volview-2` end to end** (plan Task 2, Step 6). Skipped because it creates SEEK and FHIR records and needs user consent.
- **Other environments** with tools approved before this fix still need the repair snippet run against their `tools` bucket.
- **Browser cache after the repair:** portal-frontend serves `/tools/` with `Cache-Control: public, max-age=31536000, immutable` (`services/portal/frontend/nginx.conf.template`). The repair does not change any URL: `?v=<ts>` comes from the build's `created_at`, and worker and `itk/` URLs have no version. Anyone who opened an approved tool before the repair may keep getting the cached `binary/octet-stream` copies. After the repair they must hard-reload (Ctrl+Shift+R) or clear cached files for the portal origin. Cache-busting the bundle URLs would need a portal change, which is out of scope here.
