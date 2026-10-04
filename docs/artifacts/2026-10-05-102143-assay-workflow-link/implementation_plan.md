# Plan: link an assay to a workflow from the Portal's "Configure assay" dialog

## Context

The portal finds an assay's workflow only through SEEK: Assay → SOP → Workflow. Today that link has to be built by hand in SEEK. That means creating an SOP, attaching it to the assay, and attaching the workflow to it. Until someone does, the assay can't be configured from the portal.

There is also a bug. When an assay has no linked workflow, `loadAssayList` crashes. In [useAssayActions.ts:56](services/portal/frontend/src/composables/useAssayActions.ts#L56), `useDashboardWorkflowDetail(undefined)` returns `null`, and setting `.type` on it throws. Because the loop isn't awaited, the error goes unhandled. The pencil on that assay and on every assay after it then spins forever.

**Outcome:** on the study dashboard (e.g. `/study-dashboard?trail=7,12,10,11`), an admin or researcher opens "Configure assay" and picks a workflow from a dropdown. The dropdown lists only workflows whose type matches the assay's tag. The form rebuilds its input and output rows from that workflow's ports. On **Save**, the API:

1. Creates a new SEEK SOP that links the assay to the workflow. It is placed in the assay's project(s) and those projects get view access.
2. Detaches the assay from any SOP that links it to a previous workflow.
3. Writes the Postgres config (`assay.workflow_seek_id` and the inputs and outputs) as it does today.

If the Postgres write fails, the SEEK changes are rolled back.

### Decisions from the interview

| Topic | Decision |
|---|---|
| Where the link lives | SEEK SOP (the provenance record) plus Postgres `workflow_seek_id` (the run config) |
| Relinking | Replace and reset: detach the old workflow SOP from the assay (the SOP stays in SEEK), link the new one, and reset inputs, outputs and cohort. Ask the user to confirm first. |
| SOP reuse | One new SOP per assay link |
| Type match | The dropdown is filtered to workflows whose `type` equals the assay's SEEK tag (gui, notebook or script). No tags are written. |
| Project match (added 2026-10-05, user request) | The dropdown also lists only workflows that share a SEEK project with the assay. `/dashboard/workflows` items and assay cards carry `project_ids`. The API enforces it too: `WorkflowNotInAssayProject` returns 400 before any SEEK change (only when a new link would be created). |
| SOP content | ~~A remote URL blob~~ (doesn't work for private workflows, see Step 0 results). **Revised 2026-10-05:** a generated `workflow-link.md` placeholder blob, then a PUT of a small markdown body naming the assay and the workflow. |
| Timing | Selecting a workflow only changes the form locally. All SEEK writes happen on dialog Save. |
| Visibility | A `policy` with `access: no_access` and a `view` permission for each of the assay's projects |
| Roles | Linking requires `admin` or `researcher`, using the existing `require_upload_role` |

### SEEK API, checked read-only against the running `ldh:v0.3.2`

- `sopPost` in `/seek/public/api/definitions/_schemas.yml` accepts:
  - `attributes`: `title`, `description`, `policy`, and `content_blobs: [{url, original_filename?, content_type?}]` (the `remoteContentBlob` shape)
  - `relationships`: `projects` (required), `assays`, `workflows`
  - This means a single JSON:API `POST /sops` creates the SOP and both links.
- `sopPatch` accepts `relationships.assays`. That is how the assay gets detached from an old SOP.
- `assayPatch` has no `sops` relationship.
- `Sop has_and_belongs_to_many :workflows`.

## Approach

### Step 0 results (spike run 2026-10-05 as admin1 on assay 42 and workflow 39; SOP 34 was created and then deleted)

- **The remote-URL blob doesn't work.** `POST /sops` returned `400 {"error":"bad upload"}`.
  - SEEK checks the URL when the SOP is created (`lib/seek/upload_handling/data_upload.rb` `process_from_url`), without logging in.
  - Workflow pages are private, so they return 403 even when fetched from inside the SEEK container.
- **The fallback works.** Create the SOP with `content_blobs: [{original_filename: "workflow-link.md", content_type: "text/markdown"}]` (200), then `PUT /sops/{id}/content_blobs/{blob_id}` with `Content-Type: application/octet-stream` and a small generated markdown body (200).
  - Afterwards the SOP's `workflows` = [39], `assays` = [42] and `projects` = [12], and the assay's `sops` = [34].
- `PATCH /sops/{id}` with `relationships.assays` set to `[]` detaches the assay. Re-attaching works the same way. `DELETE /sops/{id}` returns 200.
- The response shows `policy` as null. SEEK's serializer only shows the policy when `can_manage?(current_user)` is true, and the API converter does accept `policy`. That another project member can see the SOP will be checked in the end-to-end test.
- Because the URL blob is dropped, `SEEK_PUBLIC_URL` is no longer needed. The markdown body names the assay and the workflow by id and title.

### Step 0: spike against the local SEEK (throwaway, in the scratchpad)

This step checks behaviour the schema alone can't confirm. It uses a researcher token and the test project's assay (`trail=7,12,10,11` → assay 11). It confirms:

1. `POST /sops` with a remote `url` blob, a `policy`, and `projects`/`assays`/`workflows` returns 201. Headers are `Accept` and `Content-Type: application/vnd.api+json`, as in `util/populate-cpu-burn-assay.sh`.
2. Whether SEEK fetches the URL when the SOP is created. This decides whether the URL must be reachable from inside the SEEK container.
3. `GET /assays/11` then lists the SOP, and `GET /sops/{id}` lists the workflow.
4. Another member of the project can see the SOP.
5. `PATCH /sops/{id}` with `relationships.assays: []` detaches the assay.
6. `DELETE /sops/{id}` works.

The spike cleans up everything it created. If any check fails, I'll stop and come back to you before going further.

### Step 1: API SEEK writer (`services/api/src/digitaltwins/seek/writer.py`)

Add three methods to `Writer`, in the same style as `delete_workflow`. Each uses JSON:API headers, raises `RuntimeError(_seek_error(resp))` on a status of 300 or above, and uses plain `requests` with the user's token.

- `create_sop(title, description, project_ids, assay_id, workflow_id, content: str) -> int`: a POST with a placeholder blob (`workflow-link.md`, `text/markdown`), the policy and all three relationships, then a PUT of `content` to the returned blob link (`Content-Type: application/octet-stream`). If the PUT fails, it deletes the SOP and then raises.
- `set_sop_assays(sop_id, assay_ids)`: PATCH `relationships.assays`
- `delete_sop(sop_id)`: used only for rollback

### Step 2: API link service (new, `services/api/src/digitaltwins/core/assay_workflow_link.py`)

`link_assay_workflow(seek_querier, seek_writer, assay_id, workflow_id) -> undo` works like this:

- Reads the assay (and its `relationships.sops` and `projects`), each SOP's workflows, and the workflow's title.
- **No-op** if the assay's effective workflow (the first workflow found across its SOPs) already equals `workflow_id`. It returns an undo that does nothing.
- Otherwise:
  - For every SOP of the assay that links a workflow, it PATCHes the SOP's assays without this one. SOPs that link no workflow are left alone.
  - It then calls `create_sop` with:
    - title `"Workflow link: <workflow title>"`
    - a description stating that the portal created it
    - the assay's projects
    - markdown content naming the assay and the workflow (id and title), and saying the portal created it
- The returned `undo` deletes the new SOP and re-attaches the assay to the SOPs it was detached from. Rollback is best-effort and logged, the same as `_undo` in `workflows/pipeline.py`.

### Step 3: API route (`services/api/app/routers/assays.py`, `POST /assays`)

- Add an optional `link_workflow: bool = False` to `AssayDataModel` (`app/schemas/assay.py`).
- When it is true, the route:
  1. Checks the role using `credentials["claims"]`. It returns 403 unless the user is admin or researcher, using the same rule as `require_upload_role` (factor that rule into a small helper rather than duplicating it).
  2. Builds the SEEK querier and writer for the user's token and calls `link_assay_workflow`.
  3. Calls `configure_assay`. If that fails, it runs `undo()` and then raises.
  4. Returns a SEEK failure as a 502 with the SEEK error text.
- When it is false, nothing changes. This keeps `util/populate-cpu-burn-assay.sh` working: it uses the fake workflow id 9000 and doesn't link anything.
- Why it's a flag on the existing route and not a new endpoint: the SEEK link and the Postgres write then happen in one request, with one rollback. Two separate portal-backend → API calls would leave the two stores out of sync whenever the second call failed. This is recorded in the ADR.

### Step 4: portal backend (`services/portal/backend/app/router/dashboard.py`)

- `POST /assay-details`:
  - Return 400 "Select a workflow" when `workflow.seek_id` is empty. Today `int("")` raises an error there.
  - Send `"link_workflow": True`.
  - Remove the `print`s on lines 384 and 386 that this change touches.
- `GET /category-children` (around L164): use the first **non-empty** SOP workflow list, not `workflows_rel[0]`. Otherwise an assay whose first SOP links no workflow would show none.

### Step 5: frontend

- **[useAssayActions.ts](services/portal/frontend/src/composables/useAssayActions.ts)**
  - `loadAssayList`: when `item.workflowSeekId` is missing, cache a stub with `workflow: {seekId: "", uuid: "", name: "", type: item.tag, inputs: [], outputs: []}`. Wrap each assay in try/catch so one failure doesn't stop the loop.
  - `openEdit`: `structuredClone` the cached details, so that cancelling the dialog doesn't leak edits into the cache. Choosing a workflow mutates the form, so this matters now.
  - `save`: after it succeeds, write the edited copy back into the cache (it already does).
- **[AssayCard.vue](services/portal/frontend/src/views/dashboard/components/AssayCard.vue) → [AssayConfigDialog.vue](services/portal/frontend/src/views/dashboard/components/AssayConfigDialog.vue) → [AssayContent.vue](services/portal/frontend/src/components/domain/AssayContent.vue)**: pass the assay's tag down as a new `assayType` prop.
- **AssayContent.vue**
  - Replace the read-only workflow name (lines 3-8) with a `v-select`.
    - Its items come from `useDashboardWorkflows()`, filtered to `w.type === assayType`, with label `name` and value `seekId`.
    - The rule is "Please select a workflow".
    - If no workflows match, it shows "No <type> workflows registered".
  - When the selection changes and the current form has any input or output rows, ask the user to confirm the reset. Then:
    1. `useDashboardWorkflowDetail(id)`
    2. Replace `workflow` (seekId, name, type, inputs, outputs)
    3. Clear the cohort
    4. Rebuild the per-input dataset maps
  - Pull the dataset-map logic in `onMounted` (lines 180-192) out into a `loadInputDatasets()` function that runs on mount and after a switch.
  - Keep your uncommitted `'measurements'` fix as it is.
- **Workflow list caching**: `/dashboard/workflows` makes one SEEK call per workflow. Fetch it once per page load and keep it in `dashboard_cache_store` (`workflows` and `setWorkflows`), to match the existing caching style.

### Step 6: docs

- **ADR** `docs/decisions/2026-10-05-link-assay-to-workflow-via-auto-created-sop.md`, from `TEMPLATE.md`, covering:
  - SOP and Postgres vs Postgres-only vs a direct link
  - a new SOP per link vs reuse
  - a flag on `POST /assays` vs a new endpoint
  - filtering by tag
- **Artifacts**: copy this plan into `docs/artifacts/2026-10-05-<HHMMSS>-assay-workflow-link/` as the first implementation action. Sync it again after every update, and add a walkthrough at the end. Check for secrets before each sync.
- Update the "Configure assay" notes you pasted, where they are kept in the repo, to describe the new rules:
  - you can pick the workflow
  - linking creates an SOP
  - the first save no longer freezes the workflow

## TDD order, with verification for each step

1. Writer tests in `services/api/tests/test_seek_writer.py`, faking `requests.post`/`patch`/`delete` with the existing `FakeResponse`. They assert the URL, the JSON:API headers, and the payload: `policy`, the placeholder `content_blobs[0]`, the blob PUT, and the `projects`/`assays`/`workflows` relationships. Also the error path. Red → implement step 1 → green.
2. Link-service tests in a new `services/api/tests/test_assay_workflow_link.py`, using a fake querier and writer. Cases:
   - no-op when already linked
   - a fresh link creates one SOP
   - a relink detaches only SOPs that link a workflow
   - `undo` deletes the new SOP and re-attaches the old ones
   - green after step 2
3. Route tests, overriding `validate_credentials` and monkeypatching the link service. Cases:
   - `link_workflow=false` takes the old path unchanged
   - `true` without the role → 403
   - `configure_assay` raises → undo was called and the response is 500
   - a SEEK error → 502
4. Portal backend tests (pattern: `services/portal/backend/tests/test_dashboard_assay_download.py` with an `AsyncMock` client):
   - `POST /assay-details` forwards `link_workflow` and returns 400 when the workflow is empty
   - `category-children` picks the first non-empty workflow list
5. Frontend vitest (pattern: the untracked `components/domain/__tests__/AssayContent.spec.ts`; add `useDashboardWorkflows` to the `vi.mock`):
   - the dropdown is filtered by `assayType`
   - choosing a workflow replaces inputs and outputs and loads datasets for the new categories
   - `useAssayActions.loadAssayList` stores a stub for a null `workflowSeekId` and carries on to the next assay
   - `openEdit` clones
6. Run the suites:
   - API: `pytest services/api/tests/test_seek_writer.py services/api/tests/test_assay_workflow_link.py …`
   - frontend: `cd services/portal/frontend && yarn test`
   - portal backend: run its tests **outside** the live container (its unittest suite runs `drop_all()` on the live Postgres when `PORTAL_DB_HOST` is set)
7. End to end on `http://localhost/study-dashboard?trail=7,12,10,11`, after rebuilding the api, portal-backend and portal-frontend:
   1. The assay with no workflow now shows a working pencil.
   2. Open the dialog. Only workflows matching the tag are listed. Pick one, fill the form, and Save.
   3. In SEEK, the assay now has a new SOP that links the workflow, belongs to the assay's project, and is visible to another project member.
   4. Postgres `assay.workflow_seek_id` is set.
   5. Reload: the card shows the workflow, and Launch works for a script assay.
   6. Switch to another workflow. The old SOP is detached and still exists, and a new SOP is linked.
   7. Cancel without saving. Nothing changes in the cache or in SEEK.

## Out of scope

- Writing assay tags
- Reusing SOPs across assays
- Deleting old SOPs
- Linking multiple workflows to one assay
- Fixing the `AssayConfigDialog` save spinner, which doesn't await the save
- The N+1 SEEK calls in `/dashboard/workflows` (they are cached client-side instead)
