# Walkthrough: PR4, one Approve dialog

Plan: [plan.md](plan.md). Tasks: [tasks.md](tasks.md). ADR: [optional FHIR annotation](../../decisions/2026-11-06-optional-fhir-annotation.md).

## What changed
- **One dialog.** `components/ApproveDialog.vue` approves items from all four hubs.
  - **Confirm:** one paragraph on what approving does. Tools and workflows also pick a SEEK project, defaulting to the previous approval's. An item with no FHIR annotation gets one amber line saying what is published instead.
  - **Progress:** the current stage, with a bar for upload parts. It reads "Waiting for you to sign in again" when the handoff needs a fresh token.
  - **Outcome:** "<name> is in the platform.", with a coral line when the FHIR push failed ("Retry it from the card"). Or "Approval failed" with the reason.
  - **Closing.** You can close the dialog at any point. Closing doesn't cancel anything: the card keeps following the approval, and the hub refreshes.
- **One progress shape.** `components/approveAdapters.ts` maps each category's calls onto `{state, stage, percent, error, fhirError}`.
  - Tools and SDS workflows use the builder handoff. They send `fhir: hasAnnotation`, then follow the platform dataset's FHIR push.
  - Measurements and models commit their staged upload.
  - The adapters also hold the confirm copy (`APPROVE_INTRO`) and `fhirHint`. The hint for a tool, workflow or measurement says to add an annotation before approving, because the portal annotates those only before approval; a model's card can add one afterwards.
- **No FHIR checkbox; one rule.** With an annotation, approving publishes it to FHIR; without one, nothing goes to FHIR, for all four categories. Measurements and models already worked this way (the portal's uploads use the API's default `fhir: "none"`). Tools and workflows used to send `fhir: true` always, which published a bare ActivityDefinition or PlanDefinition with no port types; they now send `fhir: hasAnnotation`. This reverses the plan's D7 (always `fhir: true`), at the reviewer's request. The glossary entry says the same.
- **Removed:** `ToolApprovalDialog.vue` (its spec cases moved into `ApproveDialog.spec.ts` and `approveAdapters.spec.ts`), `measurements/components/ApprovalDialog.vue`, `SubmitProgress.vue`, and the Models hub's inline dialog. The tool card's Approve now emits the tool row, so the hub no longer refetches the list to find it.

## Deviations from the plan
- `ApproveDialog.vue` and `approveAdapters.ts` sit in `components/` with the other shared hub components, not in a new `components/approve/` folder, so the code map needs no change.
- The measurement dialog's five stage chips (only one of which the server reports) became one stage line, the same as for the other categories.

## Verification
- `make test`: api 407, builder 260 (12 skipped), frontend 286, util 5. `approveAdapters.spec.ts` and `ApproveDialog.spec.ts` were red first; `cards.spec.ts` was updated for the row emit.
- `make lint` and `make docs-check`: clean.
- `portal-frontend` rebuilt and restarted.
- Headless Firefox (Playwright, signed in as an admin; the items and every approval call were stubbed in the browser, so nothing was approved):
  - A workflow's confirm step: project picker, FHIR hint, Approve disabled until a project is picked.
  - Its progress ("Uploading the build", with the bar) and its outcome.
  - A staged measurement's confirm step at 360px.
  - One fix came out of it: the title still asked "Approve <name>?" after the approval had run. It now follows the phase ("Approving <name>" while it runs, then the name).
