# Improve the dataset registration UI

## Context

The four catalogue hubs (`/catalogue/{tools,workflows,measurements,models}`) and their "Register a new …" wizards
(`services/portal/frontend/src/views/upload-dataset/`) are hard to read and hard to use:
- **State is unclear.** Tool and workflow cards carry up to 8 chips (`build · completed`, `deploy · completed`, …);
  measurement and model cards carry 2; no card says what to do next.
- **Registering is confusing.** The wizard replaces the hub in place (no URL; Back leaves the page). A closed tool or
  workflow wizard can't be reopened. Re-submitting step 1 creates a duplicate tool. Failed API calls in the tool and
  workflow wizards show nothing.
- **The hubs are inconsistent.** There are three approval UIs and three names for approving. Delete asks for
  confirmation in some hubs only. No hub has a loading or error state. Three button styles.
- **The look is generic and dated.** The hubs use Nunito and hard-coded hex while the rest of the portal uses Hanken
  Grotesk + Fraunces. The Notebook accent is the warning amber. Fonts load from Google at runtime, which breaks airgapped installs.

Who uses it: researchers register measurements and models; admins register everything and run admin actions;
clinicians register nothing.

## Decisions (from the grilling session)

| # | Decision |
|---|---|
| D1 | Clarity first, light restyle on the existing Vue 3 + Vuetify stack. |
| D2 | Every card shows **one status sentence + one next-step button**; chips only for facts (type, version) and problems. State tables below. |
| D3 | One verb: **Approve** ("Approve", "Approve <name>?", "Approving…", "In the platform"). |
| D4 | Wizards on their own routes; leave guard; draft cards get "Continue registration"; step 1 can't be re-submitted; every API error shown inline. |
| D5 | The portal's look: Hanken Grotesk (UI) + Fraunces (page titles only), shared CSS variables, self-hosted fonts, one button style. |
| D6 | FHIR annotation is optional for every dataset: a skippable wizard step, and Add/Edit later from the card menu. |
| D7 | One Approve dialog for all four: confirm, then live progress; closable. **Approving always publishes whatever FHIR the dataset has**, so the dialog has no FHIR checkbox. An unannotated dataset gets one hint line: "No FHIR annotation, so nothing is published to FHIR. You can add one later." |
| D8 | Hub filter: All / Needs you / In progress / In the platform; "Needs you" items sort first. Real loading, error and empty states. Delete always asks for confirmation. The Tools route becomes admin-only. |
| D9 | Colour rule "quiet when fine, loud when not": steady states uncoloured, running pale, needs-you amber, failed coral. The category accent appears only on the card edge and kind label. |
| D10 | Non-SDS workflows are not supported for now: the wizard rejects them at step 1. Their code paths stay, unreachable, for later. |
| D11 | Four PRs, merged in order; "SDS dataset" in user-facing copy. |

### Card state tables (D2)

Tools and workflows (portal-built):

| State | Sentence | Button |
|---|---|---|
| created, never built (`!latestBuildId`) | Not built yet | Continue registration |
| building | Building… | View logs |
| build failed | Build failed (reason on hover) | View logs |
| built | Built — not in the platform yet | Approve |
| approving | Approving… (stage text) | — |
| approval waiting for sign-in | Approving… waiting for you to sign in again | — |
| approval failed | Approval failed (reason) | Approve again |
| in platform | In the platform | Launch (GUI tool); Deploy DAG (script workflow, admin, not deployed) |
| in platform, newer build not approved | In the platform — a newer build isn't approved yet | Approve |
| in platform, re-approval failed | In the platform + coral "re-approval failed" chip | Approve again |
| in platform, FHIR failed | In the platform — FHIR publishing failed | Retry FHIR |
| GUI tool backend failed | In the platform + coral "backend failed" chip (reason) | Launch (retries) |
| uploaded via API (`platformOnly`) | In the platform | — (menu: Delete) |
| legacy non-SDS workflow | Not an SDS package — not supported yet | — (menu: Delete) |

Measurements and models:

| State | Sentence | Button |
|---|---|---|
| upload paused | Upload paused | Resume upload |
| staged (annotation optional) | Ready to approve | Approve |
| approving | Approving… | — |
| approval failed | Approval failed (reason) | Approve again |
| in platform | In the platform | — |
| in platform, FHIR failed | In the platform — FHIR publishing failed | Retry FHIR |

