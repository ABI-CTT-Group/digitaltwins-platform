# Plan: "tools" dataset upload (script type) → MinIO + Postgres + SEEK

## Context

`POST /datasets` and the resumable `/datasets/uploads` sessions handle measurement datasets well. Every other category goes straight to `Uploader.upload_dataset` with no validation and no SEEK registration. We want tool datasets (`category=tools`) to work end to end, starting with the **script** type. Each upload should:

- store the files in MinIO bucket `tools`, at `tools/<dataset_uuid>/...`
- store the metadata in platform Postgres, with the SEEK link in `dataset.seek_id`
- register the tool in SEEK as a **Workflow** tagged `tool` + `script`, with the CWL parsed so that `internals.inputs/outputs` are populated. The portal's `/workflow-detail` (`services/portal/backend/app/router/dashboard.py:262-304`) reads `internals[].description` as each input's dataset category.

A tool dataset follows SDS, with no `sub-*`/`sam-*` folders. `primary/` holds exactly one `tool_XXX.cwl`, and the tool itself lives in `code/`.

### Decisions (from the interview)

| Topic | Decision |
|---|---|
| SEEK project | Required `seek_project_id` query param for `category=tools` (400 if missing) |
| Tool type | Required `tool_type` param, `Literal["script"]` for now; it becomes the second SEEK tag |
| Failure mode | All-or-nothing. If SEEK fails, delete the new dataset (Postgres + MinIO) and return 502 |
| Linking | `dataset.seek_id` in Postgres only. The column exists, and `PostgresQuerier.get_dataset_uuid_by_seek_id` already reads it |
| Delete | `DELETE /datasets/{uuid}` also deletes the SEEK workflow, best-effort, after commit (like the FHIR cleanup) |
| SEEK title/description | From the CWL `label` / `doc`. Fall back to the CWL filename stem when there is no `label` |
| Validation | Minimal: `primary/` must contain exactly one `tool_*.cwl` (top level) |
| Scope | One-shot `POST /datasets`, resumable sessions, and a fix for `get_dataset(get_cwl=True)` |

## Review of the legacy SEEK flow (`upload_workflow_to_seek`)

I verified this against the SEEK source in the running `ldh:v0.3.2` container. `git_support_enabled` is `true` on this instance.

1. **JSON create + content-blob PUT (steps 1–2).** Both work, but SEEK never parses the CWL. `ContentBlobsController#update` saves the blob and calls `@asset.touch`. `touch` skips `before_save :refresh_internals`, so `internals` stays empty. That breaks the portal's tool inputs/outputs, and it's why the round-trip was needed.
2. **Download SEEK's crate, re-POST it, PATCH, delete the original (steps 3–6).** These are workarounds. The crate SEEK generates names its root `"Research Object Crate for <name>"` (`workflow_extraction.rb:174`) and has no `keywords`. SEEK's crate reader takes root `name` → title and root `keywords` → tags (`workflow_extractors/ro_crate.rb:71-75`), so the tags disappear. Every extra step can also leave orphans if it fails halfway: a duplicate workflow, or a half-created one.
3. **Security.** The script hardcodes a SEEK token, an IP and project 11, and its auth dependency is commented out. The file is untracked and the token was never committed. The token should still be **rotated**, and the file must not be committed.

**Replacement: one call.** Build a minimal Workflow RO-Crate in memory and send it as one multipart `POST {SEEK_BASE_URL}/workflows`:

- crate contents: `ro-crate-metadata.json` + the CWL file
- form fields: `ro_crate=<zip>` and `workflow[project_ids][]=<id>`
- auth: `Authorization: Bearer <caller's Keycloak JWT>`, which `keycloak_jwt_auth.rb` maps to the SEEK user

SEEK handles this in `WorkflowsController#handle_ro_crate_post` → `WorkflowCrateExtractor.build`:
- sets `main_workflow_path` from the crate's `mainEntity`, so `refresh_internals` runs on save
- takes the title from root `name` (the CWL label) and the description from root `description` (the CWL doc)
- takes the tags from root `keywords`: `["tool", "script"]`

So there's no PATCH, no delete and no duplicate. The crate is a hand-built dict plus `zipfile`, so there's no new prod dependency; `rocrate` is dev-only today.

## Implementation (TDD: failing test first for each step)

0. **Sync artifacts + ADR.** Copy this plan to `docs/artifacts/<YYYY-MM-DD-HHMMSS>-tool-dataset-upload/implementation_plan.md` and add `task.md`, which includes the `[ ] Sync artifacts to docs/artifacts/` items. Write the ADR `docs/decisions/2026-09-30-register-tools-in-seek-via-single-ro-crate-post.md`, using `docs/decisions/TEMPLATE.md`. It covers:
   - one crate POST vs the six-step legacy flow vs JSON create with client-supplied `internals`
   - all-or-nothing vs keep-and-retry
   - tools stored as SEEK Workflows with tags

   Redact everything; run `gitleaks detect --source docs/artifacts/ --no-git`.

