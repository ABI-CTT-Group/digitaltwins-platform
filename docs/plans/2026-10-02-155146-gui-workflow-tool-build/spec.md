# Launchable GUI tools from gui workflows: design spec

- **Date:** 2026-10-02
- **Status:** Approved by the user, 2026-10-02
- **ADR (accepted):** [2026-10-02-build-gui-workflow-tools](../../decisions/2026-10-02-build-gui-workflow-tools.md)

## Goal

When a gui SDS workflow such as `workflow_volview` is built and approved, its GUI tool can be launched from the Tool Hub in the same way as a standalone GUI tool. Its backend, if it has one, can be deployed and started in the same way too.

## Background

- `tool_volview` (dataset `b90e5bba-…`) was created by approving the portal workflow `workflow_volview` (type gui, SDS). The Tool Hub shows it as "platform upload" with Launch disabled.
- The SDS workflow build deliberately runs no npm. This is decision 3 of [2026-10-02-portal-sds-workflow-approval](../../decisions/2026-10-02-portal-sds-workflow-approval.md): "A gui workflow's tool is stored as source."
- When the API turns each workflow step into a tool dataset (`_assemble_tool`), it copies only the root metadata, `primary/<tool>.cwl` and `code/`. That is why `/tools/b90e5bba-…/primary/my-app.umd.js` returns 404.
- The launcher mounts `window[expose]` from a bundle path that it reads from `/api/tools/metadata`. That endpoint only knows about portal `Plugin` rows.
- Only portal-backend has Node, npm, the Docker socket and the nginx plugin-conf volume. Backends always run on the portal host, even after approval.

## User decisions (2026-10-02)

| # | Question | Decision |
|---|---|---|
| 1 | Where to build | Portal only. The API gets no build capability; it only carries the built bundle into the tool dataset. |
| 2 | How a gui workflow declares its layout | The same fields as GUI tools (has backend, frontend folder, build command, backend folder), entered in the Workflow Registration step. |
| 3 | Where the bundle lives once approved | The tool dataset's `primary/`, through a small change to the API's `_assemble_tool`. |
| 4 | Backend handling | Same as tools: the build bakes in the route prefix, and Deploy backend and Compose up/down are admin actions. |
| 5 | Where launch happens | Tool Hub only, from the first build onwards (the test build before approval, the platform bundle after). The Workflow Hub is unchanged. |
| 6 | Implementation approach | Extract the shared GUI build pieces and reuse `PluginDeployer`. No hidden "shadow" tool rows, and no copied code. |
| 7 | Backend menu items | The same as the tool card: Deploy backend, then Compose up/down. |

## Changes during planning and implementation

These supersede any contradicting text above. Plan: [plan.md](plan.md).

1. **No `gui_frontend.py` module.** The shared build is the `PluginBuilder.build_frontend` method. Its helpers (`_update_vite_config`, `_create_env_file`, `frontend_install`, `frontend_build`) are `PluginBuilder` methods that existing tests use.
2. **gui workflows that aren't SDS packages are unchanged.** The earlier "fails its build" rule contradicted the acceptance criterion that root-`.cwl` workflows behave as before. Only gui **SDS** workflows build a frontend, and the wizard shows the GUI fields only when the source is an SDS package.
3. **No workflow update endpoint is added.** A gui SDS workflow registered before this change has empty GUI fields, so its build uses the defaults (no backend, `npm run build:plugin`, frontend at the `code/` root). `workflow_volview` needs a **Rebuild**, not a new registration.
4. **`workflow_builds.tool_name` marks a build that has a bundle.** `bundle_path` stays null when the upload to `tool-builds` fails; that does not fail the build, the same as a tool test build's MinIO upload.
5. **`GET /api/tools/builds/{id}/logs` also falls back to workflow builds**, so "View logs" works after the in-memory log has expired.
6. **`inspect_workflow_source` lists `code/` subfolders for an SDS workflow** (found in review of Task 12), as `inspect_tool_source` does for SDS tools, so the wizard's folder dropdowns are right for git sources (probe-source and upload-source).

## Design

### 1. Registration and data model

**Frontend.** In `BaseInformationStep.vue`, the GUI field block currently shows only when `type === 'tool' && label === 'GUI'`. It also shows when `type === 'workflow'`, the workflow type is `gui` and the source is an SDS package.
- The fields, defaults and validation are the same as for tools:
  - the build command defaults to `npm run build:plugin` and must match `^(npm|yarn)\s+\S+`
  - when has backend is on, both folders must be chosen from `code/` subfolders
- Changing the workflow type to script or notebook clears these fields.