The filter groups are: *Needs you* = failed, ready to approve, upload paused, not built, waiting for sign-in. *In progress* = building, approving. *In the platform* = everything in the platform without a problem.

## Design system (D5, D9)

**Colour**: tokens on `:root` in `src/styles/style.css`, moved from `.catalogue` in `views/catalogue/catalogue-dashboard-view.vue:209`:
| Token | Value | Use |
|---|---|---|
| `--ink` | #07131b | panels, dialogs |
| `--text` / `--text-dim` / `--text-faint` | #e9f2f5 / #a4bac4 / #5f7884 | body, secondary, hints |
| `--line` | rgba(120,200,220,.14) | borders, dividers |
| `--tone-needs` | #ffb74d | status that needs you |
| `--tone-failed` | #ff7a6b | failures (moved off #ff6b6b, so it doesn't read as the old error red) |
| `--accent-{tools,workflows,measurements,models}` | #5fd6e8 / #7fb2f0 / #62d3b0 / #b08fe8 | card edge, kind label, hub register button |

Running uses `--text` with a slow shimmer on the mark (none under `prefers-reduced-motion`). Steady states use a filled mark in `--text-dim`.

**Type**: Hanken Grotesk 400/500/600/700 for all UI; Fraunces 500 for the hub title only. Scale (×1.2): 0.75 · 0.875 · 1 · 1.2 · 1.44rem, title `clamp(2.2rem, 5vw, 3.4rem)`. Tabular numerals for versions and dates. Sentence case everywhere: the uppercase eyebrow on cards goes.

**Layout**:
```
Hub (left-aligned, max 1120px, like the catalogue landing)
  ← Catalogue
  Tools                                   (Fraunces)
  Register and build tools that assays can run.
  [ Register a tool ]   All · Needs you 3 · In progress · In the platform    [ search… ]
  ┌ card ┐ ┌ card ┐ ┌ card ┐   grid auto-fill minmax(300px,1fr)

Card
  Web GUI tool                                   …     (kind label in accent, sentence case)
  Lesion ground-truth curator
  Curate lesion masks for MRI series.                  (2 lines max)
  ▲ Built — not in the platform yet                   (status line: the one bold element)
    Approve it so assays can use it.
  gui  v1.2                                [ Approve ]

Wizard (/catalogue/tools/new, /catalogue/tools/:id/register)
  ┌ steps ──────────┐  ┌ step content, max 72ch ─────────────────┐
  │ ✓ Source        │  │ …                                        │
  │ ● FHIR annot.   │  │ inline error ▲ Couldn't save: <detail>   │
  │ ○ Build         │  │                  [ Skip for now ] [ Save ]│
  └─────────────────┘  └──────────────────────────────────────────┘
  (mobile: "Step 2 of 3 · FHIR annotation" above the content)
```

**Principles**: the status line is the one bold element on a card, and everything around it stays quiet: no card shadows, no hover lift, radius 12px on cards and 8px on controls. No middle-dot meta strings or ALL-CAPS labels. Motion only for running states and dialog progress. Visible keyboard focus, reduced motion respected, usable at 360px wide.

**Review against generic defaults**: the obvious default here is the SaaS card kit (identical rounded cards, soft shadows, a chip row). This plan avoids it by dropping shadows and the lift, making the status line carry the hierarchy, and showing colour only on the cards that need someone. There's no new palette; it builds on the portal's existing ink and aqua so these screens match the catalogue landing.

## Implementation (TDD: failing specs first in each step)

### PR1: shared look, hub states, delete confirmations, Tools role
- **Fonts:** add `@fontsource-variable/hanken-grotesk` and `@fontsource-variable/fraunces`, import them in `src/main.ts`, and update `yarn.lock`. Remove the Google `@import`s from `Hero.vue`, `HomeHero.vue`, `DashboardView.vue`, `catalogue-dashboard-view.vue`, `AssayReportView.vue` and `tutorial/index.vue`.
- **Tokens:** add the tokens above to `styles/style.css`. `.aurora-btn` stays as the only button style. Drop the register button's own style in `RegistryView.vue` and the tonal `v-btn` in `ModelsOverallView.vue`.
- **Card restyle:** `CardUI.vue` and `NoData.vue` use `--font-ui`. Remove the uppercase eyebrow, shadows and hover lift.
- **Hub shell:** new `components/HubShell.vue` (BackLink, title, one-line purpose), used by the four hub `index.vue` files. Rewrite the hero copy (the Workflows one says "tools").
- **`RegistryView.vue`:**
  - states `loading | error | ready`, with a skeleton while loading
  - an error panel with Retry
  - a per-hub `#empty` slot ("No models yet. Register one to use it in assays.")
  - "No matches" when search or filter hides everything
  - a quiet banner when a poll fails
