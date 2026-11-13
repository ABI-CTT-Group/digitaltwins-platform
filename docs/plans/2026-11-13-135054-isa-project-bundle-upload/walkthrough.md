# Walkthrough: upload an ISA project with its new datasets

Frontend only, UI prototype. Every code change is in `services/portal/frontend/src/views/isa-project/`,
plus specs, the glossary row and this folder. Nothing is sent to a server.

## What changed

- **Hub:** a second upload, **Upload ISA project with datasets**, sits beside the JSON upload. Each
  button has a one-line note saying when to use it. The JSON upload is unchanged.
- **Bundle:** one folder or .zip with the ISA project JSON at its root and a `datasets/<id>/` folder for
  each dataset, workflow or tool the design uses that isn't on the platform yet. A single wrapper
  folder (as a zipped folder has) is peeled off. There is no schema change: any id the platform
  doesn't have must have a folder of that name (`adapter/isaBundle.ts`).
  - A folder with one `primary/workflow_*.cwl` is a workflow. Its ports, port categories (CWL `doc`)
    and steps are read from the CWL, and its type comes from the assay that uses it. Each step's
    tool is the platform tool of that name, or else the `tool_*.cwl` in the same `primary/`, or else a
    tool package in the bundle.
  - A folder with only `primary/tool_*.cwl` is a tool. Anything else is a dataset, whose category is
    the category of the workflow input that reads it.
  - The design is then checked by the existing `validateIsaProject` against the platform catalogue
    plus these items. An unknown id gets a hint: no folder, or a folder of the wrong kind.
  - A folder nothing uses, or one whose id is already on the platform, is a warning and is left out.
- **Dialog** (`components/BundleUploadDialog.vue`): before a pick, it shows the layout and reuses the
  platform's `LocalFolderDropzone`. After a pick, it shows the project and each new item, with a bar in
  the platform's colour for its kind, its size and the assays that use it, plus how much is already on
  the platform. Errors disable **Add project**. A project id that already exists goes through the
  existing "Replace …?" confirm.
- **Kept:** the entry stores the bundle's items (`IsaProjectEntry.bundled`), with file counts, sizes and
  parsed workflow CWL only. The hub row says "with 1 bundled dataset, 1 bundled workflow, 1 bundled tool".
- **Study dashboard:** `StudyDesign.vue` adds the entry's items to the catalogue (`withBundled`), so the
  pickers, tools list and graph can use them. A bundled dataset has a "Bundled" tag on its graph node,
  and the side panel calls it "Bundled with this project, not on the platform yet".
- **Glossary:** new row "ISA project bundle (prototype)".

## Not done, follow-ups

- **Download JSON** still downloads the JSON only. Uploading that JSON alone fails on the new ids.
- The validator doesn't check input port names against a workflow's ports. That's true of platform
  workflows today too, so the bundle path doesn't check them either.
- A large .zip is read whole in the browser (JSZip). That's fine for a prototype, but a real upload
  would stream it to the server.
- The bundle layout and the "unknown id means bundled" rule are now in the ADR (Proposed); the ISA backend design confirms or replaces it.

## Checked

- Specs first for each part: `isaBundle.spec.ts` (new), `BundleUploadDialog.spec.ts` (new), plus
  additions to the store, hub, model, `AssayPanel`, `StudyGraph` and `StudyDesign` specs.
- `make test-frontend`: 67 files, 444 tests pass. `make lint-frontend` and `make docs-check` pass.
- Rebuilt and restarted `portal-frontend`. In headless Firefox, a good and a broken test bundle (.zip)
  were uploaded on the ISA projects page. The review, errors and warnings, the added row, the "Bundled"
  tag in the study's Flow view and the phone-width hub all looked right.

## Follow-up: terms, bundle rules, Approve (`plan-followup.md`)

Decisions from a review round on 2026-11-13, recorded in
[the ADR](../../decisions/2026-11-13-isa-project-bundle.md) (Proposed).