**Portal DB.** The startup add-column migration in `app/database/database.py` creates these columns.
- `workflows`: `has_backend` (Boolean, default False), `frontend_folder`, `frontend_build_command` and `backend_folder`. All are nullable and only meaningful for gui.
- `workflow_builds`:
  - `tool_name`: the tool CWL name, for example `tool_volview`
  - `bundle_path`: the `tool-builds` MinIO prefix of the bundle; null when the build produced none
  - `tool_dataset_uuid`: the platform tool dataset, set when approval completes
- `plugin_deployments`: a new nullable `workflow_build_id` (FK `workflow_builds.build_id`), and `build_id` becomes nullable. A row references exactly one of the two, and a check constraint enforces that.

**Validation.**
- The workflow create and update endpoints check the GUI fields with the same rules as the tool endpoints.
- gui workflows that aren't SDS packages are unchanged: root-`.cwl` gui workflows build no frontend and keep running separately built portal tools.

### 2. Build

**Shared GUI frontend build.** The GUI-only steps of `PluginBuilder.build` (`app/builder/build_tool.py`, about lines 565-630) move into a new `app/builder/gui_frontend.py`, as a single function. It takes the source dir, `frontend_folder`, `has_backend`, the build command and the expose name, and returns the build output dir. It covers: *(Superseded: implemented as the `PluginBuilder.build_frontend` method — see Changes item 1.)*
- the Vite→UMD rewrite
- the externals check
- the store-namespace plugin
- the `.env` file with `VITE_PLUGIN_ROUTE_PREFIX=/plugin/<expose>` when there is a backend
- `npm install --force`, then the build command
- collecting the `dist/` or `build/` output

`PluginBuilder` calls this function, and its behaviour does not change.

**Workflow build, gui and SDS** (`app/builder/build_workflow.py`):
1. Copy the package as today, leaving out `.git`, `node_modules`, `dist` and `build`.
2. Copy `code/` to a scratch dir and run the shared function there. The local staging dir is never modified.
3. Copy the build output into the workflow dataset at `primary/<tool_stem>/`, for example `primary/tool_volview/my-app.umd.js`, and record `tool_name`.
4. Upload the bundle to `tool-builds/<expose>/primary/` and record `bundle_path`. The whole dataset still goes to the `workflows` bucket as today.
5. npm output streams into the workflow build's log console. If the frontend build fails, the workflow build fails.

**Backend.** Nothing runs at build time. The backend stays at `code/<backend_folder>` in the build's dataset dir, which is where `PluginDeployer` expects it.

### 3. Approval and the platform API

**Portal.** The handoff already uploads every file in the build's dataset dir, so the bundle goes along with it.
- After the commit, `workflow_handoff._complete` calls the existing `GET /datasets/{workflow_uuid}/workflow-tools` and stores the single tool's `dataset_uuid` in `workflow_builds.tool_dataset_uuid`.
- If that call fails, the error is logged and the approval still completes. The tool simply isn't matched to the workflow until the next approval.
- Re-approval and delete keep using `delete_tools=true`.

**digitaltwins-api** (`src/digitaltwins/workflows/pipeline.py`, `_assemble_tool`). If the workflow package has a folder `primary/<tool_stem>/`, its contents are copied into the tool dataset's `primary/`.
- The rule applies to every workflow type and mirrors the existing `code/<tool stem>/` convention.
- `load_workflow` already ignores entries in `primary/` that aren't `*.cwl` files, so no validation change is needed.
- The API README section "Uploading a workflow dataset" documents the new folder.

### 4. Tool Hub, launch, deploy and cleanup

**`/api/tools/metadata`** also lists gui workflows whose chosen build has a bundle. The build is chosen as for tools: the approved build (`dataset_uuid == workflow.uuid`), otherwise the latest completed build. Each entry has:
- `id` = the workflow id
- `kind` = `"workflow"`
- `expose` = the build's `expose_name`
- `path`:
  - approved: `/tools/{tool_dataset_uuid}/primary/my-app.umd.js?v=<ts>`
  - not approved: `/tool-builds/{expose}/primary/my-app.umd.js?v=<ts>`

**Listing.**
- A new `GET /api/workflow/gui-tools` returns a tool-shaped row (the `ToolResponse` fields) for each gui workflow that has a build:
  - `id`: the workflow id
  - `name`: `tool_name`
  - `label`: `GUI`
  - `kind`: `"workflow"`
  - `workflowName`
  - `status`: the chosen build's status
  - `uuid`: `tool_dataset_uuid`
  - `hasBackend`
  - `latestBuildId`, `latestDeployId` and `deployStatus`
- `useToolHub` merges these rows into the list and adds their `uuid` to the `known` set, so the platform's "platform upload" card for the same dataset is not shown twice.

