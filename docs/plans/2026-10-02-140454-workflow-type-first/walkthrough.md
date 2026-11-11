# Walkthrough: workflow type first; SDS detected by the build

- **Date:** 2026-10-02
- **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)
- **ADR:** [2026-10-02-workflow-type-independent-of-sds](../../decisions/2026-10-02-workflow-type-independent-of-sds.md) (Accepted). It supersedes decision 2 of [2026-10-02-portal-sds-workflow-approval](../../decisions/2026-10-02-portal-sds-workflow-approval.md).
- **Branch:** `dev_chinchien`. Committed as 7 Conventional Commits, one per plan task, from `7cab9689` to this docs commit. The Annotation-step commit also carries the final-review fix.

## What changed

### Backend (`services/portal/backend`)

| Area | Change |
|---|---|
| `app/models/db_model.py` | New column `Workflow.is_sds` (Boolean, nullable). `WorkflowCreate.workflow_type` is now required. `WorkflowResponse.is_sds` is added. |
| `app/database/database.py` | `migrate_workflow_is_sds` adds the column and backfills `is_sds = (workflow_type IS NOT NULL)` in one transaction, **only when the column is missing**. It runs before `migrate_add_missing_columns`. |
| `app/builder/build_workflow.py` | The rule "a type needs an SDS package" is removed. A successful build returns `is_sds` from `detect_workflow_layout`. |
| `app/utils/builder_utils.py` | After a successful build, `result["is_sds"]` is copied to `build_record.workflow.is_sds` when the result has it. Only workflow builds return it. |
| `app/router/workflow_router.py` | `/cwl` returns `is_sds`. The SDS approval and the legacy approval's refusal check `is_sds`. Platform delete checks `in_platform(workflow)` alone. |

### Frontend (`services/portal/frontend/src`)

| Area | Change |
|---|---|
| `views/upload-dataset/components/BaseInformationStep.vue` | The workflow type radio is at the top of the form, always shown, defaults to `script`, and lists Script, Notebook, Web GUI. The tool radio uses the same order and defaults to `Script`. `hasBackend` defaults to `false`. The workflow payload always sends `workflowType`. |
| `views/upload-dataset/components/workflow_cwls.ts` (new) | `loadWorkflowCwls` reads a workflow's CWL from a local, public GitHub or probed source, and works out `isSds` from that source. |
| `views/upload-dataset/components/BaseAnnotateStep.vue` | It uses the new loader. `isSdsWorkflow` is now a ref set from the source, and a progress bar shows while the CWL loads. A load error is shown for any workflow, SDS or not. The tool probe helper no longer takes a `kind`. |
| `views/upload-dataset/components/WorkflowCard.vue` | "Submit to approval" goes to the platform when `isSds` is set. |
| `views/upload-dataset/workflow/UploadWorkflowForm.vue` | The submit handler is typed `WorkflowInformationStep` (see the rulings). |
| `models/types.ts`, `bootstrap/workflow_api.ts` | `WorkflowResponse.isSds` added. `WorkflowInformationStep.workflowType` is required. The `/cwl` response type has `isSds`. |

## Verification

| Check | Result |
|---|---|
| Backend suite, in a throwaway container with no network | 151 tests, OK, 9 skipped. Baseline was 141. New: 3 for the migration, 2 for the executor, 3 for create, 1 for `/cwl`, 1 for approval. One build test was replaced. |
| Frontend `npx vitest run` | 46 tests passed. Baseline was 36. New: 1 card test, 4 loader tests, 4 registration form tests, 1 Annotation step test (added in the review fix). |
| Frontend `vite build` (Node 20 container) | Built. |
| Type check | `vue-tsc` crashes before it checks anything; that was already broken, see below. The one type error this change caused was proven and fixed with plain `tsc` on a mirror of the signature. |
| Manual check on the dev stack (plan, Task 7 Step 4) | **Not run.** It rebuilds the running portal containers, so it waits for the user's go-ahead. |

Every new test was run and seen to fail before the code change, and the failure was the expected one.

## Rulings made during implementation

- **Commits only on request.** The user's global instructions say to commit only when asked; the user then asked, and the work went in as one commit per task.
- **Task 5:** a CWL load failure is now caught into `loadError`. The final review showed this hid the error for SDS packages too, because SDS status now comes from that same load. Fixed: the error is shown for any workflow (see below).
- **Task 6:** making `workflowType` required broke `UploadWorkflowForm.vue`'s `handleSubmit(data: BaseInformationStep)` with TS2345. The handler is now typed `WorkflowInformationStep`.

## Known issue outside this change

`vue-tsc --noEmit` crashes on Node 18 and Node 20 with `Search string not found: "/supportedTSExtensions = .*(?=;)/"`. The project's `vue-tsc ^1.2` doesn't work with the TypeScript version it resolves. Until it is upgraded, `.vue` files get no type checking.

## Final review

A fresh reviewer (Opus) reviewed the whole change. It found no Critical issues and one Important issue: SDS load errors were hidden. That issue is fixed, with a test that failed first and then passed: `BaseAnnotateStep.spec.ts`, "says why a workflow's CWL could not be read…". After the fix, all 46 frontend tests pass and the build works.

Deferred Minor findings:

- **Layout change after approval.** If an SDS workflow is approved and its repo then becomes a root-`.cwl` workflow, the legacy approval can reuse the real platform UUID, and a later delete skips FHIR cleanup.
- **Overlapping builds.** If two builds overlap, the older one finishing last can overwrite `is_sds`. Approval is still safe, because it requires the latest build to have completed.
- **Tool payload.** The tool create payload now also carries `workflowType: 'script'`, from the form data the two wizards share. The backend ignores it.
- **Test gaps.** There is no test for a rebuild flipping `is_sds` from true to false, and none for deleting a typed workflow that has a placeholder UUID.
- **Unbuilt SDS workflows.** "Submit to approval" on an SDS workflow that hasn't been built takes the legacy path, which returns a 500. That 500 already existed.
- **ADR wording.** "Approval always follows the latest completed build" is true only for the POST approval.