0b. **Remove the hardcoded MinIO credentials from the example tool script.** `tests/data/sds_tool_dicom_to_nifti/code/tool_dicom_to_nifti.py` is a test fixture. `_get_s3_client` (~L38-40) falls back to `"minioadmin"` and to a secret that matches the **live** MinIO secret in local `secrets.env`/`.env`. It is in no git commit.
   - Change it to `os.environ["MINIO_ACCESS_KEY"]` / `os.environ["MINIO_SECRET_KEY"]`, with no defaults, so a missing variable fails loudly. The endpoint default `http://minio:9000` is not a secret and stays.
   - Rebuild `tests/data/sds_tool_dicom_to_nifti.zip`, which contains the same file, from the fixed folder. Keep the `sds_tool_dicom_to_nifti/` wrapper and the empty folders.
   - Verify: `grep -rF` for the old value across `tests/` (including `unzip -p` of the zip) returns nothing, and `gitleaks detect --source tests/ --no-git` is clean.
   - This is the only change to the example dataset. Its other issues (listed under Out of scope) are left for you.

1. **Spike against live SEEK** (manual, before writing code). Build the crate for `tests/data/sds_tool_dicom_to_nifti/primary/tool_dicom_to_nifti.cwl` and POST it with a real user token (placeholder `<REDACTED>` in the notes). Check:
   - it returns 200
   - the title is "Tool - dicom to nifti"
   - the tags are `tool, script`
   - `workflow_class.key == "cwl"`
   - `internals.inputs[0].description == "measurements"`

   Also confirm a multipart request with a Bearer JWT isn't rejected by CSRF, and delete the test workflow afterwards. If any check fails, stop and revisit the approach before continuing.

2. **Tool validation.** New `src/digitaltwins/tools/validation.py`: `find_tool_cwl(root) -> Path` raises `ValueError` unless `primary/` has exactly one top-level `tool_*.cwl`. It reuses `resolve_project_root` from `measurements/validation.py`.
   - Test `tests/test_tool_validation.py`: ok / none / two / wrong name / cwl only in a subfolder.

3. **SEEK writer.** New `src/digitaltwins/seek/writer.py`, class `Writer(api_token)`, following the `seek/querier.py` style (`SEEK_BASE_URL`, Bearer header, `RuntimeError` on failure):
   - `build_tool_crate(cwl_path, tool_type) -> bytes`
   - `register_tool(cwl_path, tool_type, project_id) -> int`
   - `delete_workflow(workflow_id)`

   Test `tests/test_seek_writer.py` with `requests` monkeypatched:
   - crate JSON: root name/description/keywords, `mainEntity`, `programmingLanguage` cwl
   - the stem fallback
   - the POST URL, headers and form fields
   - the id parsed from the response
   - `RuntimeError` on 4xx/5xx

4. **Tool commit unit.** New `src/digitaltwins/tools/pipeline.py`: `commit_tool(root, tool_type, seek_project_id, api_token, dataset_name=None) -> str`.
   1. `find_tool_cwl`
   2. `Uploader().upload_dataset(root, category="tools", dataset_name=...)`. This is already atomic across Postgres and MinIO.
   3. `Writer.register_tool`
   4. `UPDATE dataset SET seek_id`

   If step 3 or 4 fails, call `Deleter().delete_dataset(uuid)` (plus a best-effort SEEK delete if step 4 failed), then raise `SeekRegistrationError(RuntimeError)`. Order: Postgres/MinIO go first because their compensation is local and reliable; SEEK is the likelier failure.

5. **One-shot endpoint** (`app/routers/datasets.py`).
   - Add query params `tool_type: Optional[Literal["script"]]` and `seek_project_id: Optional[int]`. Both are required when `category == "tools"` (400 if missing).
   - Branch to `commit_tool` in the threadpool, passing `_creds["token"]`. `SeekRegistrationError` → 502.
   - Test `tests/test_datasets_tools_api.py`, in the style of `test_datasets_oneshot_api.py`. It uses `platform_db` plus a `FakeSeek` fixture modelled on `hapi`, and the real `tools` bucket with each created uuid prefix cleaned up in teardown. Cases:
     - happy path: `dataset.category == "tools"`, `seek_id` set, objects under `tools/<uuid>/primary/tool_*.cwl`
     - missing param → 400
     - bad structure → 400 and nothing stored
     - SEEK failure → 502 and no dataset row or objects left

   The tool dataset fixture is generated in `tmp_path` inside the test (CWL + `code/*.py` + `dataset_description.xlsx` copied from `tests/data/example_sds_dataset`). That way no secret-bearing file is committed.