**ToolCard** for `kind === "workflow"`:
- **Tag:** "from workflow `<name>`" replaces "platform upload" and "in platform".
- **Launch:** the existing rules apply. It is enabled when the build is completed, with the same backend-deployed and Compose-up warnings.
- **Menu:**
  - Deploy backend (when there is a backend)
  - Compose up/down (after a deploy has completed)
  - View logs

  Rebuild, Submit and Delete stay on the Workflow Hub card, which owns the workflow.

**Deploy.**
- A new admin-only endpoint, `GET /api/workflow/{id}/deploy`, mirrors the tool deploy endpoint and writes a deployment row with `workflow_build_id`.
- It deploys **the build whose bundle Launch loads** (approved, otherwise latest), so the baked-in `/plugin/<expose>` route always matches.
- The existing Compose execute and check endpoints work on deployment rows. They are adjusted wherever they assume a `Plugin`.
- `ToolsOverallView` sends deploy requests by `kind`.

**Cleanup.**
- A workflow rebuild first shuts down that workflow's deployments, the same as tools.
- Deleting a workflow also shuts down its deployments and removes `tool-builds/<expose>/` for each of its builds.
- The startup reconcile and the shutdown cleanup in `app/main.py` also cover deployments that have `workflow_build_id`.

## Testing (TDD: write the tests first)

**Portal backend (`unittest`).** Run these locally, never inside the live portal-backend container: the suite drops the database when `PORTAL_DB_HOST` is set.
- The existing tool build tests pass before and after the extraction.
- The gui path of the workflow builder, with npm mocked: the bundle lands in `primary/<tool_stem>/`, `tool_name` and `bundle_path` are set, and the staging dir is not modified.
- A gui workflow that isn't an SDS package builds no frontend and is unchanged.
- `/tools/metadata` returns the right workflow entry paths before and after approval.
- `_complete` stores `tool_dataset_uuid`, and a failing workflow-tools call doesn't fail the approval.
- The workflow deploy endpoint writes a row with `workflow_build_id` and deploys the served build.
- The check constraint on deployment rows holds.
- Rebuild and delete shut down workflow deployments and remove the `tool-builds` prefix.

**digitaltwins-api (pytest).**
- `_assemble_tool` copies the contents of `primary/<tool_stem>/` into the tool's `primary/`.
- Without that folder, the behaviour is unchanged.
- The tool still has exactly one `primary/tool_*.cwl`.

**Frontend (vitest).**
- `BaseInformationStep` shows and validates the GUI fields for a gui workflow.
- `ToolCard` shows the workflow tag and the reduced menu.
- `useToolHub` de-duplicates platform rows against `tool_dataset_uuid`.

**Manual end-to-end.**
1. Set VolView's GUI fields on `workflow_volview`: no backend, build command `npm run build:plugin`.
2. Rebuild it, and launch from the Tool Hub (loads from `tool-builds`).
3. Approve it, and launch again (loads from `/tools/{uuid}`).
4. Confirm the "platform upload" card is gone.

## Acceptance criteria

- After a successful build, a gui SDS workflow's tool appears in the Tool Hub tagged "from workflow `<name>`", and Launch mounts it.
- After approval, Launch loads `/tools/{tool_dataset_uuid}/primary/my-app.umd.js`, and that file exists in the platform `tools` bucket.
- For a workflow with a backend, Deploy backend, then Compose up, then Launch reaches the backend through `/plugin/<expose>/`.
- Script and notebook workflows, root-`.cwl` workflows and standalone tools behave exactly as before.

## Out of scope: existing tool-side issues found during research

These are noted for follow-up and are not fixed here.
- A local-source tool build modifies the canonical staging dir in place. That is how `volview_983ba79e` ended up in `tests/data/tool_volview/code/vite.config.ts`.
- A tool rebuild after approval tears down deployments, and deploy targets only the latest build. The approved bundle's baked-in backend route can then no longer be redeployed.
- `backend_deploy_command` is stored but never run.
- The build and deploy error paths assign `error` and `error_message`, which are not columns, so `error_messages` is never filled.
- `plugin_metadata` and `toolMetadata` don't match, so plugin metadata is dropped.
- `/test-build` calls a non-existent `builder.build_plugin`.
- The legacy workflow approval uuid contains a literal `$`.
- Each workflow annotation save inserts a new row instead of updating the existing one.
- Workflow test builds live in the platform `workflows` bucket rather than a separate builds bucket.

## On acceptance

- The ADR status changes to Accepted.
- Decision 3 of `2026-10-02-portal-sds-workflow-approval.md` gets a "Superseded by" note.
- The writing-plans skill then produces the implementation plan in this folder.
