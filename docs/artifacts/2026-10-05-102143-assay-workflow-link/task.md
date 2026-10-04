# Task: link an assay to a workflow from the Portal's "Configure assay" dialog

Plan: [implementation_plan.md](implementation_plan.md)

## Progress

- [x] Plan approved; copied to `docs/artifacts/`
- [x] Sync artifacts to docs/artifacts/
- [x] **Step 0, spike** against the local SEEK (admin1, assay 42, workflow 39; SOP 34 was created, then deleted)
  - [x] Remote-URL blob → 400 `bad upload`, because SEEK fetches the URL anonymously and the private workflow returns 403
  - [x] Fallback: a placeholder `workflow-link.md` blob, then a PUT of its content → works. The link, PATCH detach/re-attach and DELETE all work.
  - [x] Decision revised with the user: the SOP content is a generated markdown file
- [x] Sync artifacts to docs/artifacts/ (plan updated with the spike results)
- [x] **Step 1, API SEEK writer** (`seek/writer.py`): `create_sop`, `set_sop_assays`, `delete_sop`
  - [x] Red: 7 new tests in `tests/test_seek_writer.py` failed (`AttributeError`)
  - [x] Green: 21/21 pass
- [x] **Step 2, API link service** (`core/assay_workflow_link.py`): `link_assay_workflow(...) -> undo`
  - [x] Red: `tests/test_assay_workflow_link.py` failed (module missing)
  - [x] Green: 7/7 pass (covers: no-op, fresh link, relink detaching only SOPs that link a workflow, undo, failed create, failed detach, undo that keeps going after a failure)
- [x] **Step 3, API route**: `POST /assays` gets `link_workflow` (admin/researcher check, SEEK failure → 502, undo when the save fails)
  - [x] Red: `tests/test_assay_configure_api.py` failed (no `_link_workflow_in_seek`)
  - [x] Green: 5/5 pass
  - [x] Full API suite: 185 passed, 150 skipped, 4 failed, 1 error. All 5 also fail with my API changes stashed:
    - `test_delete_dataset_api` ×2
    - `test_minio::test_upload`
    - `test_upload_workspace_datasets_jupyter`
    - `test_upload_dataset_api::test_upload_zip`
  - Note: the repo `.venv` needed `fhir-cda==1.2.5` (the pinned prod dependency) to import the app
- [x] **Step 4, portal backend** (`router/dashboard.py`)
  - [x] `POST /assay-details`: 400 when no workflow is set; send `link_workflow: true`; remove the touched `print`s
  - [x] `GET /category-children`: use the first non-empty SOP workflow list
  - [x] Red: 3/3 failed in `tests/test_dashboard_assay_workflow_link.py` (KeyError / ValueError / None). Green: 3/3 pass.
  - [x] Full portal backend suite: 204 passed, 7 skipped. Run outside the live container, in a scratch venv with `PORTAL_DB_HOST` unset and psycopg2-binary installed.
- [x] Sync artifacts to docs/artifacts/
- [x] **Step 5, frontend**
  - [x] `useAssayActions.loadAssayList`: stub when there is no workflow (no more `undefined` workflow-detail call, so no crash); try/catch for each assay that shows a toast
  - [x] `openEdit`: edits a JSON copy, so Cancel leaves the cache alone
  - [x] Pass the `assayType` prop: AssayCard → AssayConfigDialog → AssayContent
  - [x] AssayContent: "Select Workflow" `v-select` filtered by `assayType`; asks before resetting when a workflow is already linked; `loadInputDatasets()`; removed the read-only name and its fetch
  - [x] Workflow list cached in `dashboard_cache_store` (`workflows`, `setWorkflows`), fetched once per page load
  - [x] vitest. Red first, each time:
    - `useAssayActions.spec.ts`: 3, including the crash reproduction `Cannot set properties of undefined (setting 'type')`
    - `AssayContent.spec.ts`: 5 new
    - `AssayConfigDialog.spec.ts`: 1
    - Green: full suite 17 files, 70 tests passed
  - Note: `vue-tsc` (1.2) crashes against the installed TypeScript (`Search string not found: supportedTSExtensions`). This tooling problem predates this work, and `yarn build` doesn't type-check.
- [x] Sync artifacts to docs/artifacts/
- [x] **Step 6, docs**
  - [x] ADR `docs/decisions/2026-10-05-link-assay-to-workflow-via-auto-created-sop.md`
  - [x] "Configure assay" notes: not stored in the repo, so nothing to update. The ADR and the walkthrough describe the new rules.
  - [x] Walkthrough ([walkthrough.md](walkthrough.md))
  - [x] Project docs: `docs/populating_data.md` (how to link an assay to its workflow in the portal, and the rules) and `docs/api_examples.md` (manual SOP-link recipe: placeholder blob + PUT, policy, detach PATCH, why remote-URL blobs fail)
- [x] Sync artifacts to docs/artifacts/ and run gitleaks
- [x] Rebuilt api, portal-backend and portal-frontend (all healthy)
- [x] **Follow-up (user request): only offer workflows from the assay's project**
  - [x] Checked live SEEK: assays 41, 42 and 43 are in project 12. Before this change, script assay 42 was also offered workflows 38 and 39 from project 11 (Breast). After it, script → 89, gui → 91, notebook → 93.
  - [x] Portal backend: `project_ids` on assay cards (`category-children`) and on `/dashboard/workflows` items. Red 2/2 → green; full suite 206 passed, 7 skipped.
  - [x] Frontend: `projectIds` on `DashboardCategory` and `DashboardWorkflow`; `assayProjectIds` prop AssayCard → AssayConfigDialog → AssayContent; filter on type AND a shared project. Red 3 → green; vitest 71 passed; tsc clean for the touched `.ts` files.
  - [x] Plan, ADR and walkthrough updated; rebuilt portal-backend and portal-frontend
- [x] **Follow-up (user request): the API rejects a workflow from another project**
  - [x] `link_assay_workflow` raises `WorkflowNotInAssayProject(ValueError)` before any SEEK change when the workflow shares no project with the assay. It is skipped when the assay is already linked to that workflow (a no-op re-save).
  - [x] `POST /assays` returns 400 with the message
  - [x] Red (import error) → green: 36 passed across link, route and writer tests. Full API suite: 188 passed; same 5 failures as before.
  - [x] ADR, plan and walkthrough updated; API image rebuilt
  - [x] Live check (2026-10-05, admin1, scratchpad `e2e_cross_project.py`), 4/4 pass:
    - linking assay 42 → workflow 39 (project 11) returns 400 "Workflow 39 is not in any of assay 42's projects (12)."
    - SEEK unchanged (SOPs [37]) and Postgres unchanged (workflow 89)
    - re-saving 42 → 89 returns 200 and adds no SOP
  - Note: the dialog's toast (`getApiErrorMessage`) never shows the server's `detail`, so this shows only "Save failed, please try again." The portal backend also passes the API error body through as a JSON string. Both are existing behaviour and unchanged.
- [x] **End-to-end**, 2026-10-05 as admin1, through the portal API the dialog uses (scratchpad `e2e_link.py`)
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
