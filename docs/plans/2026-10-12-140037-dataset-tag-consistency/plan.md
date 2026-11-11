# Plan: consistent card tags across the dataset hubs

## Context

The four portal hubs (Measurements, Models, Tools, Workflows) use different words for the same states, and each hub hides some state that another hub shows. "completed" on a tool means *build finished*, while on a measurement it means *in platform*. The model card says "registered" and "awaiting approval" where the measurement card says "completed" and "pending". FHIR progress is folded into the status chip, so a FHIR push reads as "uploading…" or "registering…" even though the files are already stored. (Brief: `docs/artifacts/2026-10-12-140037-dataset-tag-consistency/brief.md`.)

**Goal:** a user can read any card in any hub with the same few rules, and the same word always means the same thing.

## Decisions (from the interview)

| Question | Decision |
|---|---|
| Scope | All 4 hubs |
| Word for "not yet submitted" | `draft` |
| Unfinished chunked upload | `upload paused`. On the hub it has always stopped: leaving the wizard calls `uploader.stop()` (`measurements/steps/InformationStep.vue:331`) |
| Approved and being stored | `registering…` |
| "platform upload" chip | **Dropped**: REST/CLI uploads show `in platform` like everything else |
| FHIR | **No FHIR chip.** A FHIR failure turns `in platform` amber, with the reason in the tooltip |
| Re-approval failed while already in platform | Also amber `in platform`, with the reason in the tooltip |
| Failure detail | **Tooltip** (`title`) on the chip. The "stage ·" chip and the model card's inline failure text are removed |
| Build chip | **Always shown** on portal-built tools and workflows, including `build · completed` |
| Hub filters | Keep "Registration status: In platform / Not in platform"; **add it to the Models hub** |

## Tag design

**Rules for users:**
1. **The first chip is always the registration state**, in one of five words.
2. **Other state chips read `<what> · <state>`**: `build · …` (new) and `deploy · …` (existing).
3. **Colour:** grey = waiting for you, cyan = running, green = done, red = failed, amber = done but something needs attention. **Hover a red or amber chip to see why.**

