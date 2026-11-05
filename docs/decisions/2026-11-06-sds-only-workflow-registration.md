# Register only SDS workflow packages in the portal, for now

- **Date:** 2026-11-06
- **Status:** Accepted

## Context

The portal's Workflow wizard accepts two kinds of source: an SDS package (`dataset_description.xlsx` at the
root, `primary/workflow_*.cwl` plus each step's `tool_*.cwl`, code in `code/`), and a folder or repository
with a workflow `.cwl` at its root. Only SDS packages reach the platform: their approval goes through the
handoff to the platform API ([2026-10-02-portal-sds-workflow-approval](2026-10-02-portal-sds-workflow-approval.md)).
A root-`.cwl` workflow is annotated by picking a registered tool for each step, and its "approval"
(`GET /api/builder/workflow/{id}/approval`) only gives the row a `sparc-workflow-` placeholder uuid and
pushes FHIR. It never creates a platform dataset, so assays can't use it. The redesigned hub cards
([2026-11-06-card-status-sentence](2026-11-06-card-status-sentence.md)) had no honest next step to offer
such a workflow.

## Alternatives Considered

### Option A: Keep both kinds, and finish the root-`.cwl` approval
- Pros: nothing a user does today stops working.
- Cons: the approval would have to package a root-`.cwl` source as a platform dataset, which is its own
  project; until then the wizard keeps promising something it can't deliver.

### Option B: Accept only SDS packages for now; keep the other code paths, unreachable (chosen)
- Pros: every workflow registered from the portal can be approved into the platform. The wizard says why
  it refuses a source, before anything is uploaded.
- Cons: users with a root-`.cwl` workflow must package it as SDS first. Existing root-`.cwl` rows can only
  be deleted.

### Option C: Remove the root-`.cwl` code paths
- Pros: less code.
- Cons: they would be rebuilt when root-`.cwl` support comes back.

## Decision

Option B. Step 1 of the Workflow wizard refuses a source that isn't an SDS package: "This folder isn't an
SDS package (no dataset_description.xlsx). Only SDS workflow packages can be registered for now." The
root-`.cwl` annotation branch in `BaseAnnotateStep.vue`, the legacy approval route and
`useWorkflowApproval` stay in place, marked `follow-up: non-SDS workflows`. A workflow row that isn't an SDS
package reads "Not an SDS package — not supported yet" on its card and offers only Delete.

This supersedes the part of [2026-10-02-workflow-type-independent-of-sds](2026-10-02-workflow-type-independent-of-sds.md)
that kept root-`.cwl` workflows supported in the portal wizard.

## Consequences

- Tools are unaffected: the Tool wizard still accepts a root-`.cwl` tool or an SDS-packaged one.
- Bringing root-`.cwl` workflows back means finishing their approval, then lifting the check in
  `BaseInformationStep.vue` and searching for the `follow-up: non-SDS workflows` markers.
