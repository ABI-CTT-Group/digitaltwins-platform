# Portal workflows: the type is always asked; the build detects SDS packages

- **Date:** 2026-10-02
- **Status:** Accepted

## Context

Decision 2 of [2026-10-02-portal-sds-workflow-approval](2026-10-02-portal-sds-workflow-approval.md) made `workflows.workflow_type` do two jobs: it is the workflow's type, and setting it is what marks the workflow as an SDS package. So the Workflow wizard can only ask for the type after it has detected an SDS source. The radio appears late, at the bottom of the form, and only for SDS packages. The Tool wizard asks for its type first, every time.

Root-`.cwl` workflows stay supported, with their legacy approval.

## Alternatives Considered

### Where "is SDS" lives

#### Option A: keep `workflow_type` as the SDS marker
- Pros: no change.
- Cons: the type can't be asked first, and the two wizards stay inconsistent.

#### Option B: a separate `workflows.is_sds` column (chosen)
- Pros: the type is just the type, and it can be required for every workflow.
- Cons: a new column, plus a one-time backfill for existing rows.

#### Option C: make the wizard accept only SDS packages
- Pros: no new column. The type is always meaningful.
- Cons: new root-`.cwl` workflows could no longer be registered. Rejected by the user.

### Who sets `is_sds`

#### Option A: the client sends the probe result at create; the build verifies it
- Pros: the least code.
- Cons: the server relies on a value relayed by the client until the build checks it.

#### Option B: the server detects it at create
- Pros: free for local sources, whose staged folder is already there.
- Cons: Git sources would need a second clone, using the access token that create deliberately never receives. So it fails for private repositories.

#### Option C: the build detects it, as for tools (chosen)
- Pros: the server is the only authority, and it matches how tools work (`detect_tool_layout` at build). The Annotation step works out SDS from the CWL files it already loads.
- Cons: `is_sds` is unknown until the first successful build. That has no effect, because approval already requires a completed build.

## Decision

- `workflow_type` (`script|notebook|gui`) is required for every new workflow and is asked first in the wizard.
- `workflows.is_sds` is written only by a successful build, from `detect_workflow_layout`. Before the first build it is `NULL`, which means not SDS.
- When the column is added, existing rows are backfilled once with `is_sds = (workflow_type IS NOT NULL)`.
- SDS approval, the legacy approval's refusal and the Annotation step's branch all check `is_sds`. The platform delete checks `in_platform` alone, because only the SDS handoff assigns a real dataset UUID.
- This replaces decision 2 of [2026-10-02-portal-sds-workflow-approval](2026-10-02-portal-sds-workflow-approval.md).

## Consequences

- The Workflow and Tool wizards ask for their type in the same place.
- New root-`.cwl` workflows store a type. Nothing uses it yet apart from the card's type chip.
- The backfill must run only when the column is first created. Running it again would mark root-`.cwl` workflows that have a type as SDS.
- If a rebuild of a Git source finds a different layout, it updates `is_sds`. Approval always follows the latest completed build.
