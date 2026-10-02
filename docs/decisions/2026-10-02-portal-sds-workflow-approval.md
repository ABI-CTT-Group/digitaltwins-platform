# Portal workflow wizard: build and approve SDS workflow packages through the tool handoff

- **Date:** 2026-10-02
- **Status:** Accepted

## Context

You can't upload a workflow dataset such as `tests/data/workflow_image_conversion` from the portal's Workflow wizard. That dataset is an SDS package: `dataset_description.xlsx` sits at the root, `primary/` holds one `workflow_*.cwl` plus every step's `tool_*.cwl`, and the code is in `code/`. The wizard rejects it with "No CWL files found in the root of the selected folder".

When SDS tools were added (commit `86ce1cec`), workflows kept the root-`.cwl` rule on purpose. Every later step of the portal workflow flow assumes that rule:

- The build copies the whole source into `code/` and copies only root `.cwl` files into `primary/`.
- In the Annotation step, the user maps each CWL step to a portal tool that already exists.
- Approval (`GET /api/workflow/{id}/approval`) is a stub. It gives the workflow a `sparc-workflow-…` placeholder ID and annotates it with `fhir_cda.Annotator(...).workflow()`. Per [2026-10-02-workflow-dataset-ingest](2026-10-02-workflow-dataset-ingest.md), that annotator crashes on `run: tool_x.cwl`.

digitaltwins-api already ingests SDS workflow packages: one-shot upload, resumable sessions, the CLI and the client. Ingest creates one tool dataset per step, registers everything in SEEK, and optionally pushes an ActivityDefinition per tool and a PlanDefinition for the workflow. Portal tools already reach the API through an approval handoff (`app/services/tool_handoff.py`, [2026-10-01-unified-tool-dataset-ingest](2026-10-01-unified-tool-dataset-ingest.md)).

## Alternatives Considered

### Path from the portal to the platform

#### Option A: upload straight from the wizard to the API
- Detect an SDS workflow in the browser, ask for the workflow type and SEEK project, and send the files to `/datasets/uploads` directly. The portal build and approval steps are skipped.
- Pros: the least code; one validation path.
- Cons: there is no portal record, build log or approval gate. It also works differently from tools, which go through build and then approval.

#### Option B: the tool way: build, annotate, then an approval handoff (chosen)
- The wizard detects SDS workflow packages, from local folders and zips as well as Git.
- The build passes the package through unchanged.
- The Annotation step annotates each step's tool ports.
- Approval hands the latest build to `/datasets/uploads` (`category=workflows`) as the approving user, using the tool handoff's token relay and resume.
- Pros:
  - The same lifecycle and UI as tools: Registration, Annotation, Build, then Approve.
  - Re-approval replaces the previous version.
  - Deleting the portal workflow also deletes it from the platform.
- Cons: more code: a new layout module, a workflow handoff, DB columns, a reworked annotation branch and approval wiring.

#### Option C: only relax the frontend check
- Cons: the build would produce a broken dataset (the package nested inside `code/`, nothing in `primary/`), and approval still uploads nothing.

### Root-`.cwl` workflows

#### Option A: keep their current flow (chosen)
- Pros: nothing existing changes.
- Cons: two approval paths stay side by side until the stub is retired.

#### Option B: assemble an SDS package from the selected portal tools
- Cons: much larger. It also duplicates tools that are already approved, because the API creates new tool datasets on every upload.

### Handoff code

#### Option A: reuse `tool_handoff`'s machinery, with a thin `workflow_handoff` (chosen)
- `tool_handoff.run` gets a build model and a completion callback as parameters. `workflow_handoff` supplies its own `start`, `fhir_descriptions` and `_complete`, and reuses `Api`, `relay`, `progress`, `_files`, `_send_parts` and `_wait`.
- Pros: one implementation of token relay and resume. Tool behaviour is unchanged.
- Cons: `tool_handoff` becomes slightly more general than its name suggests.

#### Option B: a copy of `tool_handoff` for workflows
- Cons: about 150 duplicated lines, and the two copies of the token logic would drift apart.

### What happens to a workflow's tools on delete and re-approval

#### Option A: delete them with the workflow (`delete_tools=true`) (chosen)
- Pros: the API created those tools for this workflow, so nothing is left orphaned.
- Cons: none for portal-approved workflows. The API never shares tools between uploads.

#### Option B: keep them
- Cons: every re-approval would leave a set of orphan tool datasets behind.

## Decision

Option A in every section except the first, where Option B was chosen:

1. **Detection.** A source whose resolved root has `dataset_description.xlsx` is an SDS workflow package. It needs exactly one `primary/workflow_*.cwl`. All other workflow rules are left to the API's `load_workflow` at finalize, so they live in one place.
2. **Workflow type.** It is chosen in the Registration step (script, notebook or gui) and stored as `workflows.workflow_type`. "This workflow is an SDS package" is equivalent to "`workflow_type` is set". The build fails when the two don't match. *Superseded by [2026-10-02-workflow-type-independent-of-sds](2026-10-02-workflow-type-independent-of-sds.md): every workflow has a type, and the build sets `workflows.is_sds`.*
3. **Build.** The package is copied as it is, without `.git`, `node_modules`, `dist` or `build`, and nothing is npm-built. A gui workflow's tool is stored as source, the same as through the API or the CLI.
4. **Annotation.** Each step gets per-port FHIR resource types, read from the step's packaged `tool_*.cwl`. They are stored as `{"steps": [...]}` in `fhir_note`, and the handoff turns them into `{"workflow": {..., "action": [...]}, "workflow_tools": {...}}`.
5. **Approval.** `POST /api/workflow/{id}/approval` and `GET /api/workflow/{id}/approval/status` mirror the tool endpoints. The legacy `GET /api/workflow/{id}/approval` refuses SDS workflows with a 409.
6. **Delete and re-approval.** These call `DELETE /datasets/{uuid}?delete_tools=true`.
7. **Authentication** is consistent with tools and measurements:
   - every `/api/workflow` endpoint needs a valid Keycloak token, as `/api/tools` does;
   - writes need `admin` or `researcher`. These are create, upload-source, probe-source, annotation, build, both approvals and delete. digitaltwins-api applies the same rule to measurements (`require_upload_role`).

## Consequences

- Portal-approved SDS workflows appear in SEEK, MinIO, Postgres and FHIR exactly as API uploads do. The Workflow Hub lists them once: the portal row carries the dataset UUID, so the platform row is de-duplicated.
- The workflow router is no longer open.
  - Anonymous requests get 401, and users without `admin` or `researcher` can no longer create, build, approve or delete workflows.
  - `/metadata` and `/{expose}/primary/...` also need a token now, as their tool counterparts already do. No caller of either was found in the repo. A consumer outside the repo would have to send a token.
- Root-`.cwl` workflows still use the placeholder approval, so this ADR does not retire it.
- Steps that run the same tool share one ActivityDefinition, so the first such step's annotation is the one used for that tool. Each tool's ActivityDefinition takes the workflow's version, because an SDS workflow package has only one version.
- A source with `dataset_description.xlsx` counts as SDS. Without exactly one `primary/workflow_*.cwl` it is rejected, even if it also has a root `.cwl`. This matches the tool rule.
- `delete_plugin` is async, so it runs the platform DELETE in a worker thread (`asyncio.to_thread`), which keeps the event loop free. If the platform rejects the token, delete keeps the workflow and asks the user to sign in again.
