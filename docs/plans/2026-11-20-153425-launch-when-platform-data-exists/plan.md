# Plan: Launch a linked assay when its platform data exists

## Context
In the example ISA project's study design (`/study-dashboard`), an assay's Launch stays disabled until
every earlier assay it reads from is submitted in the page. That run state lives only in the page, so a
reload forgets earlier submissions. The linked platform assays don't need it: each reads datasets
configured in advance on the platform, which already exist.

Request: Launch is always on if the dataset is there.

## Decision
- A linked assay counts as **ready** when every dataset its platform configuration reads exists on the
  platform, whether or not the earlier assays are submitted in the page.
- The check: the platform assay's configuration (`/dashboard/assay-details`) names a dataset per input;
  each must be listed by `/dashboard/datasets?category=<input category>`. No configuration, an input
  with no dataset, or a failed request means not ready (the old rule then applies).
- Planned edges stay dashed until the producer is submitted: the planned dataset still doesn't exist.
- "Simulate next run" still follows the chain (producers submitted), so it fast-forwards one wave at a
  time.
- Unlinked assays (uploads) keep the old rule.

## Steps (tests first)
1. Model: `Sim.available` (assays whose platform data exists); `assayStatus` treats them as ready;
   `simulateRunStep` ignores it. → `isaProject.spec.ts`
2. `platformInputsExist(seekId)` in `platformRun.ts`. → `platformRun.spec.ts`
3. `StudyDesign.vue`: check each linked assay on load, keep the result across Reset.
   → `StudyDesign.spec.ts`
4. Rebuild `portal-frontend`; check in headless Firefox.

## Verification
`make test-frontend`, `make lint`, `make docs-check`; screenshot of the pilot study with downstream
Launch buttons on.

## Outcome
- All ten pilot assays, and the four in "Image pipeline test", show "Ready to run" with Launch on,
  because every dataset their platform assays read is on the platform.
- Edges from assays that aren't submitted yet stay dashed (planned).
- "Simulate next run" still runs one wave of the chain per click.
- Checks: `make test-frontend` (520 tests), `make lint` and `make docs-check` pass; headless Firefox
  check of the pilot study's List and Flow views.
