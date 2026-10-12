# One tag vocabulary for the dataset hub cards

- **Date:** 2026-10-12
- **Status:** Accepted

## Context

The four portal hubs (Measurements, Models, Tools, Workflows) each tagged their
cards with a single status chip, but the chip meant different things:

- On tools and workflows it showed the portal build, so `completed` meant "the
  build finished".
- On measurements and models it mixed upload, registration and FHIR state, so
  `completed` meant "in platform", and a FHIR push showed as `uploading…` or
  `registering…` even though the files were already stored.
- The two session-based hubs used different words for the same states
  (`pending` vs `awaiting approval`, `completed` vs `registered`).
- Approval progress, "in platform", "platform upload", a `stage ·` chip and a
  bare `FHIR` chip each appeared on some hubs only.

Users comparing hubs could not tell whether two words meant the same state.

## Alternatives Considered

### Option A: Keep one status chip per card, aligning the words
- Pros: smallest change.
- Cons: a single chip still has to mix build, registration and FHIR, which is
  what caused the confusion.

### Option B: Separate chips for registration, FHIR and build
- Pros: each chip answers one question; FHIR state visible on every hub.
- Cons: one more chip on every card; tools and workflows need their platform
  dataset's FHIR status.

### Option C: Separate registration and build chips, no FHIR chip (chosen)
- Pros: one registration chip with five words used by every hub; build state
  labelled `build · …`, so it can no longer be read as registration; a FHIR
  failure still shows, as an amber `in platform` with the reason on hover.
- Cons: a successful FHIR publish, and FHIR details saved before approval, are
  not visible on the card.

Wording alternatives that were rejected:

- `awaiting approval` for an unsubmitted item. It implies someone else must
  act, but the user approves it themselves, so it is `draft`.
- `uploading…` for an unfinished chunked upload. Leaving the upload wizard
  stops the upload (`InformationStep.vue` calls `uploader.stop()`), so on the
  hub it is `upload paused`.
- A combined `ready to register` state. It ties build and annotation readiness
  to registration, with different rules per hub. Readiness is read as `draft`
  plus `build · completed` instead.
- Keeping `platform upload` for REST/CLI uploads. The portal can only detect
  these for tools and workflows, so the chip itself was inconsistent.

## Decision

Option C. Every card shows, in this order:

1. **Registration** (always): `upload paused` · `draft` · `registering…` ·
   `registration failed` · `in platform`. `in platform` turns amber when a FHIR
   push or a later re-approval failed.
2. **`build · <status>`**: tools and workflows built by the portal.
3. **`deploy · <status>`**: unchanged.
4. **Type** (`gui` / `script` / `notebook`): tools and workflows.
5. Descriptive chips, then the date.

The colours follow one rule: grey waits for the user, cyan is running, green is
done, red failed, amber is done but needs attention. A red or amber chip's
tooltip gives the reason, which replaces the `stage ·` chip and the model card's
inline failure text.

The labels, colours and derivations live in one module,
`services/portal/frontend/src/views/upload-dataset/components/cardTags.ts`, so
the hubs cannot drift apart again.

## Consequences

- Tool and workflow cards read their platform dataset's `fhirStatus` from the
  `/datasets` listing the hubs already fetched. `usePlatformTools` /
  `usePlatformWorkflows` became `withPlatformTools` / `withPlatformWorkflows`,
  which attach it to the portal's items and append the platform-only ones. No
  extra request is made.
- Failure reasons are only in tooltips, which need a mouse.
- A new state or hub has to be added in `cardTags.ts`, not in a card.
- The Models hub gained the same "Registration status" filter as the other hubs.
