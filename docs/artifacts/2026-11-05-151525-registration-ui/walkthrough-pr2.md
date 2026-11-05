# Walkthrough: PR2, status line, next step, vocabulary, filter

Plan: [plan.md](plan.md). Tasks: [tasks.md](tasks.md). ADR: [card status sentence](../../decisions/2026-11-06-card-status-sentence.md).

## What changed
- **Builder fields.** Tool and workflow list rows carry `has_annotation`. `/tools/plugin/build/{id}/deploys` returns the deploy's `error`: the response model named it `error_messages`, which matches no column, so it was always empty. `/workflow/gui-tools` rows carry `build_error` (the latest build's error messages) and `deploy_error`.
- **One status sentence per card.** `components/cardStatus.ts` turns a tool, workflow, measurement or model into `{sentence, reason, hint, tone, group, action, problems}`, following the plan's state tables. `StatusLine.vue` shows it with a mark coloured by tone: steady uncoloured, running pale and pulsing (static under reduced motion), needs-you amber, failed coral. A failure's reason sits under the sentence, clamped to two lines, and in full on hover.
- **One next-step button.** Each card renders the status's action as its only button: Build, View logs, Approve, Approve again, Launch, Deploy DAG, Retry FHIR, Resume upload. The menu holds the rest: Launch (when it isn't the button), Rebuild, Stop backend, View logs, Add/Edit FHIR annotation, Preview fhir.json, Export annotation, Deploy DAG again, Cancel upload, Delete.
- **Chips are facts and problems.** Type, version and "from <workflow>" stay. Registration, build and deploy chips, author and date are gone (`formatDate` went with them). A problem on an item that otherwise works is a coral chip with its reason as the title: "backend failed", "re-approval failed", "rebuild failed", "DAG deploy failed".
- **Tool cards** drop the per-type accent: kind "Tool", type as a chip.
- **Approving without an annotation.** A staged measurement shows Approve whether or not it has an annotation. The platform's commit job pushes FHIR only when there are descriptions.
- **Non-SDS workflows** read "Not an SDS package — not supported yet" and offer only Delete. The legacy `useWorkflowApproval` call stays in `workflow_api.ts`, marked `follow-up: non-SDS workflows`; the hub no longer calls it.
- **Hub filter.** `HubFilterChips.vue` (All · Needs you *n* · In progress · In the platform) replaces each hub's "Registration status" select. `hubFilter.ts` groups by the status's `group`. `useHubFilter` gives each hub its filter, its counts from the last list, and a Needs-you-first sort through the new `RegistryView` `sortFn` prop.
- **Retry FHIR** is now on tool and workflow cards (`POST /api/datasets/{uuid}/fhir/push`), as well as measurements and models.

## Deviations from the plan
- A never-built tool offers **Build** (the existing Rebuild flow), not "Continue registration": the wizard can't be reopened for an existing tool until PR3's routes exist. A never-built workflow shows "Not built yet" with no button for the same reason.
- Add/Edit FHIR annotation for tools and workflows also waits for PR3 (`?step=annotation`).
- Three states were added to the tables for an item already in the platform: "In the platform — rebuilding…", a "rebuild failed" chip, and "In the platform — deploying the DAG…".

## Verification
- `make test-builder`: 259 passed, 12 skipped. The 5 new cases in `test_hub_status_fields.py` failed first.
- `make test-frontend`: 219 passed. The new and rewritten specs (`cardStatus`, `hubFilter`, `StatusLine`, `HubFilterChips`, `cards`, `hub_filter_views`, the `RegistryView` sort and the hub loaders) were red first. `cardTags.spec.ts` and `formatDate.spec.ts` were removed with their code.
- `make lint` and `make docs-check`: clean.
- `builder` and `portal-frontend` rebuilt and restarted.
- Headless Firefox (Playwright, signed in as an admin) captured the four hubs with real data, all in the platform. The Workflows hub was also captured with stubbed list responses covering built, build failed, approving, approval failed, FHIR failed, DAG failed, in the platform and non-SDS, at 1360px and 360px. Two layout bugs were found and fixed: status lines didn't line up across a row when descriptions had different lengths, and a long "from <workflow>" chip wrapped onto two lines.
