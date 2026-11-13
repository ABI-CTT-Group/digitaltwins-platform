# Walkthrough: study design sandbox on the Test Project

Frontend only. Every code change is in `services/portal/frontend/src/views/isa-project/`, plus specs,
the glossary row and this folder. The real Test Project's assays, workflows and CWL ports were read
from the platform (SEEK, Postgres, MinIO) to build the fixtures; nothing was written to them.

## What changed

- **Example:** "Breast pilot (example)" is replaced by **"Test Project (example)"**
  (`fixtures/example-test-project.json`). Its study has four assays wired as on the platform:
  `Test Assay 1: cohort selection` → `Test Assay 2: image conversion` → `Test Assay 3: image visualisation`,
  and `Test Assay 2` → `Test Assay 4: breast app` (`nrrd_output` → `contrast_pre_nrrd`). Browsers that
  stored the retired example drop it on their next visit.
- **Catalogue:** the real workflows (`workflow_mri_curation`, `workflow_image_conversion`,
  `workflow_volview`, `workflow_Lesion-Ground-Truth-Curator`), their five tools and CWL, and the five
  `test_*` datasets.
- **Shared dataset names:** as on the platform, several output ports of one assay can promise one
  dataset. Pickers and edges name a planned dataset as `dataset / port`; new workflows default to one
  dataset per assay (`<assay title> outputs`).
- **Flow view:** a platform dataset sits in the column before its first reader, below any card there.
  Edge labels stack the dataset over the port (`DatasetEdge.vue`). A platform dataset that feeds
  several inputs is labelled with the count ("14 inputs").
- **Side panel:** inputs are grouped by the dataset they read. A dashed rail marks a planned group, and
  a group of four or more starts collapsed. Outputs are grouped by dataset, with one name field that
  renames every output in the group.
- **Hub:** each row previews its studies' assays as a chain (`StudyChain.vue`), drawn with the same
  dashed lines and fork as the Flow view.
- **Glossary:** "Planned dataset (prototype)" now says that several ports can fill one dataset.

## Checked

- `make test` (frontend: 393 tests), `make lint` and `make docs-check` pass.
- `portal-frontend` was rebuilt and restarted on its own. A headless Firefox walk-through, signed in as an admin, showed:
  - the hub row and its chain, including at phone width;
  - the Flow view with the fork and the breast app's datasets beside it;
  - the breast app panel with three groups, the group of 14 collapsed and then opened;
  - Test Assay 2's picker offering both the real `test_curated_dataset` and the planned `test_curated_dataset / curated_dataset`;
  - Launch then Submit on Test Assay 1 turning its edge solid and Test Assay 2 ready;
  - the List view.
- No `/api` request carried a sandbox id. The dashboard still loads the real programme list, as before.
- The cohort warning is covered by the panel spec (Test Assay 1 on subject 2 warns Test Assay 2).

## Left for the backend design

- Sample types on platform-dataset inputs: the real breast app reads 14 sample types from one dataset.
- An output's sample name that differs from its port name.
