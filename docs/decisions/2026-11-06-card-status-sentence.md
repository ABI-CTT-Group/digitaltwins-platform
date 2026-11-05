# A status sentence and one next step on every hub card

- **Date:** 2026-11-06
- **Status:** Accepted

## Context

The [card tag vocabulary](2026-10-12-card-tag-vocabulary.md) gave the four dataset hubs (Tools, Workflows,
Measurements, Models) the same words, but a tool or workflow card still carried up to eight chips
(`draft`, `build · completed`, `deploy · completed`, type, version, author, date...). Users could read
each chip yet still not tell what state the item was in, or what to do next. The hub filter only split
"in platform" from "not in platform", so a failed build and a draft looked alike. Every action sat in
the card menu under a different name ("Submit to approval", "Approval (upload to MinIO)",
"Approve (register model)"). Measurements could be approved only with a FHIR annotation, though the
platform commits them without one.

## Alternatives Considered

### Option A: Keep the chips and shorten their words
- Pros: smallest change.
- Cons: the user still has to combine several chips into one state, and the next step stays hidden
  in the menu.

### Option B: One status sentence and one next-step button per card (chosen)
- Pros: each card answers "where is it, and what do I do?" in one line and one button. Chips are left
  for facts (type, version) and for problems on an item that otherwise works, such as a failed
  backend. The filter can group items by what they need.
- Cons: every state needs a written sentence; a card shows fewer details at a glance (author and date
  are gone).

### Option C: A progress tracker per card (registered → built → approved)
- Pros: shows how far along an item is.
- Cons: the steps differ per category, and most states that need attention (FHIR failed, backend
  failed, newer build not approved) are not steps.

## Decision

Option B. `services/portal/frontend/src/views/upload-dataset/components/cardStatus.ts` maps an item to
`{sentence, reason, hint, tone, group, action, problems}`; `StatusLine.vue` shows it and each card
renders the action as its one button. The state tables are in the
[registration UI plan](../artifacts/2026-11-05-151525-registration-ui/plan.md), and `cardStatus.spec.ts`
has one case per row.

- **Words.** One verb for committing an item to the platform: **Approve** ("Approving…",
  "Approval failed", "Approve again"). The state that ends it is **In the platform**.
- **Colour: quiet when fine, loud when not.** Steady states keep the text colour, running is pale,
  needs-you is amber (`--tone-needs`), failed is coral (`--tone-failed`). A problem on an item that
  otherwise works is a coral chip with the reason on hover. The category accent is only on the card's
  edge and kind label.
- **Filter.** All · Needs you · In progress · In the platform (`hubFilter.ts`). "Needs you" items sort
  first, and the chip counts them.
- **Menus** hold what isn't the button: Launch, Rebuild, Stop backend, View logs, Add/Edit FHIR
  annotation, Deploy DAG again, Delete.
- **FHIR annotation is optional for approval.** A staged measurement shows Approve with or without an
  annotation; the platform publishes to FHIR only what the dataset has.
- **Workflows that aren't SDS packages** say "Not an SDS package — not supported yet" and offer only
  Delete. Their legacy approval call stays in `workflow_api.ts`, unused, for a later change.

## Consequences

- The builder adds the fields the sentences need: `has_annotation` on tool and workflow list rows, the
  deploy `error` on `/tools/plugin/build/{id}/deploys`, and `build_error` / `deploy_error` on
  `/workflow/gui-tools` rows. The hubs keep the latest build's `error_messages` as the "Build failed"
  reason.
- A failure's reason shows under the sentence (two lines, in full on hover). A problem chip's reason is
  still only on hover.
- A tool or workflow in the platform whose latest build completed but was never approved reads "a newer
  build isn't approved yet", from that build's `handoff_status`. Every approval that gave an item a real
  platform uuid also marked its build `completed` (`tool_handoff.py`, `workflow_handoff.py`); approvals
  before handoffs existed gave only a `sparc-tool-` / `sparc-workflow-` placeholder, so those items read
  "Built — not in the platform yet" instead.
- A never-built tool or workflow offers Continue registration, which reopens its wizard at
  `/catalogue/<hub>/<id>/register`, at the FHIR annotation step until it has one and at the build after.
- A new state is added in `cardStatus.ts` and its spec, not in a card. `cardTags.ts` is gone.
