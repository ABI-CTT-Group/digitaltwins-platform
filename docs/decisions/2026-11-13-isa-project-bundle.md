# Upload an ISA project with its bundled datasets, workflows and tools

- **Date:** 2026-11-13
- **Status:** Proposed

## Context

An ISA project (prototype, draft schema `0.1-draft`) describes a project's investigations, studies
and assays, with each assay's workflow, cohort and inputs. Until now an upload was accepted only when
every dataset and workflow it names was already on the platform. A group that has a study design but
no data or workflows on the platform yet had no way in.

Only a frontend prototype exists (`services/portal/frontend/src/views/isa-project/`). This records the
choices it makes so the ISA backend design can confirm or replace them before anything reads bundles
for real.

## Alternatives Considered

### Option A: Guided steps
Upload the JSON, then attach a folder to each missing item, one at a time.
- Pros: each mistake shows up next to the item it belongs to.
- Cons: many picks for a large design, and the design and its data travel separately.

### Option B: One bundle (chosen)
One folder or .zip with the JSON at its root and a `datasets/<id>/` folder for each item the platform
doesn't have.
- Pros: one pick; the bundle can be zipped and handed on as a whole.
- Cons: users must learn a folder layout.

### Marking an item as new: an explicit list in the JSON
A `newDatasets` / `newWorkflows` section in the JSON.
- Pros: a typo in a platform id stays an error and doesn't look like a new item.
- Cons: a schema change, and the same id is written in two places.

### Who owns a bundled item: the project
A bundled item stays with the project that brought it.
- Pros: nothing is shared before anyone has reviewed it.
- Cons: two projects that bring the same data keep two copies, and other projects can't use it.

## Decision

- **One bundle**: `isa-project.json` (the only .json at the root) and `datasets/<id>/` folders. A single
  wrapper folder is ignored.
- **An id the platform doesn't have names a bundled item.** It needs a folder of that name; there is
  no schema change. A folder nothing in the design uses, or one whose id is already on the platform, is
  left out with a warning.
- **Every folder is an SDS package**: `dataset_description.xlsx` at its root, as the builder's SDS
  check requires. A dataset folder also needs files under `primary/`. A folder with one
  `primary/workflow_*.cwl` is a workflow, whose ports, categories (CWL `doc`) and steps come from that
  CWL. A folder with only `primary/tool_*.cwl` is a tool. Anything else is a dataset.
- **A step's tool** is the platform tool of the same name when there is one, otherwise the tool CWL in
  the workflow package, otherwise a tool package in the bundle.
- **One category per bundled dataset**: inputs that read it as different categories are an error.
- **Lifecycle**: approving the project creates its SEEK project and registers its bundled items through
  the normal register and approve steps. After that they are ordinary platform items any project can
  use. The prototype simulates this in the browser.

## Consequences

- A typo in a platform id is reported as a missing folder, unless the bundle has a folder with the
  same typo; then it becomes a bundled item.
- A tool CWL in a workflow package with a platform tool's name is ignored, even when it differs (for
  example, another Docker image). The backend should follow the real SDS workflow approve flow here.
- **Download JSON** gives the JSON only, so it can't be uploaded again on its own while it names
  bundled items.
- The backend has to accept one large upload that holds several datasets.
