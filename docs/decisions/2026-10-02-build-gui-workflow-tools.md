# Build a gui workflow's tool in the portal so it can be launched

- **Date:** 2026-10-02
- **Status:** Accepted
- **Supersedes:** decision 3 of [2026-10-02-portal-sds-workflow-approval](2026-10-02-portal-sds-workflow-approval.md) ("nothing is npm-built … a gui workflow's tool is stored as source")

## Context

When an SDS workflow of type gui (for example `workflow_volview`) is approved, digitaltwins-api creates a tool dataset for its single step. The portal's workflow build copies the package without running npm. The API's `_assemble_tool` copies only the tool CWL and `code/`. So the tool dataset has no `primary/my-app.umd.js`, and the Tool Hub lists it as a non-launchable "platform upload".

Launching a GUI tool needs three things:
- a UMD bundle
- its `expose` global name
- for a backend, a `/plugin/<expose>` route that is baked in at build time and served by a compose project on the portal host

Only portal-backend has Node, npm, the Docker socket and the nginx plugin-conf volume ([2026-10-01-unified-tool-dataset-ingest](2026-10-01-unified-tool-dataset-ingest.md)).

## Alternatives Considered

### Where to build

#### Option A: the portal's workflow build (chosen)
- Pros:
  - It reuses the existing GUI build: the Vite→UMD rewrite, the externals check and the route-prefix `.env`.
  - The backend runtime is already on the portal host.
  - Builds can be tested before approval.
- Cons: the workflow build becomes slower and can fail on npm errors.

#### Option B: digitaltwins-api builds at ingest
- Pros: REST and CLI uploads of gui workflows and tools would also become launchable.
- Cons:
  - Node and the build code would have to be added to the API, and kept in step with the portal's copy.
  - The API still couldn't run backends.
  - The launcher and the routing live in the portal anyway.

### Where the approved bundle lives

#### Option A: the tool dataset's `primary/`, carried by the API (chosen)
- The portal writes the bundle to the workflow package's `primary/<tool_stem>/`, and `_assemble_tool` copies that folder's contents into the tool's `primary/`.
- Pros: the tool dataset has the same layout as an approved standalone GUI tool, so the launch path is the same.
- Cons: a small API change, and the bundle is stored twice (in the workflow dataset and in the tool dataset).

#### Option B: under `code/`, with no API change
- Cons: build output is mixed into the source folder, and the launch path differs from standalone tools.

#### Option C: the workflow dataset only
- Cons: it needs a new public route for the `workflows` bucket, and the tool dataset stays source-only.

### How to reuse the GUI build and deploy code

#### Option A: extract a shared GUI frontend build, and reuse `PluginDeployer` (chosen)
- Pros: one build implementation, and no duplicate entities.
- Cons:
  - A refactor of `build_tool.py`.
  - New columns on `workflows` and `workflow_builds`.
  - Deployment rows that can reference either a tool build or a workflow build.

#### Option B: a hidden "shadow" `Plugin` per gui workflow
- Cons:
  - Two entities with one lifecycle, which must be kept in sync on rebuild, delete and approval.
  - The shadow plugin must never be approved on its own.

#### Option C: copy the build steps into `WorkflowBuilder`
- Cons: about 300 lines of fragile regex and build code duplicated, which will drift apart.

## Decision

The portal builds a gui SDS workflow's frontend during the workflow build. It uses a frontend build function shared with tool builds, and the same registration fields as GUI tools.
- **Where the bundle goes:**
  - into the workflow package at `primary/<tool_stem>/`
  - to `tool-builds/<expose>/primary/` for launching before approval
  - into the tool dataset's `primary/` on approval, copied by the API's `_assemble_tool`
- **Backends work as for tools:** the build bakes in the route prefix, and Deploy backend and Compose up/down are admin actions. The deploy targets the build whose bundle Launch loads.
- **Launch and the backend actions live only on the Tool Hub card** for the workflow's tool, tagged "from workflow `<name>`".

Details are in the spec: [docs/artifacts/2026-10-02-155146-gui-workflow-tool-build/spec.md](../artifacts/2026-10-02-155146-gui-workflow-tool-build/spec.md).

## Consequences

- gui workflows can be launched from their first build onwards, the same as standalone GUI tools.
- A gui workflow's build now needs npm to succeed, and takes as long as a tool build.
- `plugin_deployments` rows can now belong to a workflow build as well as a tool build, so every query over deployments must handle both.
- digitaltwins-api gains one convention, `primary/<tool_stem>/`, which applies to all upload paths. REST and CLI GUI uploads remain stored but not launchable, because the portal still has no expose name for them.
- Workflow test builds still live in the platform's `workflows` bucket. Only the bundle is also copied to `tool-builds`.
- Only gui **SDS** workflows build a frontend; root-`.cwl` gui workflows keep running separately built portal tools. A gui SDS workflow registered before this change builds with the defaults (no backend, `npm run build:plugin`) on its next rebuild.
