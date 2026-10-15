# Title SEEK tools and workflows with the portal name

- **Date:** 2026-10-15
- **Status:** Accepted

## Context

Tools and workflows are registered in SEEK with one RO-Crate POST ([2026-09-30-register-tools-in-seek-via-single-ro-crate-post.md](2026-09-30-register-tools-in-seek-via-single-ro-crate-post.md)). SEEK takes the workflow title from the crate's root `name` (`workflow_extractors/ro_crate.rb`). Until now we filled that with the CWL `label`, or the CWL file stem when there is no label.

The portal also asks the user for a name, prefilled from the folder name. It is stored as `dataset.dataset_name`, but never reaches SEEK. As a result:

- Two uploads that share a CWL, such as a package and a renamed copy, get the same SEEK title and can't be told apart in SEEK's list.
- The portal and SEEK name the same item differently.

## Alternatives Considered

### Option A: Keep the CWL label as the title
- Pros: no change. The title travels with the CWL file.
- Cons: the problems above remain. The only workaround is editing the CWL `label` before each upload.

### Option B: Portal name as the title, CWL label → stem as fallback
- Pros: SEEK shows what the user typed and saw in the portal. Small change: one optional `title` argument on the crate builders and the `Writer` register methods. It still uses SEEK's own extractor (root `name`), so the single-POST flow is unchanged.
- Cons: the CWL label no longer appears as the SEEK title when a portal name is given; it remains visible in the CWL file. The SEEK title is fixed at registration, so a later rename in the portal doesn't reach SEEK.

### Option C: Set the title with a PATCH after the crate POST
- Pros: the crate stays a pure function of the CWL.
- Cons: a second call to SEEK, plus a partial-failure state to roll back. The 2026-09-30 decision avoided exactly this.

## Decision

**Option B.** The crate root `name` is the portal name. When no name is given, or it is blank, the CWL `label` is used, and then the file stem. This applies to tool uploads and workflow uploads approved in the portal.

The step tools that a workflow upload registers have no name of their own, so they keep the CWL `label` → stem title. So does the `POST /datasets` direct-ingest route, which takes no name.

The root `description` stays the CWL `doc`. The main-entity file entry keeps the CWL `label` as its `name`.

## Consequences

- SEEK and the portal show the same name for tools and workflows uploaded through the portal.
- This partly supersedes the 2026-09-30 ADR, where Option C said SEEK sets the title from the CWL `label`. Tags, `internals` and the single POST are unchanged.
- SEEK workflows that are already registered keep their old titles. There is no backfill.
- The SEEK title can drift from the portal name if a rename feature is added later; such a feature would also need to update SEEK.
