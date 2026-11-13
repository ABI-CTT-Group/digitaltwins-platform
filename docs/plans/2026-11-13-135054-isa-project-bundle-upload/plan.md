# ISA projects: upload a design together with its new datasets (UI-only prototype)

## Context

`/catalogue/isa-project` (`IsaProjectHub.vue`) accepts an ISA project JSON only when every
`datasetId` and `workflowId` it references is already on the platform: `validateIsaProject`
(`model/isaProject.ts`) checks them against the fixture catalogue and rejects unknown ids. That
stays as it is.

The gap: a group with a study design but **no data or workflows on the platform yet** has no way in.
This adds a second option, **Upload ISA project with datasets**: one bundle (a folder or a .zip)
holding the JSON plus a folder per new dataset, workflow or tool. It stays a prototype: nothing is
sent to a server; only file names, counts, sizes and the parsed workflow/tool CWL are kept in the
browser.

Decisions from the user (2026-11-13):
- **One bundle**: `isa-project.json` at the root, new items under `datasets/<id>/`.
- **Unknown ids** mark new items: no schema change. Any `datasetId` / `workflowId` not on the
  platform must be matched by a `datasets/<id>/` folder, or it is an error.
- **Scope: everything**: measurement (and model) datasets, workflow datasets and tool datasets.
- **Fidelity**: read workflow and tool CWL only (ports, categories, steps); for other folders only
  count files and bytes.

## Bundle layout

```
my-project.zip                  (or a folder; a single wrapper folder is peeled off)
├── isa-project.json            exactly one .json at the bundle root
└── datasets/
    ├── ds-new-mri-scans/       data: anything without a CWL in primary/
    ├── wf-my-seg/              workflow: SDS package with one primary/workflow_*.cwl
    │   └── primary/workflow_my_seg.cwl, tool_*.cwl
    └── t-extra-tool/           tool: primary/tool_*.cwl and no workflow CWL
```

How a folder is classified, and what it becomes in the catalogue:
- **Workflow**: exactly one `primary/workflow_*.cwl` (reuse `sdsWorkflowCwls`, `utils.ts`). Ports come
  from the CWL `inputs`/`outputs`, category from each port's `doc` (as in
  `examples/workflow/workflow_image_conversion`), default `measurements`. Type comes from the assay
  that uses it. Steps come from `steps[].run`. Each step's tool is the catalogue tool of the same name
  when one exists, otherwise a new tool built from that `tool_*.cwl` in the same `primary/` (an SDS
  workflow package carries its tools, as the real approve flow does).
- **Tool**: `primary/tool_*.cwl` and no workflow CWL (reuse `sdsToolCwls`).
- **Data**: everything else. Category is the category of the workflow port that reads it.

Then the existing `validateIsaProject` runs against **catalogue + bundle items**, so port names,
planned datasets and cycles are checked exactly as today.

Problems the review shows:
- Blocking: no root JSON or more than one; an unknown id with no matching folder; a workflow folder
  with zero or several `workflow_*.cwl`; a step whose tool CWL is missing; CWL that won't parse; any
  existing validator error.
- Warning only: a folder nothing in the design uses.

## UI

Same visual language as the hub (HubShell, aurora buttons, row cards). No new palette or type.
The distinctive piece is the review: it reads as a manifest, each new item matched to the assays that
use it, so the user sees immediately what the bundle adds and what is missing.

Hub toolbar:
```
[ ⬆ Upload ISA project (JSON) ]  [ ⬆ Upload ISA project with datasets ]
  Uses data already on the platform    Folder or .zip: the JSON plus datasets/<id>/ folders
```

`BundleUploadDialog.vue` (v-dialog, two states):
```
Upload ISA project with datasets
┌───────────────────────────────────────────┐
│  LocalFolderDropzone (folder or .zip)     │   + the layout tree above as a hint
└───────────────────────────────────────────┘

── after reading ──────────────────────────────
Test Project 2 · 1 investigation, 1 study, 3 assays

New in this bundle
  Datasets   ✓ ds-new-mri-scans   measurements  412 files, 1.2 GB  used by Assay 1
  Workflows  ✓ wf-my-seg          2 steps                          used by Assay 2
  Tools      ✓ tool_seg_unet      script        (from wf-my-seg)
             ✓ tool_dicom_to_nrrd already on the platform
Already on the platform: 2 datasets, 1 workflow
⚠ datasets/old-scratch/ isn't used by the design
✗ assay a-visualise input dicom_file: unknown dataset ds-raw (no datasets/ds-raw/ folder)

                       [ Choose another bundle ]  [ Add project ]   (disabled while ✗)
```
A project id that already exists goes through the existing "Replace …?" confirm.

