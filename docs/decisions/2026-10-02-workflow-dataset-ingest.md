# Ingest workflow datasets together with their tools

- **Date:** 2026-10-02
- **Status:** Accepted

## Context

The dataset upload API can ingest tool datasets (see [2026-10-01-unified-tool-dataset-ingest.md](2026-10-01-unified-tool-dataset-ingest.md)). We now need to ingest **workflow** datasets of three types:

- **script:** any number of script-tool steps;
- **notebook:** one notebook-tool step;
- **gui:** one GUI-tool step.

A workflow dataset is laid out like a tool dataset:

- `primary/workflow_*.cwl` (`class: Workflow`);
- a copy of each step's `primary/tool_*.cwl`;
- the code in `code/`.

The examples are `tests/data/workflow_image_conversion` and `tests/data/workflow_volview`. Uploading a workflow must also register its tools.

Several things constrain the design:

- The `workflows` category and MinIO bucket already exist and are in use:
  - assay workspace outputs default to it (`app/routers/assays.py`);
  - the portal's `WorkflowBuilder` writes `workflows/<expose_name>/`.
- SEEK checks the caller's Keycloak token, which lives only 300 s.
- The listing `GET /workflows` reads SEEK workflows tagged `workflow`.
- `fhir_cda`'s `WorkflowAnnotator` expects inline step definitions. It crashes on `run: tool_x.cwl`.

## Alternatives Considered

### Tool records

#### Option A: a separate tool dataset per tool CWL (chosen)
- Pros:
  - Tools appear in tool listings and in SEEK as tools.
  - They get their own FHIR ActivityDefinition, which the workflow's PlanDefinition links to.
- Cons:
  - Code is stored twice, once in the workflow and once in each tool.
  - There are more registrations to roll back on failure.

#### Option B: SEEK entries only
- Pros: one MinIO dataset.
- Cons: tools exist in SEEK with no dataset behind them.

#### Option C: embedded only
- Pros: the simplest option.
- Cons:
  - Tools are invisible to tool listings.
  - There is no ActivityDefinition to link from the PlanDefinition.

### Splitting `code/` between tools

#### Option A: a hybrid split by type, with per-tool subfolders (chosen)
1. If `code/<tool_stem>/` exists, it becomes that tool's `code/`.
2. Otherwise, a script tool gets the top-level `code/<tool_stem>.*` files.
3. Otherwise, a notebook or gui tool, which is the only step, gets all of `code/`.

- Pros: handles both examples as they are, and allows an explicit layout.
- Cons: two conventions to document.

#### Option B: subfolders only
- Cons: the example datasets would have to be restructured.

#### Option C: the whole `code/` for every tool
- Cons: script tools carry files that aren't theirs.

### Category and bucket

#### Option A: share `workflows`, with `dataset.workflow_type` as the discriminator (chosen)
- Pros:
  - Matches the category name that was asked for.
  - The other writers are untouched.
  - Keys can't collide: `<uuid>/` versus `<expose_name>/`.
- Cons:
  - Code must never branch on the category alone. A workflow *definition* is a dataset with `workflow_type` set.

#### Option B: move assay outputs elsewhere
- Cons: extra scope and a behaviour change for assays.

#### Option C: a new category name
- Cons: deviates from the requested name.

### FHIR descriptions

#### Option A: our own builder, keyed by CWL step id (chosen)
- Clients send `{"workflow": {...}, "workflow_tools": {<step_id>: {...}}}`.
- Pros: works with `run:` file references, and validates step and port ids.
- Cons: we maintain the description shape ourselves.

#### Option B: `fhir_cda.Annotator(...).workflow()`
- Cons: crashes on our CWL layout, and its glob picks up tool CWLs as the workflow.

### Delete

#### Option A: a required `delete_tools=true|false` for workflow datasets (chosen)
- Without it, the API returns 409 listing the tools.
- Deleting a tool that a workflow still uses returns 409.
- Roles stay `admin|researcher`.
- Pros: the client has to confirm explicitly.
- Cons: one extra round-trip for clients that don't know about it.

#### Option B: default to keeping the tools
- Cons: it is easy to orphan tools by accident.

## Decision

Option A in every section.

The commit is all-or-nothing:

1. Every SEEK registration is made first, because of the short token: each tool tagged `tool` + type, then the workflow tagged `workflow` + type. The workflow's RO-Crate packs the tool CWLs it references.
2. Then the tool datasets are stored (`tools/<uuid>/`), followed by the workflow dataset as uploaded (`workflows/<uuid>/`).
3. Then the links are written: `dataset.seek_id`, `tool_type` / `workflow_type`, and a `workflow_tool(workflow_dataset_uuid, step_id, tool_dataset_uuid)` row per step.
4. If anything fails, everything already created is undone.

FHIR is opt-in, as for tools:

1. The tools' ActivityDefinitions are pushed first.
2. Then the workflow's PlanDefinition, whose actions point to them through `related_tool_uuid`.

Verified against the live SEEK on 2026-10-02:

- SEEK accepts a workflow crate that packs its tool CWLs.
- It resolves the steps' `run: tool_*.cwl`, tags the workflow, and extracts the workflow's inputs, outputs and steps into `internals`.

## Consequences

- Re-uploading a workflow creates new tool datasets. Tools are not deduplicated or reused.
- The `workflow_tool` foreign key to the tool dataset has no cascade. A tool that a workflow uses can't be deleted on its own.
- Every reader of the `workflows` category must check `workflow_type` to tell workflow definitions apart from assay outputs.
- Airflow DAGs found in `code/` are stored, not deployed.
