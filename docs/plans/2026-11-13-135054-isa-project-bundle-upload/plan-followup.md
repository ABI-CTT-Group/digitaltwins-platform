# ISA projects bundle upload: follow-up (terms, rules, Approve)

## Context

The bundle upload (one folder or .zip: ISA project JSON plus `datasets/<id>/` folders for what isn't on
the platform yet) is built and verified (`docs/plans/2026-11-13-135054-isa-project-bundle-upload/`).
A grilling round on 2026-11-13 settled the open decisions below, and the user asked for an **Approve
button like the other upload pages**. Everything stays a **UI-only prototype**: no API calls, no change
to real data, and no change to shared upload-dataset code (`ApproveDialog.vue`, `approveAdapters.ts`).

Decisions (user, 2026-11-13):
1. **Term: "bundled"**. A bundled dataset / workflow / tool came in this project's bundle and isn't on
   the platform yet. "Planned dataset" stays for assay outputs only.
2. **Lifecycle**: approving the project registers its bundled items on the platform; afterwards they
   are ordinary platform items any project can use.
3. **Folder id already on the platform**: warn and use the platform copy (unchanged).
4. **Tool CWL in a workflow package with a platform tool's name**: reuse the platform tool (unchanged;
   the risk goes in the walkthrough).
5. **One category per bundled dataset**: inputs reading it with different categories is an error.
6. **SDS required**: every folder the design uses needs `dataset_description.xlsx` at its root (the
   builder's SDS marker); a dataset folder also needs files under `primary/`.
7. **ADR now, status Proposed**.
8. **Approve**: simulated, like the other hubs (confirm, progress, result), in a prototype-only dialog.
   Only uploaded projects get it; examples mirror the platform's Test Project and are left as they are.
   Study dashboard behaviour is unchanged after approval.

## Changes

All in `services/portal/frontend/src/views/isa-project/` unless noted.

### 1. "Bundled" everywhere
- Rename the code term: `StagedFiles` → `BundledFiles`, the `staged?` field on catalogue items →
  `bundled?`, `IsaProjectEntry.staged` → `bundled`, `withStaged` → `withBundled`, `BundleRead.staged`
  → `bundled`. Files: `model/types.ts`, `sandbox.ts`, `adapter/isaBundle.ts`, `model/isaProject.ts`,
  `isaProjectStore.ts`, `IsaProjectHub.vue`, `StudyDesign.vue`, the components and specs.
- UI: graph tag "New" → "Bundled"; side panel note → "Bundled with this project, not on the platform
  yet"; hub row → "with 1 bundled dataset, 1 bundled workflow, 1 bundled tool"; dialog heading
  "New in this bundle" → "Bundled items".

### 2. Bundle rules (`adapter/isaBundle.ts`)
- Category conflict: `datasets/<id>/ is read as measurements by assay a1 input x and as models by assay
  a2 input y; a dataset has one category.`
- SDS: for each folder the design uses, `datasets/<id>/ isn't an SDS package: it needs
  dataset_description.xlsx at its root.` and, for datasets, `datasets/<id>/ has no files under
  primary/.` Unused folders and folders already on the platform are left out, so they aren't checked.
  Reuse `SDS_MARKER` from `upload-dataset/components/utils.ts`.

### 3. Approve (prototype)
- **Store** (`isaProjectStore.ts`), persisted like the rest:
  - `registered: Catalogue`: items approved in this browser, used by every project.
  - Entry gains `approval?: { state: "approving" | "approved"; stage?: string }` (`sandbox.ts`).
  - `approve(projectId)`: sets `approving`, walks the stages with short delays ("Creating the SEEK
    project", then "Registering <name>" per bundled item), then moves the entry's bundled items into
    `registered` (deduped by id), clears `entry.bundled`, and sets `approved`. It runs in the store, so
    closing the dialog doesn't stop it, as on the other hubs.
  - `catalogue` getter: fixture catalogue + `registered`. A later JSON upload
    (`fixtureSource.parseUpload` takes an optional extra catalogue), a bundle read
    (`BundleUploadDialog`) and the study dashboard (`StudyDesign`) all use it.
- **Dialog**: new `components/IsaApproveDialog.vue`, copying `ApproveDialog.vue`'s look and phases:
  - Confirm: "Approve <title>?" and "Its SEEK project is created from the ISA tree, and its bundled
    datasets, workflows and tools are registered so any project can use them. Prototype: nothing
    reaches the platform; only this browser's list changes."
  - Progress: the current stage and a bar ("You can close this: the row keeps following it.").
  - Result: "<title> is in the platform."
- **Hub row** (`IsaProjectHub.vue`), uploads only:
  - Before approval: a status line "Not in the platform yet. Approve it to create its SEEK project and
    register its 3 bundled items." (or "…to create its SEEK project." with none), and an **Approve**
    button first in the actions.
  - While approving: "Approving… <stage>" and no button. After: "In the platform" and no button.
  - Remove on an approved project says its registered items stay. Replacing it with a new upload makes
    a new, unapproved draft.

### 4. Docs
- **ADR** `docs/decisions/2026-11-13-isa-project-bundle.md` (from `docs/decisions/TEMPLATE.md`, status
  Proposed): the bundle layout, "an id the platform doesn't have means a bundled item", the SDS rule,
  reusing platform tools by name, and the lifecycle (registered on approval). Alternatives considered:
  guided per-item attach, explicit `newDatasets` list in the JSON, per-project ownership.
- **Glossary** (`docs/glossary.md`): add "Bundled item (prototype)"; update "ISA project bundle" with
  the SDS rule; add one sentence to "ISA project (prototype)" on Approve.
- Plan folder `docs/plans/2026-11-13-135054-isa-project-bundle-upload/`: sync this plan as
  `plan-followup.md`, extend `tasks.md`, update `walkthrough.md`.

## Steps (TDD: specs first for each)

0. Sync this plan into the plan folder and add the tasks.
1. Rename to "bundled" (mechanical; the existing specs keep passing after the same rename).
2. `isaBundle.spec.ts`: category conflict; folder without the marker; dataset without `primary/`
   files; existing fixtures gain `dataset_description.xlsx`.
3. `isaProjectStore.spec.ts`: `approve` walks the stages (fake timers), moves bundled items to
   `registered`, survives a reload; `catalogue` includes `registered`; a JSON upload can then use a
   registered id.
4. New `IsaApproveDialog.spec.ts`: confirm text, then progress, then result.
   `IsaProjectHub.spec.ts`: Approve shown for uploads only; status line before, during and after.
5. `StudyDesign.spec.ts`: a registered item shows as a platform item (no Bundled tag).
6. Glossary, ADR, walkthrough.

## Verification

- `make test-frontend`, `make lint`, `make docs-check` pass.
- Rebuild and restart only the portal frontend:
  `docker compose build portal-frontend && docker compose up -d --no-deps portal-frontend`.
- Headless Firefox: upload the good bundle (now with `dataset_description.xlsx` in each folder),
  approve it, watch the row go from "Not in the platform yet" through "Approving…" to "In the
  platform", then upload a JSON that uses the registered dataset id and check it is accepted. Also a
  non-SDS bundle and a category-conflict bundle, to check their errors.
