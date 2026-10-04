# Walkthrough: upload SDS workflow packages from the portal

This walkthrough covers how [plan.md](plan.md) was implemented. The design decisions are recorded in [ADR 2026-10-02-portal-sds-workflow-approval](../../decisions/2026-10-02-portal-sds-workflow-approval.md).

## The problem

The portal's Workflow wizard rejected `tests/data/workflow_image_conversion` with "No CWL files found in the root of the selected folder".

SDS-package detection was only switched on for tools (`BaseInformationStep.vue:296`, `props.type === 'tool'`), so a workflow needed a `.cwl` at the root of the folder. Every later stage made the same assumption:
- the build;
- the Annotation step, which mapped each step to a portal tool;
- approval, which was a placeholder stub.

## What changed

### Backend (`services/portal/backend`)

| File | Change |
|---|---|
| `app/builder/workflow_layout.py` (new) | Detects an SDS workflow package: `dataset_description.xlsx` plus exactly one `primary/workflow_*.cwl`. `inspect_workflow_source(staging, want_cwl, want_npm=False)` reports `is_sds`. `read_workflow_cwl` returns the workflow CWL and, for an SDS package, its tool CWLs as a list of `{cwl_file, content}`. It is a list, not a dict, because the frontend's camelCase interceptor would rewrite filename keys. |
| `app/builder/source_acquirer.py` | `SourceSpec.workflow_layout`. A workflow Git probe also returns `is_sds` and `tool_cwls`, and still returns the package.json version and author. |
| `app/builder/build_workflow.py` | Copies an SDS package through unchanged, without `.git`, `node_modules`, `dist` or `build`. The build fails when the SDS layout and `workflow_type` don't match. |
| `app/models/db_model.py` | `workflows.workflow_type` and `seek_project_id`. `workflow_builds` gains handoff columns that mirror `plugin_builds`. The pydantic models are extended. `init_db` → `migrate_add_missing_columns` adds the columns to an existing Postgres; all of them are nullable, so existing rows stay on the legacy path. |
| `app/services/tool_handoff.py` | Two parts are extracted: `tool_section(version, draft)` and `open_session(api, build, username, body)`. `run(build_id, build_cls=PluginBuild, complete=None)` is now parameterised. Tool behaviour is unchanged. |
| `app/services/workflow_handoff.py` (new) | `fhir_descriptions(workflow)` turns the `{"steps": [...]}` annotation into `{"workflow": {..., "action": [...]}, "workflow_tools": {<first step per tool>: ...}}`. It also provides `start`, `run`, and a `_complete` that, on re-approval, deletes the previous dataset with `delete_tools=true`. |
| `app/router/workflow_router.py` | **Authentication:** the whole router requires a token, and writes need `admin` or `researcher`, as on `/api/tools`. **Endpoints:** upload-source, `/cwl` and probe-source use the workflow layout. New `POST /{id}/approval` and `GET /{id}/approval/status`. The legacy `GET /{id}/approval` returns 409 for SDS workflows. **Delete:** for an approved SDS workflow, delete first calls `DELETE /datasets/{uuid}?delete_tools=true` in a worker thread. If the platform rejects the token, it returns "digitaltwins-api rejected the token; sign in again". |

### Frontend (`services/portal/frontend/src`)

