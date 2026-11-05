# Tasks: improve the dataset registration UI

Plan: [plan.md](plan.md). Four PRs, merged in order. Branch for PR1: `feat/registration-ui-shell` (stacked on PR #386).

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
- [ ] Builder: `has_annotation` on tool/workflow rows; deploy `error` on deploy rows and gui-tools (tests first)
- [ ] `cardStatus.ts` + `cardStatus.spec.ts` (one case per table row)
- [ ] `hubFilter.ts`, `StatusLine.vue`, `HubFilterChips.vue` (+ specs)
- [ ] Cards render status line + one action; menus renamed; measurement approve without annotation
- [ ] Remove `cardTags.ts` and its specs
- [ ] ADR `card-status-sentence` (supersedes 2026-10-12-card-tag-vocabulary); glossary: Approval, FHIR annotation
- [ ] Green; live check; walkthrough

## PR3: wizard routes, resume drafts, inline errors, optional FHIR step
- [ ] Routes (`new`, `:id/register`), hub `index.vue` as layout
- [ ] `registrationSteps.ts` + Continue registration
- [ ] Async `submit` props, `apiError.ts`, inline errors
- [ ] SDS-only workflow source check; follow-up markers on non-SDS paths
- [ ] Optional FHIR step with Skip; leave guard; token prompt on resume
- [ ] ADR `sds-only-workflow-registration`
- [ ] Green; live check; walkthrough

## PR4: one Approve dialog
- [ ] `ApproveDialog.vue`, `approveAdapters.ts` (+ specs; move ToolApprovalDialog cases)
- [ ] Remove the three old approval UIs
- [ ] ADR `optional-fhir-annotation`
- [ ] Green; live check; walkthrough
