# ISA projects: download a project as a bundle, plus a demo bundle (UI-only prototype)

## Context

The ISA projects page (`/catalogue/isa-project`) can upload an **ISA project bundle**: one folder or
.zip with `isa-project.json` and an SDS `datasets/<id>/` folder for each bundled item. Rows can only
**Download JSON**. The user asked (2026-11-13) for (1) an example bundle to upload and (2) a way to
download a project, starting with the Test Project example, "as JSON with datasets".

The prototype holds no dataset files, only each item's id, name and category, plus workflow CWL.
Fetching the real files would break the UI-only rule for this prototype, so the
download is an **SDS skeleton**.

Decisions (user, 2026-11-13):
- **Contents: SDS skeleton.** `isa-project.json`, plus a `datasets/<id>/` folder for every dataset and
  workflow the design uses. Each folder has a generated `dataset_description.xlsx` and placeholder or
  CWL files. It's a template to fill in. Uploaded again as-is, a folder whose id is on the platform is
  left out with a warning, as now.
- **Placement: every row** gets "Download bundle". For an uploaded project, its bundled folders are
  skeletons too, since files aren't kept.
- **Demo:** the "Upload ISA project with datasets" dialog gets **Download an example bundle**. It builds
  a ready-to-upload bundle in the browser that passes every check and can be approved.

## What a skeleton bundle holds

```
<project id>/
├── isa-project.json                 the project, as Download JSON gives it
└── datasets/
    ├── <dataset id>/
    │   ├── dataset_description.xlsx  generated: Title = dataset name, Type = category, a placeholder note
    │   └── primary/README.txt        which files go here (one sub-<n> folder per subject for measurements)
    └── <workflow id>/
        ├── dataset_description.xlsx
        └── primary/
            ├── <workflow name>.cwl   the catalogue CWL as YAML, with cwlVersion, class: Workflow and
            │                         each port's category as `doc`, so reading it back gives the same ports
            └── tool_<name>.cwl       only for bundled tools (a placeholder CommandLineTool);
                                      platform tools are reused by name, as when reading
```

Reading a skeleton back with `readBundle` gives the same project, and the same bundled items for an
uploaded project. A round-trip spec checks this.

## Demo bundle

`Test Project (bundled demo)`, id `p-test-project-demo`: a copy of the Test Project example where
- Assay 1 reads the bundled dataset `ds-demo-mri` (measurements) instead of `ds-test-dicom`.
- Assay 2 runs the bundled workflow `wf-demo-image-conversion`, a copy of `workflow_image_conversion`
  whose second step runs the bundled tool `tool_demo_dicom_to_png`. Its first step keeps the platform
  tool.

It's built as a project plus bundled catalogue items and written with the same skeleton writer. The
review shows one bundled dataset, one workflow and one tool, and the project can be approved.

## Changes

`services/portal/frontend/src/views/isa-project/`:
- New `adapter/isaBundleWriter.ts`:
  - `bundleZip(project, catalogue): Promise<Blob>` writes the skeleton above. Items come from
    `catalogue`, which already includes the entry's bundled items and the registered ones. It uses
    JSZip and SheetJS (`xlsx`), both dynamic imports as elsewhere (`sampleTypes.ts`,
    `LocalFolderDropzone.vue`), and `js-yaml` for CWL.
  - `demoBundle(platform: Catalogue): { project, bundled }` returns the demo project and its items.
- `IsaProjectHub.vue`: **Download bundle** (ghost) after **Download JSON** on every row. It builds the
  catalogue as the study dashboard does (`store.platformCatalogue()` plus the entry's `bundled`) and
  saves `<project id>.isa-bundle.zip`. Reuses the existing `download` link pattern.
- `components/BundleUploadDialog.vue`: in the idle state, under the layout hint, a link **Download an
  example bundle** saves `p-test-project-demo.isa-bundle.zip`.
- Docs: glossary "ISA project bundle" gets one sentence on downloading a skeleton. Plan synced to
  `docs/plans/2026-11-13-135054-isa-project-bundle-upload/plan-followup-2.md`, with tasks and
  walkthrough updated.

## Steps (TDD, specs first)

0. Sync this plan to the plan folder and add the tasks.
1. `__tests__/isaBundleWriter.spec.ts`:
   - The example's zip lists the JSON and a folder for each of its datasets and workflows.
   - `dataset_description.xlsx` reads back (SheetJS) with Title and Type.
   - The workflow CWL keeps the ports and categories.
   - Round trip: `readBundle(bundleZip(example))` gives the same project, with each folder "already on
     the platform".
   - Round trip for an uploaded bundled project gives back the same bundled items.
   - The demo reads back with no errors and 1 dataset, 1 workflow and 1 tool bundled.
2. `IsaProjectHub.spec.ts`: every row has **Download bundle**. Clicking it creates a zip download
   (spy on `URL.createObjectURL`).
3. `BundleUploadDialog.spec.ts`: the idle state offers **Download an example bundle**.
4. Implement, then `make test-frontend`, `make lint`, `make docs-check`.

## Verification

- Rebuild and restart only the portal frontend:
  `docker compose build portal-frontend && docker compose up -d --no-deps portal-frontend`.
- Headless Firefox:
  - Download the example row's bundle and check its file list.
  - Download the demo from the dialog, upload it, check the review (1 dataset, 1 workflow, 1 tool), then
    approve it.
  - Re-upload the example's bundle and check the "already on the platform" warnings.