| Chip | Values | Cards | Shown when |
|---|---|---|---|
| **Registration** | `upload paused` · `draft` · `registering…` · `registration failed` · `in platform` | all 4 | always |
| **Build** | `build · pending` · `build · building` · `build · completed` · `build · failed` (raw values, matching the card's "Building" button and the log console) | tools, workflows | the item has a portal build (not `platformOnly`) |
| **Deploy** (unchanged) | `deploy · …` | GUI tools with a backend | as today |
| **Type** | `gui` · `script` · `notebook` | tools, workflows | the type is known (tools: `label`; workflows: `workflowType`) |
| Descriptive (unchanged) | `from workflow X`, version, author | as today | as today |
| Date (unchanged) | date, right-aligned | all 4 | as today |

**Fixed chip order on every card:** Registration → build → deploy → type → descriptive → date. Today tools put version and author first.

**Type chip:** workflows keep their existing `workflowType` chip (`script` / `notebook` / `gui`). Tools get the same chip, from `label` (`GUI` → `gui`, `Script` → `script`, `Notebook` → `notebook`), including REST-uploaded tools and a gui workflow's tool. Both hubs render it through one `typeTag()` helper, so the words always match. The tool card's eyebrow ("Web GUI Tool" / "Script" / "Notebook") and accent colour are unchanged. Legacy workflows with no type show no type chip, as today.

### What each Registration value means

| Value | Colour | Meaning | Hubs | What the user can do |
|---|---|---|---|---|
| `upload paused` | grey #9fb4bf | The chunked upload stopped partway (the user left the wizard or closed the tab). Some files are staged; nothing is in the platform. | measurements, models | Resume upload / Cancel upload |
| `draft` | grey #9fb4bf | All files are staged (measurement/model) or built in the portal (tool/workflow), but not yet submitted. | all 4 | Edit, then Approve / Submit to approval |
| `registering…` | cyan #5fd6e8 | Approved; the platform is storing it now: files to MinIO, dataset record (and SEEK for tools/workflows). | all 4 | Wait; actions are disabled |
| `registration failed` | red #ff6b6b | Storing it failed; nothing new reached the platform. The tooltip gives the reason. | all 4 | Approve / Submit again, or delete |
| `in platform` | green #6fd49a | Stored in the platform. A FHIR push may still be running in the background (actions are disabled while it runs, as today). | all 4 | Use it, delete |
| `in platform` | amber #ffb74d | Stored, but FHIR publishing failed, or a later re-approval failed. The tooltip says which, and why. | all 4 | Retry FHIR (menu or approval dialog) / Submit again |

### Does it cover what users need to know?

| User question | Answered by |
|---|---|
| Where is my item in the lifecycle? | Registration chip |
| Can I submit it for approval? | Tool/workflow: `draft` + `build · completed`. Model: `draft`. Measurement: `draft`, with the Approval menu item present only once it is annotated (as today) |
| Is something running? | `registering…`, `build · pending/building`, `deploy · deploying` |
| Did something go wrong, and why? | A red or amber chip, plus its tooltip; build failures via "View logs" as today |
| Can I launch it? | `build · completed` (+ `deploy · completed` for GUI tools with a backend); the Launch button is disabled otherwise, as today |
| What kind of tool/workflow is it? | Type chip (`gui` / `script` / `notebook`) |
| Which version, who, when? | Descriptive chips + date |

**Not shown on the card:**
- whether an item has been published to FHIR, or has FHIR details saved (you chose no FHIR chip; tool/workflow FHIR status stays visible in the approval dialog);
- whether a deployed backend is actually running, which is still checked when Launch is clicked.

### Mapping today's chips to the new ones

| Today | After |
|---|---|
| Tools/workflows: unlabelled `pending` / `building` / `completed` / `failed` (the build) | `build · pending` / `build · building` / `build · completed` / `build · failed` (same values and colours, with a prefix) |
| Tools/workflows: `approving…` / `approval failed` | `registering…` / `registration failed` (tooltip: `handoffError`) |
| Tools/workflows: `platform upload` / `in platform` | `in platform` |
| Measurements: `uploading source…` · `pending` · `uploading…` · `submit failed` · `completed` · `FHIR failed` + `in platform` + `stage · …` | `upload paused` · `draft` · `registering…` (or green `in platform` during a FHIR push) · `registration failed` · `in platform` · amber `in platform` |
| Models: `uploading source…` · `awaiting approval` · `registering…` · `registration failed` · `registered` · `FHIR failed` + `in platform` + `FHIR` | the same as measurements; the `FHIR` chip is removed |

### How each hub derives the chips

- **Measurements and models**, from `MeasurementResponse.status` and `uuid`:
  - `pending_upload` → `upload paused`
  - `pending` → `draft`
  - `uploading` without a uuid → `registering…`
  - `submit_failed` → `registration failed` (tooltip: `failureMessage`)
  - with a uuid: `fhir_failed` → amber `in platform` (tooltip: "FHIR publishing failed: <failureMessage>"); anything else → green `in platform`
- **Tools and workflows**, from `handoffStatus`, `uuid`, `platformOnly` and the platform dataset's `fhirStatus`. Precedence:
  1. `uploading` / `awaiting_reauth` / `committing` → `registering…`
  2. a real uuid (not a `sparc-tool-`/`sparc-workflow-` placeholder) or `platformOnly` → `in platform`. It is amber if `fhirStatus === 'failed'` (tooltip: FHIR failure) or `handoffStatus === 'failed'` (tooltip: "Re-approval failed: <handoffError>").
  3. `handoffStatus === 'failed'` → `registration failed` (tooltip: `handoffError`)
  4. otherwise → `draft`. A legacy placeholder uuid counts as `draft`, which matches today's "Not in platform" filter.

## Implementation

All paths are under `services/portal/frontend/src/`.

1. **New `views/upload-dataset/components/cardTags.ts`**: pure functions returning `{ label, color, title? } | null`: `measurementRegistrationTag(m)`, `handoffRegistrationTag(item, placeholderPrefix)`, `buildTag(status)` and `typeTag(type)` (case-insensitive `gui` / `script` / `notebook`, else null). This is the single source of the labels and colours.
2. **Data** (only what the amber FHIR-failure rule needs on tools and workflows):
   - `models/types.ts`: add `handoffError?`, `fhirStatus?` and `fhirFailureMessage?` to `ToolResponse` and `WorkflowResponse`.
   - `bootstrap/tool_api.ts`:
     - `useWorkflowTools` enrich: add `handoffError: latestBuild.handoffError`.
     - `useToolHub`: the `/datasets?categories=tools` call already made by `usePlatformTools` also attaches `fhirStatus` and `fhirFailureMessage` to known tools by uuid, with no second request.
   - `bootstrap/workflow_api.ts` and `bootstrap/platform_api.ts`: the same for workflows. Confirm that `/datasets` rows carry `fhir_status` for the `workflows` category.
   - `bootstrap/measurement_api.ts`: no change; `status` already carries `fhir_failed`.
3. **Cards**: each `#meta` slot renders the Registration chip, the build chip, the deploy chip (tools only), the type chip (tools and workflows), the descriptive chips and the date, in that order, as `aurora-chip` spans with `:title`. Menus, Launch logic, polling and the Retry FHIR button stay unchanged.
   - `measurements/components/MeasurementCard.vue`: drop `statusLabel`, `statusColor`, the "stage ·" chip and the separate "in platform" chip.
   - `models/components/ModelCard.vue`: drop the label and colour maps, the `FHIR` chip and the `#action` failure text.
   - `components/ToolCard.vue` and `components/WorkflowCard.vue`: the unlabelled status chip becomes `buildTag(status)`; the approving, approval-failed, "platform upload" and "in platform" chips become the Registration chip. Move version and author after the state chips.
4. **Filter**: `models/ModelsOverallView.vue` gets the same `registrationFilter` select as `measurements/MeasurementsOverallView.vue:12-26,95-107`, copied pattern, keyed on `!!m.uuid`.

## Tests (TDD: write them first, see them fail, then implement)

- **New `components/__tests__/cardTags.spec.ts`**: a table of inputs to label, colour and tooltip for every derivation above, including:
  - the legacy placeholder → `draft`
  - FHIR failed → amber `in platform` with a FHIR tooltip
  - re-approval failed → amber `in platform` with a re-approval tooltip
  - a FHIR push in progress on a measurement → green `in platform`
  - `platformOnly` → no build chip
  - `typeTag`: `GUI` / `Script` / `Notebook` / `gui` / `script` / `notebook` → lowercase chip; unknown or empty → no chip
- Card tests check that a tool and a workflow of each type (portal and REST-uploaded) show the type chip.
- **`components/__tests__/cards.spec.ts`**:
  - Update the existing tag tests: "shows where it came from" now expects `in platform`, not `platform upload`, and "tags a workflow approved into the platform".
  - Add chip and order checks for ToolCard and WorkflowCard.
  - Add new `MeasurementCard` and `ModelCard` blocks.
- **`components/__tests__/tool_hub.spec.ts`**: `useToolHub` attaches `fhirStatus` to a portal tool. Add the equivalent for `useWorkflowHub`.
- **`components/__tests__/registration_filter.spec.ts`**: add a Models hub case.

## Docs and traceability

- **ADR `docs/decisions/2026-10-12-card-tag-vocabulary.md`**:
  - *Decision:* one Registration chip with five shared values, plus `<what> · <state>` chips for build and deploy; no FHIR chip, with FHIR failure shown as amber `in platform`; shared vocabulary in `cardTags.ts`.
  - *Rejected:*
    - a single merged status chip, which causes today's confusion;
    - a separate FHIR chip, judged not worth the extra chip;
    - a "ready to register" state, which ties build and annotation readiness to registration;
    - `awaiting approval`, which implies someone else acts;
    - `uploading…` for a stopped upload;
    - keeping `platform upload`, which can't be detected for measurements and models.
  - *Consequence:* FHIR publish success is not visible on cards.
- Sync this plan to `docs/artifacts/2026-10-12-140037-dataset-tag-consistency/plan.md` right after approval. Add `task.md` and `walkthrough.md` there while working. Use repo-relative paths only and no secrets.
- No commits unless asked.

## Verification

1. Vitest in a throwaway container: `docker run --rm -v $PWD/services/portal/frontend:/fe -w /fe node:20 npx vitest run`. All tests pass.
2. Type-check the touched files with vue-tsc 2.2.10 + TS 5.9.3 in a throwaway container (the pinned vue-tsc 1.8 can't run). The known `RegistryView` slot-typing error is expected.
3. Rebuild the frontend: `docker compose up -d --build --no-deps portal-frontend`.
4. Check in the browser at http://localhost/catalogue-dashboard:
   - a paused upload shows `upload paused`
   - a staged measurement shows `draft`
   - a committed model shows `in platform`
   - a built, unsubmitted tool shows `draft` + `build · completed` + its type chip
   - a script, a notebook and a gui tool and workflow each show their type chip
   - an approved tool shows `in platform` + `build · completed`
   - a REST-uploaded workflow shows `in platform` with no build chip
   - a FHIR-failed measurement shows amber `in platform`, and its tooltip gives the reason
   - the Models hub filter splits correctly
   - chip order is the same on all four hubs
