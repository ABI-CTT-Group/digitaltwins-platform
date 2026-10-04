# Link an assay to its workflow from the portal through an auto-created SEEK SOP

- **Date:** 2026-10-05
- **Status:** Accepted

## Context

The portal finds an assay's workflow by walking SEEK: Assay → SOP → Workflow. It uses the first workflow it finds. Postgres separately stores `assay.workflow_seek_id`, which names the Airflow DAG (`workflow_<id>`).

Before this change, the SEEK side of that link had to be built by hand in SEEK. An assay with no linked workflow also crashed the dashboard's assay loader: its configure pencil, and the pencil of every assay after it, spun forever.

We want admins and researchers to pick the workflow in the portal's "Configure assay" dialog.

We checked SEEK (`ldh:v0.3.2`) on a live instance:

- **What its JSON:API accepts.** `POST /sops` accepts `projects`, `assays` and `workflows` relationships plus a `policy`. `PATCH /sops/{id}` can replace `relationships.assays`. `assayPatch` has no `sops` relationship.
- **A remote-URL content blob is rejected.** SEEK fetches the URL anonymously when the SOP is created (`process_from_url`). A private workflow's page returns 403, so `POST` fails with `400 bad upload`.
- **A placeholder blob followed by a `PUT` of its content works.**

## Alternatives Considered

### Where the link lives

- **SEEK SOP + Postgres `workflow_seek_id` (chosen).**
  - Pros: SEEK stays the provenance record, and the existing read path (the card, the dialog) keeps working.
  - Cons: one save writes to two stores, which needs a rollback.
- **Postgres only.**
  - Pros: no SEEK writes; `POST /assays` can already store `workflow_seek_id`.
  - Cons: SEEK no longer shows which workflow an assay runs, and the card's SOP walk would disagree with the config.
- **A direct assay ↔ workflow link in SEEK.**
  - Pros: no placeholder SOP.
  - Cons: breaks the Assay → SOP → Workflow convention the querier relies on.

### SOP reuse

- **A new SOP per assay link (chosen).**
  - Pros: simple; it lives in the assay's own project(s).
  - Cons: some duplicate SOPs in SEEK.
- **One SOP per workflow, shared by assays.**
  - Pros: less clutter.
  - Cons: needs lookup logic, and an SOP shared across projects raises permission edge cases.

### SOP content

- **A remote URL to the workflow page.** Rejected: it fails for private workflows (see Context).
- **A generated `workflow-link.md` (chosen).** It is created as a placeholder blob, then a `PUT` uploads a short markdown body naming the assay and the workflow.
- **A copy of the workflow's CWL.** Rejected: it duplicates content and needs extra fetching.

### API shape

- **A `link_workflow` flag on `POST /assays` (chosen).**
  - Pros: the SEEK link and the Postgres config happen in one request with one undo.
  - Cons: the route does two things when the flag is set.
- **A new `PUT /assays/{id}/workflow`, called by the portal before `POST /assays`.**
  - Cons: if the second call fails, SEEK and Postgres disagree, and undoing it over HTTP means creating yet another SOP.

### Assay type vs workflow type

- **Filter the picker by the assay's SEEK tag (chosen).** No tag writes, and a mismatch can't happen.
- **Also filter by project (chosen).** Only workflows that share a SEEK project with the assay are offered. SEEK's API would otherwise let any workflow the user can see be linked, including ones from other projects.
- **Write the workflow's type into the assay's tag.** Rejected: it adds another SEEK PATCH.
- **No coupling.** Rejected: a script assay could be linked to a GUI workflow.

## Decision

The "Configure assay" dialog has a workflow picker, limited to workflows whose type equals the assay's tag and that belong to one of the assay's SEEK projects. Picking a workflow only changes the form: its ports become the inputs and outputs, and the cohort is cleared. If a workflow was already linked, the user confirms first.

On Save, the portal sends `POST /assays` with `link_workflow: true`. For admin and researcher users, the API then calls `link_assay_workflow`, which:

1. Leaves everything alone if the assay's first linked workflow already is the chosen one.
2. Otherwise detaches the assay from every SOP that links a workflow. Plain protocol SOPs are kept, and detached SOPs stay in SEEK.
3. Creates `Workflow link: <title>` in the assay's projects:
   - policy: `no_access` publicly, `view` for those projects
   - its `workflow-link.md` content is uploaded
4. Saves the Postgres config.

If the save fails, the SEEK change is undone on a best-effort basis: the new SOP is deleted and the old SOPs are re-attached. A SEEK failure is returned as 502. Calls without the flag (for example `util/populate-cpu-burn-assay.sh`) behave as before.

## Consequences

- An assay can be wired to a workflow without leaving the portal. The first save no longer freezes the workflow: re-picking replaces the link and resets the form.
- Each relink leaves one detached SOP in SEEK, kept as history.
- The SOP belongs to the user who saved it. Detaching an SOP someone else owns needs edit rights on it; without them, SEEK's error surfaces as a 502.
- An assay with no type tag gets an empty picker, and so does an assay whose project has no workflow of its type. The fix is to tag the assay, or to register the workflow in that project, in SEEK.
- The project rule is also enforced by the API. `link_assay_workflow` raises `WorkflowNotInAssayProject` (returned as 400) before changing SEEK. The check runs only when a new link would be created, so re-saving an assay whose existing link already points at that workflow stays a no-op, even if someone made that link by hand in SEEK across projects.
- A save now makes about 6 SEEK calls, which must fit in the portal-to-API timeout (15 s).
