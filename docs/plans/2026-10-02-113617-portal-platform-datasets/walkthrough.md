# Walkthrough: platform workflows and tools in the portal

Implements [plan.md](plan.md), with option B for the dialog's tool list (a new read endpoint).

## What changed

### API (`services/api`)

| File | Change |
|---|---|
| `app/routers/datasets.py` | New `GET /datasets/{uuid}/workflow-tools` → `{workflow_type, tools: [{dataset_uuid, dataset_name, seek_id, step_ids}]}`. A non-workflow gets `null` / `[]`, and an unknown uuid gets `404`. It reuses `workflows.pipeline.linked_tools`, so it matches the delete's 409. |
| `tests/test_datasets_workflows_api.py` | 3 cases: a script workflow, a non-workflow, and an unknown dataset. |
| `README.md` | One line under "Deleting". |

### Portal frontend (`services/portal/frontend`)

| File | Change |
|---|---|
| `src/bootstrap/platform_api.ts` (new) | `usePlatformWorkflows(known)`, `useWorkflowTools(uuid)`, `deletePlatformDataset(uuid, deleteTools?)` and `datasetInUse(err)`, which reads the API's 409 (snake_case) into camelCase `PlatformLink`s. |
| `src/bootstrap/workflow_api.ts` | `useWorkflowHub()`: portal workflows plus platform-only ones. If the platform is down, only the latter are hidden. |
| `src/models/types.ts` | `WorkflowResponse.platformOnly` and `workflowType`, and a new `PlatformLink`. |
| `src/views/upload-dataset/components/DeletePlatformDatasetDialog.vue` (new) | The confirmation dialog, described below. |
| `components/WorkflowCard.vue` | A platform-only workflow shows `<workflowType>` and "platform upload" chips. Its menu is only **Delete workflow**, which emits `delete-platform`. The portal menu is unchanged. |
| `components/ToolCard.vue` | A platform-only tool's menu is **Delete tool** (`delete-platform`); before, it had no menu. Portal tools are unchanged. |
| `workflow/WorkflowsOverallView.vue` | Uses `useWorkflowHub`. "In platform" now includes platform-only workflows. `delete-platform` opens the dialog, and `deleted` refreshes the list. |
| `workflow-tool/ToolsOverallView.vue` | `delete-platform` opens the dialog (`kind="tool"`), and `deleted` refreshes the list. |
| `package.json`, `yarn.lock`, `vite.config.ts`, `src/testing/{setup,vuetify}.ts` | The vitest setup, described below. |

### How the dialog works

**Workflow:**
1. It lists the tool datasets from `GET …/workflow-tools`, with their steps.
2. It offers three buttons: **Cancel**, **Delete workflow only** (`delete_tools=false`) and **Delete workflow and its N tools** (`delete_tools=true`). A workflow without tools gets a single **Delete workflow** button.

**Tool:**
- It offers **Cancel** and **Delete tool**.
- On a 409 it shows "Used by workflow(s): … Delete the workflow first." and keeps the tool.

**Errors:** other errors are shown in the dialog. A dataset is deleted only after an explicit click.

### Test setup

- **Dependencies:** `vitest` ^3.2.4, `jsdom` ^26.1.0 and `@vue/test-utils` pinned to **2.4.6**. Later releases need `js-beautify` 2, whose `nopt` 10 requires Node 22, while the build image is `node:20-alpine`.
- **Script:** `yarn test` runs `vitest run`.
- **Location:** the helpers live in `src/testing/`, not `src/test/`, because the portal's `.gitignore` ignores every folder named `test`.
- **`setup.ts`:** stubs `ResizeObserver` and `visualViewport`, which jsdom lacks and Vuetify overlays use.
- **`testVuetify()`:** mounts components with a real Vuetify.
- **Lockfile:** `yarn.lock` was updated with Yarn 1.22.22 (bundled in `node:20`). Existing package versions are unchanged; only some range headers were merged. A clean `yarn install --frozen-lockfile` passes. `package-lock.json` is not used by the Dockerfile and was not updated, so it is now stale.

## Verification

- **API:** the full suite has 314 passed (+3), with the same 4 failed and 1 error as before (all legacy).
- **Frontend `yarn test`:** 20 passed in 5 files.
  - `platform_api.spec.ts`: 6
  - `workflow_hub.spec.ts`: 2
  - `DeletePlatformDatasetDialog.spec.ts`: 7
  - `cards.spec.ts`: 4
  - `vuetify.spec.ts` (setup smoke test): 1
- **Type-check:** run with vue-tsc 2.2.10 and TypeScript 5.6, installed in a temporary directory. The project's own `vue-tsc` ^1.2 can't run against its TypeScript 5; that was already broken, and no script uses it.
  - The new and changed code has 0 errors (the dialog's two boolean bindings were fixed).
  - 12 errors remain, all already present in the committed code. These include `ToolsOverallView.vue:10` (`handoffStatus`), the `v-for` over `items` in `WorkflowsOverallView.vue`, and `glslify` typing in `vite.config.ts`.
- **`yarn build`:** succeeds.

## Live check (2026-10-02)

The user rebuilt `digitaltwins-api` and `portal-frontend` and deleted the platform workflow `workflow_image_conversion` and its tools from the portal ("delete worked"). Afterwards:

- **Postgres:** the dataset rows `a8d6da0e-…` (workflow), `a89fa502-…` and `a8b7d12c-…` (tools) are gone. `workflow_tool` is empty, and no dataset has `workflow_type` set.
- **SEEK:** workflows 72, 70 and 71 return 404.
- **HAPI:** PlanDefinition/1410 and ActivityDefinition/1408 and /1409 return 410 (deleted).
- **MinIO:** `workflows/a8d6da0e-…/`, `tools/a89fa502-…/` and `tools/a8b7d12c-…/` hold 0 objects.

The planned checks were:

1. `/upload-workflow-dataset` lists `workflow_image_conversion` (dataset `a8d6da0e-…`, SEEK 72) with "platform upload" and `script` chips.
2. In the Tool Hub, **Delete tool** on `tool_dicom_to_nifti` says "Used by workflow(s): workflow_image_conversion".
3. In the Workflow Hub, **Delete workflow** lists `tool_dicom_to_nifti` and `tool_dicom_to_nrrd`. **Delete workflow and its 2 tools** removes all three, and the tools disappear from the Tool Hub.