| File | Change |
|---|---|
| `views/upload-dataset/components/utils.ts` | `sdsWorkflowCwls`, `sdsWorkflowCwlResult`, `noWorkflowCwlMessage`. |
| `composables/useLocalFolderInfo.ts`, `useGithubRepoInfo.ts` | `allowSds: boolean` is replaced by an `SdsKind` of `'tool'`, `'workflow'` or `null`. Both now return `isSds`. |
| `views/upload-dataset/components/BaseInformationStep.vue` | Passes `props.type` to the folder check (this is the fix for the reported error). For an SDS source it shows a workflow type radio (Script, Notebook or Web GUI), which is required; `workflowType` is sent only for SDS sources. |
| `views/upload-dataset/components/sds_workflow.ts` (new) | `sdsWorkflowSteps(workflowCwl, toolCwls)` returns each step with the ports of the tool it runs. It accepts map or list form, matches the tool on the basename of `run`, and strips a leading `#` from step ids. |
| `views/upload-dataset/components/BaseAnnotateStep.vue` | A new branch for SDS workflows. It loads the workflow and tool CWLs from a local source, public GitHub or the backend probe, and offers per-port FHIR resource selects (outputs are required, inputs optional). It submits `{"steps": [...]}`. Root-`.cwl` workflows keep the portal-tool picker. |
| `bootstrap/workflow_api.ts` | `useWorkflowPlatformApproval` and `useWorkflowApprovalStatus`. Workflow builds now carry `handoffStatus`. |
| `views/upload-dataset/components/ToolApprovalDialog.vue` | Serves both kinds through a `kind` prop. The `tool` prop was renamed `item`. The file kept its name. |
| `views/upload-dataset/components/WorkflowCard.vue` | **Approval:** an SDS workflow's "Submit to approval" opens the dialog. While a handoff is active the card polls its status, which relays fresh tokens, and shows "approving…" or "approval failed" chips. **Delete:** the card now deletes the workflow itself, as `ToolCard` does. On failure it shows the message in a toast and stops showing the card as busy. |
| `views/upload-dataset/workflow/WorkflowsOverallView.vue`, `workflow-tool/ToolsOverallView.vue` | Wire up the dialog and `onApprovalDone`; apply the `:item` rename. |

## Deviations from the plan

- **No commits.** Following the user's rule, every task left its changes uncommitted. Task diffs were reviewed as working-tree snapshot trees.
- **Task order.** The tasks ran in the order 1, 3, 3b, 2, 4–8. Task 3 also took Task 2's offline import check and `make_workflow_client`, because Task 3's test needs them.
- **Async delete.** `delete_plugin` runs the platform DELETE with `asyncio.to_thread`. The plan's snippet called a blocking 120 s httpx request directly inside an `async def`, which would have frozen the backend's event loop.
- **Final-review fixes.** The whole-branch review led to four further changes:
  - the workflow delete now reports failures instead of leaving the card stuck;
  - workflow Git probes keep their package.json version and author (the plan's snippet had dropped them);
  - `sdsWorkflowSteps` matches the tool on the basename of `run` and strips `#` from step ids, as the API does;
  - the annotation Submit no longer throws when there is no form.
- **Type check.** The project's `vue-tsc ^1.2` can't run against TypeScript 5; that was already broken. vue-tsc 2.2.10 with TypeScript 5.6 was run from a scratch directory and compared with a HEAD export: 12 errors before, the same 12 after.
- **Registration step.** There is no component spec for the Registration-step change (plan ruling). It is checked by the type check and the live run.

## Tests

| Suite | Before | After |
|---|---|---|
| Portal backend (isolated container, `--network none`) | 114 OK, 9 skipped | **141 OK, 9 skipped** |
| Frontend `yarn test` | 20 | **36 passed** |
| `yarn build` | — | OK |
| vue-tsc 2.2.10 | 12 errors | 12 errors (none new) |

The new backend tests are:
- `test_workflow_layout` (7)
- `test_workflow_sds_source` (6)
- `test_workflow_build_dataset` (5)
- `test_workflow_auth` (4)
- `test_workflow_handoff` (12)

The new frontend specs are:
- `useLocalFolderInfo` (5)
- `useGithubRepoInfo` (2)
- `sds_workflow` (4)
- `ToolApprovalDialog` (2)
- three more cases in `cards`

## Live verification

This is still pending. The user rebuilds and restarts `portal-backend` and `portal-frontend`, then runs Task 9 Step 3 of the plan:
1. upload `workflow_image_conversion` from a local folder;
2. annotate it, build it and approve it;
3. check SEEK, the API, HAPI and the Hub;
4. re-approve it, then delete it;
5. run the root-`.cwl` regression check;
6. run the authentication checks.

The new database columns are added when the backend starts (`init_db`).

## Known limitations (deferred)

- A folder with `dataset_description.xlsx` but no `primary/workflow_*.cwl` is now treated as a broken SDS package, even if it has a root `.cwl`. Tools follow the same rule.
- Deleting a workflow while its approval is still uploading can leave the new platform dataset behind; tools have the same gap. It then appears in the Hub as a "platform upload", which can be deleted.
- Steps that run the same tool share one ActivityDefinition, and the first step's annotation is used for it.
- The ActivityDefinition of each tool carries the workflow's version.
- `/api/workflow/metadata` and `/{expose}/primary/...` now need a token. No caller was found in the repo.