- **One term, "bundled":** a bundled dataset, workflow or tool came in the project's bundle and isn't on
  the platform yet. The code, the graph tag, the side panel and the hub row all use it; "planned
  dataset" stays for assay outputs. Glossary rows: "Bundled item", plus updates to "ISA project" and
  "ISA project bundle".
- **SDS required:** every folder the design uses needs `dataset_description.xlsx` at its root, and a
  dataset folder needs files under `primary/`.
- **One category:** inputs that read one bundled dataset as different categories are an error.
- **Unchanged after review:** a folder whose id is already on the platform is left out with a warning,
  and a tool CWL that has a platform tool's name reuses the platform tool. The package's copy could
  differ, which is noted in the ADR.
- **Approve (simulated):** uploaded projects get an **Approve** button and a status line, as on the
  other upload pages: "Not in the platform yet…", then "Approving… <stage>", then "In the platform".
  `IsaApproveDialog.vue` copies the look of the shared `ApproveDialog.vue`, which isn't changed. It
  confirms, then follows the stages ("Creating the SEEK project", "Registering <item>"), then shows the
  result. The approval runs in the store, so closing the dialog doesn't stop it, and an approval cut off
  by a page reload is dropped. Approving moves the project's bundled items into a browser-wide
  registered list. After that they are platform items for every project: the study dashboard, later
  JSON uploads and bundle reads all see them. Examples have no Approve button. Nothing reaches the
  platform.

### Checked (follow-up)

- Specs first, except `IsaApproveDialog.spec.ts`, which was written together with its component.
- `make test-frontend`: 68 files, 459 tests pass. `make lint` and `make docs-check` pass.
- Rebuilt and restarted `portal-frontend`. In headless Firefox: a non-SDS bundle is blocked with its
  error; a good bundle is added, approved (the dialog was closed mid-way and the row kept following
  it) and ends "In the platform"; a JSON uploaded afterwards that uses its registered dataset and
  workflow ids is accepted.


## Follow-up 2: download a bundle, demo bundle (`plan-followup-2.md`)

- **Download bundle** on every row (`adapter/isaBundleWriter.ts`, `bundleZip`). The prototype keeps no
  dataset files, so the zip is an SDS skeleton: `isa-project.json`, plus `datasets/<id>/` for each
  dataset and workflow the design uses. Each folder has a generated `dataset_description.xlsx` (Title,
  Type, a placeholder note). A dataset folder also gets `primary/README.txt`. A workflow folder gets its
  catalogue CWL as YAML, with each port's category as `doc`, plus a placeholder `tool_*.cwl` for each
  bundled tool. Platform tools are found by name.
- **Round trip:** reading a downloaded bundle back gives the same project. For the example, every folder
  is "already on the platform" and left out with a warning. For an unapproved bundled upload, its
  bundled items come back with the same ports and steps.
- **Download an example bundle** in the upload dialog (`demoBundle`): a copy of the Test Project
  (`p-test-project-demo`). Assay 1 reads the bundled dataset `ds-demo-mri`. Assay 2 runs the bundled
  workflow `wf-demo-image-conversion`, whose second step runs the bundled tool `tool_demo_dicom_to_png`.
  Only the bundled items get folders, so it passes with no errors or warnings, and it can be approved.
- **Fixed:** the dialog's layout hint said a dataset folder could hold "any files", which has been wrong
  since the SDS rule was added. It now lists `dataset_description.xlsx` for every folder.

### Checked (follow-up 2)

- Specs first: `isaBundleWriter.spec.ts` (new, 7 tests), the hub's download button and the dialog's
  example link.
- `make test-frontend`: 69 files, 468 tests pass. `make lint` and `make docs-check` pass.
- Rebuilt and restarted `portal-frontend`. In headless Firefox:
  - downloaded the example row's bundle (JSON, 3 dataset and 4 workflow skeletons);
  - downloaded the demo from the dialog, uploaded it (1 bundled dataset, workflow and tool) and approved
    it;
  - re-uploaded the example's bundle, which showed 7 "already on the platform" warnings.
