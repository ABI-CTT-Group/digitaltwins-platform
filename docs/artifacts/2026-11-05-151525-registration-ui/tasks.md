# Tasks: improve the dataset registration UI

Plan: [plan.md](plan.md). Four PRs, merged in order. PR1: `feat/registration-ui-shell` (#387, merged).

## PR1: shared look, hub states, delete confirmations, Tools role
- [x] Baseline: `make test-frontend` (186), `make lint` clean
- [x] Failing specs: `RegistryView.spec.ts` (5 red: loading, error + retry, empty slot, no matches, poll failure banner)
- [x] Specs: `ConfirmDialog.spec.ts` (written with the component, not red first); `cards.spec.ts` (3 red: Delete emits the item, no API call, card not greyed out)
- [x] Failing spec: `catalogue_routes.spec.ts` (each hub's roles; Tools red)
- [x] Fonts: `@fontsource-variable/hanken-grotesk`, `@fontsource-variable/fraunces` `^5.3.0` in `main.ts`; `yarn.lock` (npmjs.org); Google `@import`s removed (6 files); font stacks now `var(--font-ui)` / `var(--font-title)`
- [x] Tokens on `:root` in `styles/style.css` (removed from the catalogue landing); `.aurora-btn` is the one button style, no hover lift, visible focus
- [x] `CardUI.vue` / `NoData.vue`: `--font-ui`, sentence-case kind label, no lift, constant accent edge; `isDeleting` prop removed
- [x] `HubShell.vue` in the four hub `index.vue` files; titles and subtitles rewritten
- [x] `RegistryView.vue`: loading / error / ready, empty and no-match states, poll-failure notice; `Search.vue` and `Refresh.vue` folded in and deleted
- [x] `ConfirmDialog.vue` + `useConfirm.ts`; delete and cancel-upload confirm in all hubs; delete calls moved from cards to hubs
- [x] Router: Tools admin-only
- [x] Green: `make test-frontend` (199), `make lint`, `make docs-check`
- [x] Rebuild and restart `portal-frontend`; bundle serves its own fonts
- [x] Browser walk-through: headless Firefox screenshots of the four hubs, phone width and the delete confirmation; fixed register-button accent and clipped filter label
- [x] Walkthrough (`walkthrough-pr1.md`); sync artifacts; gitleaks dir scan (no leaks)

## PR2: status line, next step, vocabulary, filter
Branch: `feat/registration-ui-status`.
- [x] Builder: `has_annotation` on tool/workflow rows; deploy `error` on deploy rows; `build_error` / `deploy_error` on gui-tools (`test_hub_status_fields.py`, 5 red first)
- [x] Failing specs: `cardStatus.spec.ts` (one case per table row), `hubFilter.spec.ts`, `StatusLine.spec.ts`, `HubFilterChips.spec.ts`, `cards.spec.ts` rewritten, `RegistryView.spec.ts` (sort), hub loaders keep `buildError` / `deployError` (25 red)
- [x] `cardStatus.ts`, `hubFilter.ts` (+ `useHubFilter`), `StatusLine.vue`, `HubFilterChips.vue`; `RegistryView` `sortFn`
- [x] Cards render status line + one action; chips for type, version and problems only; menus renamed; measurement approve without annotation
- [x] Hubs: filter chips, Needs-you-first sort, Retry FHIR for tools and workflows; legacy non-SDS workflow approval no longer offered
- [x] Remove `cardTags.ts`, `cardTags.spec.ts`, `formatDate` (+ spec); `registration_filter.spec.ts` → `hub_filter_views.spec.ts`
- [x] ADR `2026-11-06-card-status-sentence` (supersedes 2026-10-12-card-tag-vocabulary); glossary: Approval, FHIR annotation; portal README ADR link
- [x] Green: `make test-builder` (259 passed, 12 skipped), `make test-frontend` (219), `make lint`, `make docs-check`
- [x] Rebuild and restart `builder`, `portal-frontend`; headless Firefox screenshots (real hubs, stubbed workflow states, 360px); fixed status-line alignment and the long "from workflow" chip
- [x] Walkthrough (`walkthrough-pr2.md`); sync artifacts; gitleaks dir scan
- Deviations from the plan, to pick up in PR3: a never-built tool offers **Build** (the Rebuild flow) instead of Continue registration; a never-built workflow offers nothing yet. "Add/Edit FHIR annotation" for tools and workflows waits for the wizard routes.

## PR3: wizard routes, resume drafts, inline errors, optional FHIR step
Branch: `feat/registration-ui-wizard`. Picks up PR2's deviations (Build → Continue registration; never-built workflows; Add/Edit FHIR annotation for tools and workflows).
- [x] Builder: saving a workflow's annotation again updates it in place, like a tool's (`test_hub_status_fields.py`, red first)
- [x] `registrationSteps.ts` `nextStep` / `registerRoute` / `hubRoute` + spec; cards: Continue registration replaces Build; Add/Edit FHIR annotation for tools and SDS workflows before approval
- [x] Routes: each hub `index.vue` is a layout; children `''`, `new`, `:id/register?step=`; roles on the parent (`catalogue_routes.spec.ts`)
- [x] One tool and workflow wizard, `RegisterWizard.vue` (replaces `UploadToolForm`, `UploadWorkflowForm`, `BaseCompleteStep`): `new` creates once then `router.replace`s to `:id/register?step=annotation`; step 1 a read-only summary there; steps not clickable (`RegisterWizard.spec.ts`)
- [x] Async `submit` props on `BaseInformationStep` / `BaseAnnotateStep` / `BaseBuildStep`; API errors inline (`apiError.ts` `describeApiError`, shared `.step-error`)
- [x] SDS-only workflow check in `BaseInformationStep`; `follow-up: non-SDS workflows` markers on the non-SDS paths
- [x] Optional FHIR step: "FHIR annotation (optional)" + Skip for now (tool, workflow, measurement; model renamed); a saved tool or SDS workflow annotation is filled in on edit
- [x] Leave guard (`useLeaveGuard`: route leave + `beforeunload`) while step 1 has input or an upload runs
- [x] Token prompt on resume (git sources) via `RebuildAuthDialog` (new `title` / `note` / `verb` props); step 1's token kept in tab memory only (`pendingAuth.ts`)
- [x] Measurements and models: `new` / `:id/register?step=upload|annotation` routes (`dataset_wizards.spec.ts`)
- [x] `WizardFrame.vue`: the three wizards' shared frame, with "Step n of m" on phones (found by the 360px screenshot)
- [x] ADR `2026-11-06-sds-only-workflow-registration`; card-status ADR consequence updated; portal README user guide
- [x] Green: `make test` (api 407, builder 260, frontend 267, util 5), `make lint`, `make docs-check`
- [x] Rebuild and restart `builder`, `portal-frontend`; headless Firefox walk-through (stubbed items): Continue registration → annotation → Skip → build, token prompt, leave guard (dismiss stays, accept leaves), 360px
- [x] Walkthrough (`walkthrough-pr3.md`); sync artifacts; gitleaks dir scan
- TDD slips: the measurement step's Skip button and `WizardFrame` have no spec of their own (the wizard specs stub them).

## PR4: one Approve dialog
Branch: `feat/registration-ui-approve`.
- [x] `approveAdapters.ts` (+ spec): tools and SDS workflows (handoff; always `fhir: true`; SEEK project; FHIR push followed), measurements and models (upload session); one progress shape; the FHIR hint per category
- [x] `ApproveDialog.vue` (+ spec, ToolApprovalDialog cases moved): confirm → progress → done or failed; closable mid-way; waiting for sign-in; start error inline; title follows the phase
- [x] Hubs and cards use it (the tool card's Approve emits the row); removed `ToolApprovalDialog.vue` (+ spec), `measurements/components/ApprovalDialog.vue`, `SubmitProgress.vue`, the Models hub's inline dialog
- [x] One FHIR rule (reviewer's request, reverses D7): tools and workflows send `fhir: hasAnnotation`, so an unannotated item of any category isn't published to FHIR; hints and specs updated (spec and code changed together, not red first)
- [x] ADR `2026-11-06-optional-fhir-annotation`; glossary "FHIR annotation"; portal README ADR link
- [x] Green: `make test` (api 407, builder 260, frontend 286, util 5), `make lint`, `make docs-check`
- [x] Rebuild and restart `portal-frontend`; headless Firefox with stubbed approval calls: workflow confirm (project picker, FHIR hint) → progress → done; measurement confirm at 360px
- [x] Walkthrough (`walkthrough-pr4.md`); sync artifacts; gitleaks dir scan
