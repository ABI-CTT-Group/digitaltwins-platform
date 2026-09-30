# Register tool datasets in SEEK with a single RO-Crate POST

- **Date:** 2026-09-30
- **Status:** Accepted

## Context

Tool datasets (`category=tools`) are SDS folders with one `primary/tool_*.cwl` and the tool code in `code/`. They are stored like any other dataset: files in MinIO (`tools/<dataset_uuid>/...`) and metadata in platform Postgres. They must also appear in SEEK. SEEK has no tool type, so a tool is registered as a **Workflow** tagged `tool` plus its tool type (`script`, later `notebook` / `gui`). The portal already lists tools with `GET /workflows?filter[tag]=tool`. It builds each tool's inputs/outputs from the workflow's `internals`, and uses each input's `description` (the CWL `doc`) as the dataset category.

So SEEK must parse the CWL. A prototype (`services/api/app/routers/upload_workflow_to_seek`, untracked) got there in six calls: create, upload the blob, download the crate, re-POST it, PATCH, and delete the original. We checked SEEK's source in `ldh:v0.3.2` to see which of those calls are actually needed:

- `ContentBlobsController#update` saves the blob and calls `asset.touch`. `touch` skips `before_save :refresh_internals`, so after a JSON create plus blob PUT, `internals` stays empty.
- The RO-Crate POST (`WorkflowsController#handle_ro_crate_post` → `WorkflowCrateExtractor`, with `git_support_enabled = true` here) sets `main_workflow_path` from the crate's `mainEntity`, so `internals` is extracted on save.
- The crate reader takes the root `name` as the title and the root `keywords` as the tags (`workflow_extractors/ro_crate.rb`). The crate SEEK generates itself is named "Research Object Crate for …" and has no keywords. That is why the prototype's title was prefixed and its tags were lost.

## Alternatives Considered

### Option A: Keep the six-step prototype flow
- Pros: already tried by hand.
- Cons: six calls to SEEK; a PATCH to repair the title and tags; a create-then-delete dance. A failure midway leaves duplicate or half-created workflows. It also used a hardcoded token.

### Option B: JSON create with `internals` supplied by the client
- Pros: JSON only; no zip.
- Cons: we would have to parse the CWL ourselves into SEEK's internal structure, which duplicates SEEK's CWL extractor. `internals` isn't in the documented `workflowPost` schema. Setting a description still needs a PATCH (`workflowPost` has no `description`).

### Option C: Build a minimal Workflow RO-Crate and send one multipart POST
- Pros: one call. SEEK's own extractors set the title (CWL `label`), the description (CWL `doc`), the tags (crate `keywords`) and `internals`. Nothing to repair or delete. The request uses the caller's Keycloak JWT, like the rest of the SEEK integration.
- Cons: relies on RO-Crate submission, a WorkflowHub extension that isn't in SEEK's OpenAPI spec. We build `ro-crate-metadata.json` by hand.

## Decision

**Option C.** `digitaltwins.seek.writer.Writer.register_tool` builds the crate in memory (`ro-crate-metadata.json` + the CWL) and POSTs it to `{SEEK_BASE_URL}/workflows` with `workflow[project_ids][]`. The project comes from the required `seek_project_id` parameter.

The upload is **all-or-nothing**:
1. Postgres + MinIO first; `Uploader.upload_dataset` is already atomic.
2. Then SEEK.
3. Then `dataset.seek_id`.

If step 2 or 3 fails, the new dataset is deleted and the API returns 502. We did not add a `seek_status` column with a retry endpoint, as FHIR has, because tools are small and re-uploading is cheap. The link lives only in Postgres (`dataset.seek_id`). Deleting a tools dataset also deletes its SEEK workflow, best-effort, after the Postgres commit.

## Consequences

- A tool in SEEK always has parsed inputs and outputs. The portal needs no change to show them.
- The API depends on SEEK's RO-Crate submission behaviour. A SEEK upgrade that changes it would surface as a failure in the upload tests or in the manual check.
- Re-uploading a tool creates a new SEEK workflow. Versioning (`POST /workflows/submit` with `update_existing`) is future work.
- If SEEK is unavailable, tool uploads fail with 502 and nothing is stored. There is no partial state to reconcile.
- The crate POST must send only `Authorization`, with no `Accept: application/json`. With that header SEEK treats the call as JSON:API, requires a `data` record, and returns 422. This was verified live on 2026-09-30 (see `docs/artifacts/2026-09-30-122834-tool-dataset-upload/spike_seek_single_post.md`).
- Upload sessions need the caller's token when the commit runs. It is passed to the background job in memory and never stored. So a session left `failed` by a SEEK error is retried through `/approve`, which brings a fresh token.
