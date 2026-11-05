# The FHIR annotation is optional, and only an annotated item is published to FHIR

- **Date:** 2026-11-06
- **Status:** Accepted

## Context

Each hub approved its items in its own way, with its own rule about FHIR:

- A measurement could be approved only once it had an annotation, though the platform commits it without one.
- Tools and workflows had a "Publish to FHIR" checkbox in their approval dialog, ticked by default.
- The Models hub's inline dialog said a model is "published to FHIR as a Device" only when it had an annotation.

The wizards made the annotation step look required. Users who didn't know which FHIR resource a port becomes
couldn't finish a registration, and an approver had to decide about FHIR a second time, at approval.

The platform also treated an item without an annotation differently by category:

- **Measurements and models.** The portal creates every upload with the API's default `fhir: "none"`; only
  saving an annotation switches the session to `"descriptions"`. A commit in `"none"` mode stores no
  descriptions and queues no FHIR push (`_commit` and `run_commit_job` in
  `services/api/src/digitaltwins/measurements/jobs.py`). A later push without an annotation fails
  (`test_push_without_an_annotation_fails_cleanly`).
- **Tools and workflows.** With `fhir: true`, the builder's handoff sends FHIR descriptions even without an
  annotation: for a tool, only its version (`tool_handoff.fhir_descriptions`). The API then pushes an
  ActivityDefinition, or a PlanDefinition plus an ActivityDefinition per bundled tool, with no port types.
  With `fhir: false` the handoff sends no descriptions, and the commit pushes nothing, as for datasets.

Nothing in the platform reads a tool's or workflow's FHIR resources; the builder's workflow delete only removes
them if they exist.

## Alternatives Considered

### Option A: Keep a "Publish to FHIR" choice at approval
- Pros: the approver can keep an item out of FHIR, or publish a bare definition.
- Cons: two places decide one thing (the annotation, then the checkbox), and the measurement and model hubs
  never had the choice.

### Option B: Require an annotation before approval, everywhere
- Pros: everything in the platform is fully annotated in FHIR.
- Cons: blocks registration on knowledge many registrants don't have; the platform doesn't need it.

### Option C: The annotation is optional, and decides FHIR (chosen)
- Pros: one rule for all four categories: with an annotation, approving publishes it to FHIR; without one,
  nothing goes to FHIR. One decision, made where the annotation is edited. Approval asks only what it must
  (a SEEK project for tools and workflows).
- Cons: a tool or workflow approved without an annotation isn't in FHIR at all, not even as a bare definition,
  and can't be annotated in the portal afterwards.

## Decision

Option C.

- **Every wizard's annotation step is optional.** It's titled "FHIR annotation (optional)" and has "Skip for now".
  Cards offer Add/Edit FHIR annotation until the item is approved. After approval, models use Edit FHIR
  annotation, and measurements and models use Retry FHIR.
- **One Approve dialog for the four hubs** (`ApproveDialog.vue`, `approveAdapters.ts`), with no FHIR checkbox.
  Tools and workflows send `fhir: hasAnnotation`. For an item with no annotation, the dialog says so:
  - tools, workflows and measurements: "No FHIR annotation, so nothing is published to FHIR. To publish it,
    add one before approving." (The portal annotates these only before approval.)
  - models: "No FHIR annotation, so nothing is published to FHIR. You can add one later from its card."
- The dialog shows the approval's progress. It can be closed mid-way without cancelling anything, because the
  card keeps following the approval.

This reverses the plan's earlier choice (decision D7 of the registration UI plan) that tools and workflows
always send `fhir: true`.

## Consequences

- `ToolApprovalDialog.vue`, `measurements/components/ApprovalDialog.vue`, `SubmitProgress.vue` and the Models
  hub's inline dialog are gone. A new category needs an adapter in `approveAdapters.ts`.
- To put a tool or workflow approved without an annotation into FHIR, delete it and register it again with one,
  until the portal can annotate items after approval.
- An annotation saved with no port types still counts: the item is published, without them.
- Tools and workflows uploaded through the REST API or the CLI keep their own `fhir` setting; this decision
  covers the portal.