6. **Resumable sessions** (`app/routers/dataset_uploads.py`, `measurements/jobs.py`).
   - Migration `src/digitaltwins/postgres/migrations/0002_upload_session_tool.sql` adds nullable `upload_session.tool_type varchar(20)` and `seek_project_id integer`. Pass them through `sessions.create_session`.
   - `INGEST_CATEGORIES = {"measurements", "tools"}`.
   - `SessionCreate` gets `tool_type` / `seek_project_id`. For tools: both are required, `fhir` must be `none` and `fhir_descriptions` must be null (400 otherwise).
   - In `finalize_upload`, tools use `find_tool_cwl` instead of `validate_sparc_structure`, and skip the `sampleless_subjects` warnings.
   - `run_commit_job(upload_id, api_token=None)` / `run_commit_and_push` branch to `commit_tool` for tools. `finalize` and `approve` pass `_creds["token"]` to the background task. The token stays in memory only and is never persisted. Keycloak token lifetime isn't a concern because the commit starts right after the request.
   - Tests: create → PUT parts → finalize → 202 → poll → `completed` with `seek_id`; tools + `fhir=auto` → 400; a SEEK failure leaves the session `failed` with no dataset (approve can then retry).

7. **Delete** (`core/deleter.py`, `postgres/deleter.py`, `app/routers/dependencies.py`).
   - `get_cleanup_info` also returns `category` and `seek_id`.
   - `Deleter(api_token=None)`; `get_deleter` takes `validate_credentials` and passes the token.
   - After commit, if `category == "tools"` and `seek_id` is set, call `Writer.delete_workflow`. Errors are logged, not raised.
   - Add `seek_deleted` to the response.
   - Tests: added to `tests/test_delete_dataset_cleanup.py` — SEEK delete called with the right id, and a SEEK error still gives a successful delete.

8. **Fix `get_dataset(get_cwl=True)`** (`core/querier.py:224-235`). Check `category == "tools"`. Read the single `primary/tool_*.cwl` object from the MinIO `tools` bucket (list with `MinioDownloader.list_dataset_objects(uuid, "tools")`, then `s3_client.get_object`) instead of iRODS, which is disabled, via the folder-name path, which is wrong. Then `yaml.safe_load`.
   - Test: returns the parsed CWL for an uploaded tool.

9. **Wrap-up.** Update the `POST /datasets` docstring and `docs/api_examples.md` with a tools example. Re-check the ADR against what actually happened, sync the artifacts, and run the full `pytest services/api/tests`.

### Files touched

- New: `src/digitaltwins/tools/{__init__,validation,pipeline}.py`, `src/digitaltwins/seek/writer.py`, `postgres/migrations/0002_upload_session_tool.sql`, and 4 test files.
- Modified: `app/routers/{datasets,dataset_uploads,dependencies}.py`, `measurements/{jobs,sessions}.py`, `core/{deleter,querier}.py`, `postgres/deleter.py`.

## Out of scope / notes for you

- **Example dataset `tests/data/sds_tool_dicom_to_nifti`** (untracked). Apart from removing the secret in step 0b, I won't modify it:
  - its xlsx files are copies of `curated_dataset`: MRI title, `subjects.xlsx`/`samples.xlsx` rows (which would create sub-1..3 rows for the tool), and a 450-row DICOM manifest
  - its CWL runs `python dicom_to_nifti.py`, but the file is `tool_dicom_to_nifti.py` and is never staged into the container, and SimpleITK is missing
- The removed fallback was the **live local MinIO secret**. It was never committed, so rotation is optional. It is advisable if the example folder or zip was ever shared outside this machine.
- The `tools` MinIO bucket is **public-read** (`services/minio/init-minio.sh`), so uploaded tool code is world-readable.
- The legacy `upload_workflow_to_seek` was deleted after manual verification (it was untracked). Its token should be rotated.
- Tools are created as new SEEK workflows. Re-upload / versioning (SEEK `POST /workflows/submit` with `update_existing`) is not included.
- The notebook and gui types come later: extend `tool_type` and the `code/` expectations.

## Verification

1. `pytest services/api/tests -m "not integration"` (unit: validation, writer, crate), then `pytest services/api/tests` with the stack up (integration: API, sessions, delete, get_cwl).
2. Manual end to end on the local stack:
   - `curl -F files=@tests/data/sds_tool_dicom_to_nifti.zip "http://localhost/digitaltwins-api/datasets?category=tools&tool_type=script&seek_project_id=<id>" -H "Authorization: Bearer <REDACTED>"` → 200 with `dataset_uuid`
   - MinIO browser `tools/<uuid>/` shows `primary/` + `code/`
   - `SELECT seek_id FROM dataset WHERE dataset_uuid=...`
   - `http://localhost/seek/workflows/<seek_id>` has tags tool/script, CWL inputs/outputs, and no duplicate
   - the portal catalogue lists the tool, and its detail page shows input category "measurements"
   - `GET /datasets/<uuid>?get_cwl=true` returns the CWL
   - `DELETE /datasets/<uuid>` removes the SEEK workflow too
3. `gitleaks detect --source docs/artifacts/ --no-git` before committing.