Hub row for a bundled project: the existing "Uploaded" chip, plus the summary line gains
"with 1 new dataset, 1 workflow, 1 tool". The prototype note under the title adds that only file names
and sizes are kept, not the files.

Study dashboard: `StudyDesign.vue` merges the entry's bundle items into the catalogue it passes
down, so they show up in the input picker, workflow picker, tools dialog and graph. Items from a
bundle get a small "New" tag where their name is shown (graph source node, input picker item).

Known limitation, no change: **Download JSON** still downloads the JSON only; re-uploading it alone
fails on the new ids. Note it as a follow-up.

## Changes

`services/portal/frontend/src/views/isa-project/`:
- `model/types.ts`: optional `staged?: { fileCount: number; bytes: number }` on `CatalogueDataset`,
  `CatalogueWorkflow`, `CatalogueTool` (marks a bundle item and carries its stats).
- `sandbox.ts`: `IsaProjectEntry.staged?: Catalogue` (the bundle's items only).
- **new** `adapter/isaBundle.ts` (pure, no Vue):
  - `bundleFiles(source: LocalSource)`: list `{ path, size, text() }` from a folder (`webkitRelativePath`)
    or a zip (JSZip, already a dependency), wrapper folder removed with `findRootPrefix`
    (`composables/useFolderScan.ts`).
  - `readBundle(files, catalogue)`: returns `{ project, staged, errors, warnings }` per the rules above,
    reusing `parseCwlText` (`upload-dataset/components/workflow_cwls.ts`), `sdsWorkflowCwls` /
    `sdsToolCwls` (`upload-dataset/components/utils.ts`) and `validateIsaProject`.
  - `withStaged(catalogue, staged)`: the merged catalogue.
- `isaProjectStore.ts`: `addBundle(project, staged)` action (replace by id, like `upload`).
- **new** `components/BundleUploadDialog.vue`: dropzone, then the review above; emits the result.
- `IsaProjectHub.vue`: second button, dialog, replace-confirm reuse, row summary text.
- `StudyDesign.vue`: use `withStaged` for the selected project.
- `components/StudyGraph.vue`, `components/AssayPanel.vue`: "New" tag for `staged` items.

Docs: `docs/glossary.md` entry for "ISA project bundle" if the ISA terms are there; the plan folder below.

## Steps (TDD)

0. Copy this plan to `docs/plans/2026-11-13-<HHMMSS>-isa-project-bundle-upload/plan.md` with a
   `tasks.md` checklist. Sync after every plan edit.
1. `__tests__/isaBundle.spec.ts` (red, then green `isaBundle.ts`): root JSON missing / doubled;
   wrapper folder peeled; folder classification; new dataset category from the reading port; new
   workflow ports and categories from CWL; step tool reused from catalogue vs new from the package;
   standalone tool folder; unknown id with no folder → error; unused folder → warning; bad port on a
   new workflow caught by the validator; `withStaged` merge.
2. Store spec: `addBundle` adds and replaces by id, keeps `staged`.
3. `IsaProjectHub.spec.ts` / new `BundleUploadDialog.spec.ts`: second button opens the dialog; errors
   disable "Add project"; adding lists the row with the "with N new …" summary.
4. `StudyDesign.spec.ts`: a bundle dataset appears as an input option with the "New" tag.
5. Build the dialog and wire-up; visual pass with screenshots (headless Firefox).

## Verification

- `make test-frontend` and `make lint` pass; `make docs-check` after adding the plan files.
- Rebuild and restart only the portal frontend:
  `docker compose build portal-frontend && docker compose up -d portal-frontend`.
- Manual: make a test bundle in the scratchpad (a JSON with one new dataset folder plus a copy of
  `examples/workflow/workflow_image_conversion` renamed under `datasets/`), upload as a folder and as
  a .zip, check the review, add it, open it in the study dashboard, see the "New" items in the picker
  and graph. Also a broken bundle (missing folder, extra folder) to see error and warning.

No ADR now: this is a prototype on a draft schema. The bundle layout and "unknown id = new" choice are
recorded here and should go into the ADR planned for the ISA backend design.