- **Delete confirmations:** new `components/ConfirmDialog.vue`. Every delete and cancel-upload asks first. The calls move from the cards to the hubs (`ToolCard.vue`, `WorkflowCard.vue`, `MeasurementsOverallView.vue`).
- **Roles:** `router/index.ts` makes the Tools route `requiresRoles: ['admin']`.
- **Specs:** `RegistryView.spec.ts` (loading, error, retry, empty, no matches, poll failure), `ConfirmDialog.spec.ts`, `cards.spec.ts` (Delete emits a request), and `catalogue_routes.spec.ts` (a researcher can't reach Tools).

### PR2: status line, next step, vocabulary, filter
- **Builder (small, first):**
  - `has_annotation` on the tool and workflow list rows (`services/builder/app/router/workflow_tool_plugin.py` `get_plugins`, `workflow_router.py` list; `PluginResponse`, `WorkflowResponse`)
  - the deploy `error` on `PluginDeployResponse` and `/workflow/gui-tools` (`db_model.py:326` has a field, `error_messages`, that matches no column)
  - builder tests for both
- **New `components/cardStatus.ts` (pure):** `toolStatus`, `workflowStatus`, `datasetStatus` each return `{sentence, reason?, tone, group, action?, problems[]}`, implementing the tables above. The in-platform checks and the `HANDOFF_ACTIVE` list move here. It works when the new builder fields are missing.
- **New `components/hubFilter.ts`, `StatusLine.vue`, `HubFilterChips.vue`.**
- **Card changes:** `CardUI.vue` gets a `#status` slot. The four cards render the status line and the single action; chips are kept for facts and problems only. `ToolCard.vue` drops the per-type accent; the type becomes a chip. The measurement card lets you approve without an annotation.
- **Menus:** "Approve", "Add FHIR annotation" / "Edit FHIR annotation", "Stop backend", "View logs", "Delete …".
- **Hubs:** the four OverallViews use `HubFilterChips` and the Needs-you-first sort.
- **Build errors:** `tool_api.ts` and `workflow_api.ts` keep the latest build's error messages for "Build failed" reasons.
- **Removals:** delete `cardTags.ts`, `cardTags.spec.ts` and `registration_filter.spec.ts` once their replacements pass.
- **Specs:** `cardStatus.spec.ts` (one case per table row), `hubFilter.spec.ts`, and `cards.spec.ts` updates.

### PR3: wizard routes, resume drafts, inline errors, optional FHIR step
- **Routes:**
  - each hub `index.vue` becomes a layout (HubShell + `<router-view>`, plus `LogConsole` for tools)
  - child routes: `''` (the hub), `new`, and `:id/register?step=annotation|build`
  - the existing measurement preview route stays
  - roles stay on the parent route
- **No re-submitting step 1:** after create, `router.replace` to `:id/register?step=annotation`. There, step 1 is a read-only summary, and `editable` comes off the stepper (`UploadToolForm.vue:8`).
- **Continue registration:** new pure `components/registrationSteps.ts` `nextStep(row)` picks the step: annotation if never built, else build; a paused upload resumes. The card emits `continue` and the hub pushes the route. Edit FHIR annotation uses `?step=annotation`.
- **Inline errors:** the step components (`BaseInformationStep`, `BaseAnnotateStep`, `BaseBuildStep`, `InformationStep`, `AnnotationStep`) take an async `submit` prop, await it, and show failures inline. New `components/apiError.ts` `describeApiError` replaces the hubs' `detail()` helpers.
- **SDS-only workflows:** `BaseInformationStep.validate()` rejects a non-SDS workflow source: "This folder isn't an SDS package (no dataset_description.xlsx). Only SDS workflow packages can be registered for now." Mark the non-SDS code paths `// follow-up: non-SDS workflows` (`BaseAnnotateStep.vue` non-SDS branch, builder `GET /workflow/{id}/approval`).
- **Optional FHIR step:** the tool, workflow and measurement wizards get "FHIR annotation (optional)" with "Skip for now". `ModelFhirStep` is already optional; rename it to match.
- **Leave guard:** `onBeforeRouteLeave` + `beforeunload` while step 1 has unsaved input or an upload is running.
- **Private git repos on resume:** the annotation and build steps ask for a token through `RebuildAuthDialog.vue`, as Rebuild does today.
- **Specs:** `registrationSteps.spec.ts`, `catalogue_routes.spec.ts` (new routes, roles), `BaseInformationStep.spec.ts` (an API error shown inline; non-SDS blocked), `BaseAnnotateStep.spec.ts` (Skip saves nothing and moves on), a new `UploadToolForm.spec.ts` (`useCreateTool` called once; step 1 read-only on `:id/register`), and a leave-guard spec.

### PR4: one Approve dialog
- **New `components/approve/ApproveDialog.vue`:** confirm → progress → done or failed; closable, with the card continuing to poll. Fields: a SEEK project for tools and workflows, plus the FHIR hint line when there's no annotation.
- **New `components/approve/approveAdapters.ts`, one adapter per category:**
  - tools: `useToolApproval` / `useToolApprovalStatus`
  - SDS workflows: `useWorkflowPlatformApproval` / its status call
  - measurements and models: `useMeasurementSubmit` / `useGetMeasurement`
  - tools and workflows always send `fhir: true`, the API default (`ApprovalRequest` in `workflow_tool_plugin.py`)
- **Reuse:** the SEEK project picker and retry logic come from `ToolApprovalDialog.vue`; the stage mapping comes from `measurements/components/SubmitProgress.vue`.
- **Removals:** delete `ToolApprovalDialog.vue`, `measurements/components/ApprovalDialog.vue`, `SubmitProgress.vue`, and the inline dialog in `ModelsOverallView.vue`.
- **Editing FHIR after approval:** for tools and workflows, offer Edit FHIR annotation only before approval until a re-push is confirmed to work. Measurements and models already re-push with Retry FHIR.
- **Specs:** `ApproveDialog.spec.ts` (fields per category, progress to done and to failed, close without cancelling, waiting for sign-in) and `approveAdapters.spec.ts`. Move the `ToolApprovalDialog.spec.ts` cases into them.

### Docs (with the PR each belongs to)
- Glossary: add **Approval** (committing a registered dataset to the platform; whoever approves is the one who clicks) and **FHIR annotation** (optional; says which FHIR resource each port or file becomes) (PR2).
- New ADRs:
  - `card-status-sentence` (PR2), superseding `2026-10-12-card-tag-vocabulary.md`
  - `sds-only-workflow-registration` (PR3), superseding the root-`.cwl` path of the workflow wizard
  - `optional-fhir-annotation` (PR2/PR4: approval doesn't need an annotation, and it publishes whatever FHIR the dataset has)
- `services/portal/README.md` and `docs/codemap.md` if new folders appear (`components/approve/`).
- Artifacts: sync this plan plus a `tasks.md` to `docs/artifacts/<ts>-registration-ui/` first; one walkthrough per PR.

## Risks and follow-ups
- Merge order PR1 → PR2 → PR3 → PR4. PR2 and PR3 both touch the cards' emits and the OverallViews, and PR4 uses PR2's action IDs.
- Adding the font packages needs one online `make frontend-deps`. Nunito is still loaded by `bootstrap/webfontloader.ts` for other screens (follow-up for airgapped installs).
- Follow-ups: non-SDS workflows (D10); the ionicons scripts loaded from unpkg in `index.html` (airgap); `element-plus` as a second component library.

## Verification
- Each PR: `make test-frontend`, `make lint`, `make docs-check`; PR2 also `make test-builder`. Run `make test` + `make lint` before opening each PR.
- Live: rebuild and restart `portal-frontend` (and `builder` for PR2):
  - walk each hub as admin and as researcher: loading, empty, error, filter, every card state that exists in the data
  - register a tool and a measurement end to end, close the wizard midway and continue from the card, skip the FHIR step, and approve with live progress
  - check at 360px and with keyboard only
- A browser click-through by the user before each merge.
