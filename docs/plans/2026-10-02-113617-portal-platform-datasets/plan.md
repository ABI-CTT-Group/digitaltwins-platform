# Plan: show and delete platform-uploaded workflows and tools in the portal

## Context

Datasets can be uploaded straight to the platform through the REST API (`POST /datasets`, upload sessions, CLI) as well as through the portal. After the workflow-upload work ([2026-10-02-105120-workflow-dataset-upload](../2026-10-02-105120-workflow-dataset-upload/plan.md)), workflow 72 appeared in SEEK but not in the portal's Workflow Hub (`/upload-workflow-dataset`).

**How each hub handles API-uploaded datasets today:**

| Hub | Lists API-uploaded datasets? | Delete? |
|---|---|---|
| Workflows (`WorkflowsOverallView.vue`) | **No.** It lists only `portal.workflows` (`GET /api/workflow/`, `workflow_router.py:205`). | Only for portal workflows. |
| Tools (`ToolsOverallView.vue`) | **Yes.** `usePlatformTools()` (`tool_api.ts:107`) shows them as "platform upload" cards. | **No.** Platform-only cards have no menu (`ToolCard.vue:124`). |
| Measurements (`MeasurementsOverallView.vue`) | **Yes.** `useMeasurement()` lists `/datasets?categories=measurements` as well as the sessions. | Yes, through `DELETE /datasets/{uuid}`. |

**Goal:**
- The Workflow Hub lists platform workflows (datasets with `workflow_type` set), and they can be deleted. The user chooses whether to delete the workflow's tools too.
- Platform-only tools in the Tool Hub can be deleted, after a confirmation.
- Measurements already work, so they don't change.

**User decisions (2026-10-02):**
- Platform workflows get a delete with the "also delete its tools?" question.
- Platform tools get a delete with a confirmation.
- The frontend gets vitest, and new code is written test-first.
- The dialog reads a workflow's tools from a new read endpoint, not from a DELETE (option B).

**Out of scope:**
- Confirmations for the existing portal deletes and for measurements.
- Portal-built workflow approval, which still only assigns a `sparc-workflow-` placeholder.
- Any API changes other than the one read endpoint in §0.

## Design

### 0. API: new `GET /datasets/{uuid}/workflow-tools` (`services/api`)

- **Endpoint:** in `app/routers/datasets.py`, next to `GET /datasets/{uuid}`.
- **Auth:** `validate_credentials`, the same as the other dataset reads.
- **Response:**
  - `200 {"workflow_type": "<type or null>", "tools": [{dataset_uuid, dataset_name, seek_id, step_ids}]}`
  - For a dataset that isn't a workflow, `workflow_type` is `null` and `tools` is `[]`.
  - `404` if the dataset doesn't exist.
- **Implementation:** it reuses `workflows.pipeline.linked_tools()`, the same query the 409 already uses, so the dialog and the delete guard always agree.
- **Tests:** `tests/test_datasets_workflows_api.py` gets cases for a script workflow (2 tools with their steps), a tool / non-workflow dataset (`null`, `[]`) and an unknown uuid (`404`).
- **Docs:** a short line in `services/api/README.md` under "Deleting".

### 1. Data layer: new `frontend/src/bootstrap/platform_api.ts`

**`usePlatformWorkflows(known: Set<string>): Promise<WorkflowResponse[]>`**
- Calls `dtApi.get("/datasets", { categories: "workflows" })`.
- Keeps rows whose `workflowType` is `script`, `notebook` or `gui`. This leaves out assay workspace outputs, which share the category.
- Drops rows whose uuid is in `known`, i.e. already a portal workflow.
- Maps each row to a `WorkflowResponse` with:
  - `id = uuid = datasetUuid`, `name = datasetName || datasetUuid`
  - `version: ""`, `repositoryUrl: ""`, `status: "completed"`
  - `description: "Uploaded to the platform directly."`
  - `platformOnly: true`, `workflowType`
  - `createdAt` and `updatedAt` from `createdAt`
- This mirrors `usePlatformTools`.

**`useWorkflowTools(uuid): Promise<PlatformLink[]>`**
- Calls `dtApi.get(`/datasets/${uuid}/workflow-tools`)` and returns its `tools`. Successful responses are camelCased by the interceptor.

**`deletePlatformDataset(uuid, deleteTools?)`**
- Calls `dtApi.delete(`/datasets/${uuid}`, deleteTools === undefined ? undefined : { deleteTools })`.
- The interceptor sends `deleteTools` as `?delete_tools=`.

**`datasetInUse(err)`**
- Turns an axios 409 from that endpoint into `{ message, tools?: PlatformLink[], workflows?: PlatformLink[] }`, otherwise `null`.
- Error bodies are not camelCased by the interceptor, so it maps the API's `dataset_uuid`, `dataset_name`, `seek_id` and `step_ids` itself.

**`useWorkflowHub()`, in `workflow_api.ts`**
- Returns the portal workflows plus `usePlatformWorkflows(known)`.
- If the platform is down, it catches the error and hides only the platform rows, as `useToolHub` does.

**`types.ts`:** `WorkflowResponse` gains `platformOnly?: boolean` and `workflowType?: string`.

### 2. Confirmation dialog: new `components/DeletePlatformDatasetDialog.vue`

- It is modelled on `ToolApprovalDialog.vue`: `v-model` open, props `{ kind: "workflow" | "tool", item: { uuid, name } | null }`, and it emits `deleted`.
- The accent colour is `#7fb2f0` for workflows and `#5fd6e8` for tools.

