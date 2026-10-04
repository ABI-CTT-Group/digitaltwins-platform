# Walkthrough: link an assay to a workflow from "Configure assay"

Plan: [implementation_plan.md](implementation_plan.md) · Progress: [task.md](task.md) · ADR: [2026-10-05-link-assay-to-workflow-via-auto-created-sop.md](../../decisions/2026-10-05-link-assay-to-workflow-via-auto-created-sop.md)

## What changed

**What the user sees.** The assay's "Configure assay" dialog now opens with a **Select Workflow** dropdown. It lists only the SEEK workflows whose type (gui, notebook or script) matches the assay's tag **and** that belong to one of the assay's SEEK projects. For the Test Project (12) that means: script → `Workflow - Image conversion` (89), gui → `Workflow - VolView` (91), notebook → `Workflow - Cohort selection` (93).

- Picking a workflow loads its ports as the input and output rows, and clears the cohort.
- If a workflow was already linked, the dialog asks before resetting.

On **Save**:

1. The API links the workflow to the assay in SEEK. It creates an SOP `Workflow link: <title>` in the assay's project(s), with view access for those projects and a small `workflow-link.md` as its content.
2. It detaches the assay from any SOP that linked an earlier workflow. That SOP stays in SEEK.
3. It saves the Postgres config, as before.

If step 3 fails, steps 1 and 2 are undone.

**Bug fixed.** Assays with no linked workflow used to leave their configure pencil spinning forever, and the pencils of every assay after them too. They now open the dialog with an empty workflow to pick.

| Layer | File | Change |
|---|---|---|
| API | `services/api/src/digitaltwins/seek/writer.py` | Adds `create_sop` (POST a placeholder blob, then PUT its content; deletes the SOP if the upload fails), `set_sop_assays` (PATCH) and `delete_sop` |
| API | `services/api/src/digitaltwins/core/assay_workflow_link.py` (new) | `link_assay_workflow(querier, writer, assay_id, workflow_id) -> undo`: no-op if already linked, detaches SOPs that link a workflow, creates the new SOP |
| API | `services/api/app/routers/assays.py`, `app/schemas/assay.py` | `POST /assays` takes `link_workflow`. A workflow from none of the assay's projects gets 400 (`WorkflowNotInAssayProject`, raised by the link service before SEEK changes). It requires the admin or researcher role (otherwise 403), returns a SEEK failure as 502, and undoes the link when the save fails. Without the flag nothing changes. |
| Portal backend | `services/portal/backend/app/router/dashboard.py` | `POST /assay-details` returns 400 "Select a workflow" when none is set, and sends `link_workflow: true`. `category-children` takes the first SOP that links a workflow and adds the assay's `project_ids`. `/workflows` adds each workflow's `project_ids`. |
| Frontend | `composables/useAssayActions.ts` | Stub for an unlinked assay, try/catch for each assay, `openEdit` edits a copy |
| Frontend | `components/domain/AssayContent.vue` | The workflow `v-select` (filtered by `assayType` and `assayProjectIds`), the reset prompt, `loadInputDatasets()` |
| Frontend | `store/dashboard_cache_store.ts` | `workflows` and `setWorkflows`: the list is fetched once per page load |
| Frontend | `views/dashboard/components/AssayCard.vue`, `AssayConfigDialog.vue`, `models/types.ts` | Pass the assay's tag and projects down as `assayType` and `assayProjectIds` |
| Docs | `docs/populating_data.md`, `docs/api_examples.md`, `docs/decisions/2026-10-05-link-assay-to-workflow-via-auto-created-sop.md` | How to link in the portal and its rules; a manual SEEK recipe for the SOP link; the ADR |

## How we got here

- **Spike (Step 0)**, on the live local SEEK as admin1, using assay 42 and workflow 39:
  - The planned remote-URL content blob failed with 400 `bad upload`. SEEK fetches the URL anonymously, and a private workflow page returns 403.
  - A placeholder blob followed by a `PUT` of its content worked.
  - PATCH (detach and re-attach) and DELETE also worked.
  - The test SOP (34) was deleted afterwards.
  - The user then chose the generated-markdown content.
- **Test-first throughout.** Each new test was seen failing for the expected reason before the code was written. The frontend spec for `loadAssayList` reproduced the real crash (`Cannot set properties of undefined (setting 'type')`).

## Verification

| Suite | Result |
|---|---|
| API: `test_seek_writer.py`, `test_assay_workflow_link.py`, `test_assay_configure_api.py` | 21 + 7 + 5 passed |
| API, full suite (`PYTHONPATH=src:. pytest tests`) | 185 passed, 150 skipped, 4 failed, 1 error. All 5 also fail with this change stashed (see `task.md`). |
| Portal backend, full suite (outside the live container, `PORTAL_DB_HOST` unset) | 206 passed, 7 skipped |
| Frontend vitest | 17 files, 71 tests passed |
| `tsc -p tsconfig.json` | No errors in the touched `.ts` files. `vue-tsc` 1.2 crashes against the installed TypeScript; that problem predates this work. |
| Rebuild of api, portal-backend and portal-frontend | All 3 healthy |

**Test environment notes:**

- The repo `.venv` needed the pinned `fhir-cda==1.2.5` to import the API app.
- The portal backend tests ran in a scratch venv, with `psycopg2-binary` in place of `psycopg2`.

## End-to-end

Run 2026-10-05 as admin1, through the same portal backend calls the dialog makes, on Test Project (12):

- 16/16 checks pass.
- **Assay cards:** cards 41, 42 and 43 carry `project_ids` `["12"]`; none had a workflow before the test.
- **Dropdown filter** (type equals tag AND a shared project):

  | Assay | Offered | Type-only would offer |
  |---|---|---|
  | 41 notebook | 93 | 93, 40, 32, 33, 34 |
  | 42 script | 89 | 89, 39, 38 |
  | 43 gui | 91 | 91 |

- Save with no workflow → 400 "Select a workflow".
- **Link 42 → 89** (1.0 s):
  - SOP 35 `Workflow link: Workflow - Image conversion` links workflow 89, assay 42 and project 12.
  - Its `workflow-link.md` is 156 bytes.
  - Its policy is `no_access` plus `view` for project 12, read back as the owner.
  - The Postgres config has workflow 89, and the card shows it.
- Re-save with the same workflow → no new SOP (0.2 s).
- **Relink to 39** → SOP 35 detached (it still exists, with no assays) and SOP 36 created (2.3 s). **Relink back to 89** → SOP 37 (1.2 s). The Postgres config is on 89 again.
- **Cleanup:** deleted the detached test SOPs 35 and 36. **Final state:** assay 42 is linked to workflow 89 through SOP 37 and configured in Postgres with cohort [1], first matching dataset.
- **Not covered live** (covered by unit tests):
  - another project member viewing the SOP (only one user's token; the policy was confirmed)
  - a 403 for a non-researcher
  - rollback after a failed Postgres save
  - clicking through the dialog in a browser