**For a workflow:**
1. When the dialog opens, it calls `useWorkflowTools(uuid)` (§0) and lists the tools by name and steps.
2. It offers three buttons: **Cancel**, **Delete workflow only** (`delete_tools=false`), and **Delete workflow and its N tools** (`delete_tools=true`). With no tools, only Cancel and **Delete workflow** are offered.
3. If the delete still returns 409 (for example, the list changed in the meantime), the dialog shows the message and keeps the workflow.

**For a tool:**
- The dialog asks "Delete tool *X* from the platform?" and offers Cancel and Delete.
- On a 409, it shows "Used by workflow(s) *A*; delete the workflow first" and keeps the tool.

**Errors:** any other error is shown in a `v-alert` inside the dialog. Nothing is retried automatically.

### 3. Cards and hubs

**`WorkflowCard.vue`**
- A platform-only workflow shows the chips "platform upload" and its `workflowType`.
- Its menu has only **Delete workflow**, which emits `delete-platform` with the workflow.
- Portal workflows keep their current menu and `delete` behaviour.

**`WorkflowsOverallView.vue`**
- `:fetch-list="useWorkflowHub"`.
- `isWorkflowInPlatform` also counts `platformOnly`.
- `delete-platform` opens the dialog, and `deleted` refreshes the list.

**`ToolCard.vue`**
- A platform-only tool's menu becomes **Delete tool**, which emits `delete-platform` (it used to have no menu).
- Portal tools are unchanged.

**`ToolsOverallView.vue`:** `delete-platform` opens the dialog with `kind="tool"`, and `deleted` refreshes the list.

### 4. Test setup

- **devDependencies:** `vitest`, `@vue/test-utils` and `jsdom`, at versions compatible with vite 6 and Vue 3.5.
- **`package.json` script:** `"test": "vitest run"`.
- **Config:** a `test` block in `vite.config.ts` (`environment: "jsdom"`, `server.deps.inline: ["vuetify"]`), plus a small setup file that registers Vuetify (`createVuetify`) for component tests.
- **Lockfile:** `yarn.lock` is updated with **Yarn 1.22.22 in `node:20-alpine`**, the version the Dockerfile pins with `--frozen-lockfile`. `package-lock.json` is not used by the build and is left alone; that is noted in the walkthrough.

## Implementation order (TDD: write each test red, then make it pass)

0. **API endpoint** (§0). Write the pytest cases first, then the endpoint. Run the full API suite; only the known legacy failures should remain.
1. **Test setup.** Add vitest with one trivial passing test. Verify: `yarn test` in a `node:20-alpine` container.
2. **`platform_api.ts`**, with `src/bootstrap/__tests__/platform_api.spec.ts` (`dtApi` mocked). Cover:
   - workflowType filtering, including dropping assay outputs;
   - dropping `known` uuids;
   - the field mapping;
   - `useWorkflowTools` reading the new endpoint;
   - the `delete_tools` param;
   - parsing a 409 for both the tools and the workflows shape.
3. **`useWorkflowHub`.** Test that portal and platform rows are merged, and that a platform failure leaves the portal rows.
4. **`DeletePlatformDatasetDialog.vue`**, with a spec (data layer mocked). Cover:
   - a workflow: the tools from `useWorkflowTools` are listed, and each button sends `false` / `true`, then emits `deleted`;
   - a tool: the delete emits `deleted`, and a 409 shows the workflow names without emitting.
5. **Cards.** Specs for `WorkflowCard` and `ToolCard`:
   - a platform-only card's menu is exactly Delete and emits `delete-platform`;
   - a portal card's menu is unchanged.
6. **Hubs.** Wire `WorkflowsOverallView` and `ToolsOverallView` to the dialog.
7. **Verify.**
   - `yarn test`, `vue-tsc --noEmit` on the touched files (or the whole project if it is already clean), and `yarn build`.
   - Then the user rebuilds `portal-frontend` and checks `/upload-workflow-dataset`. Workflow 72 should be listed; deleting it should list its 2 tools.
   - Also check that a tool used by that workflow can't be deleted from the Tool Hub (the dialog shows the 409 message).
8. **Docs and artifacts.** Write the walkthrough and sync the artifacts. There is no ADR: this mirrors the existing Tool Hub pattern, and the new read endpoint is a plain addition.

## Critical files

**New:**
- `frontend/src/bootstrap/platform_api.ts`
- `frontend/src/views/upload-dataset/components/DeletePlatformDatasetDialog.vue`
- specs under `__tests__/`
- the vitest setup file

**Modified (API):**
- `services/api/app/routers/datasets.py`
- `services/api/tests/test_datasets_workflows_api.py`
- `services/api/README.md`

**Modified (portal):**
- `frontend/src/bootstrap/workflow_api.ts`
- `frontend/src/models/types.ts`
- `frontend/src/views/upload-dataset/components/{WorkflowCard,ToolCard}.vue`
- `frontend/src/views/upload-dataset/{workflow/WorkflowsOverallView,workflow-tool/ToolsOverallView}.vue`
- `frontend/package.json`, `frontend/yarn.lock`, `frontend/vite.config.ts`

## Verification

- **Automated:**
  - `docker run --rm -v $PWD:/app -w /app node:20-alpine sh -c "corepack enable && corepack prepare yarn@1.22.22 --activate && yarn install --frozen-lockfile && yarn test && yarn build"`, run from `services/portal/frontend`.
- **API:** the full `services/api` suite in the throwaway test container.
- **Live**, after the user rebuilds `digitaltwins-api` and `portal-frontend`:
  1. `/upload-workflow-dataset` lists workflow `a8d6da0e-…` (SEEK 72) as "platform upload".
  2. In the Tool Hub, Delete on `tool_dicom_to_nifti` shows "Used by workflow(s) workflow_image_conversion".
  3. In the Workflow Hub, Delete on the workflow lists both tools. "Delete workflow and its 2 tools" removes all of them, and the tools disappear from the Tool Hub.
