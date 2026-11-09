# Tasks: ISA project prototype (frontend only)

Plan: [plan.md](plan.md). Branch: `feat/isa-project-prototype`.

- [x] Branch from `origin/main`; artifacts folder with `plan.md` and `tasks.md`
- [x] Baseline: `make test-frontend` (286 pass)
- [x] Failing specs: `isaProject.spec.ts` (validation, planned datasets, input options, run order, simulated run, blocked)
- [x] `model/types.ts`, `model/isaProject.ts`; green (16)
- [x] Specs: adapter (examples valid against catalogue, fresh copies, bad JSON and bad schema rejected), written before the adapter; adapter + fixtures; green (22)
- [x] Failing specs: catalogue card + route (3 red); card + route; green
- [x] Failing specs: `AssayPanel` (7), `StudyGraph` (3, vue-flow stubbed); `useIsaProject`, `IsaTree`, `AssayPanel`, `StudyGraph`, `WorkflowToolsDialog`, `IsaProjectView`; green (32 prototype specs); `make lint-frontend` clean
- [x] Glossary (ISA project, Planned dataset), codemap, portal README; `make docs-check` (0 problems)
- [x] Rebuild and restart `portal-frontend`; browser walk-through with screenshots. Fixed: graph had no height (blank); switched to a top-down layout that refits when an input link moves an assay; planned-input chip truncated
- [x] Plan revision 2 approved: (1) a "Study design sandbox" programme in the study dashboard holding each ISA project's whole tree; (2) the catalogue card opens an ISA project upload/list hub. `plan.md` updated

## Revision 2
- [x] Failing specs: `sandbox.spec.ts` (5) and the id-format rule in `isaProject.spec.ts` (1); `sandbox.ts` + id rule; green (38)
- [x] Failing specs: `isaProjectStore.spec.ts` (6: seed once, upload/replace, bad upload, remove/reset, find study, survives reload); `isaProjectStore.ts`; green (44)
- [x] Failing specs: `useDashboardData.spec.ts` (4; 2 red, 2 regression guards); seam in `useDashboardData.ts`; green. `make test-frontend`: 337 pass (286 baseline + 51 new)
- [x] Failing specs: `IsaProjectHub.spec.ts` (6), `StudyDesign.spec.ts` (4), `DashboardView.spec.ts` (2, new); hub + study design; route → hub; `DashboardView` renders `StudyDesign` for sandbox studies; removed `IsaProjectView.vue`, `IsaTree.vue`, `useIsaProject.ts`; `make test-frontend` 349 pass; `make lint-frontend` clean
- [x] Docs: glossary, codemap, portal README, catalogue card copy; `make docs-check` (0 problems)
- [x] Rebuild and restart `portal-frontend`; screenshot walk-through: hub, upload survives reload, dashboard drill-down, study design, simulated runs, real programmes still listed, 0 `/api` requests with sandbox ids. Fixed: workflow dialog step nodes unstyled (styled from `WorkflowToolsDialog`). Researcher view not checked in a browser (no test user); covered by `useDashboardData.spec.ts`
- [x] `make test` (all suites pass; frontend 349), `make lint` (0 errors), `walkthrough.md`, artifacts synced, gitleaks dir scan of artifacts + changed source (no leaks)
- [x] Plan revision 3 approved: one example ("Breast pilot (example)"), List / Flow views of a sandbox study's assays with assay cards, labelled and dashed edges, configuration in a drawer, no loops. `plan.md` updated

## Revision 3
- [x] Sync artifacts to `docs/artifacts/` (plan.md, tasks.md)
- [x] Failing specs: one shipped example that validates; retired examples pruned from the store, uploads kept (7 red); breast-pilot fixture, catalogue, adapter map, pruning; green. Sandbox, panel, hub, dashboard-seam and `DashboardView` specs moved to the breast pilot
- [x] Failing specs: `studyGraph` assay nodes, platform source nodes, grouped labelled edges, planned flag after a run; `simulateAssay` (3 red); green (19)
- [x] Failing specs: `SandboxAssayCard.spec.ts` (5), `StudyGraph.spec.ts` (3: left-to-right, dashed edges, labels, card events); card + graph rewrite; green
- [x] Failing specs: `StudyDesign.spec.ts` (7: List / Flow toggle remembered, cards in the study's order, pencil opens the side panel, Launch runs one assay, unavailable actions, Load study design links to hub); `StudyDesign.vue` (side panel is a right-hand `v-dialog`: the app has no Vuetify layout for a navigation drawer); `make test-frontend` 361 pass; `make lint-frontend` clean
- [x] Rebuild and restart `portal-frontend`; browser walk-through (one project, Flow and List, side panel, planned input, Launch and Simulate, View workflow, phone width, 0 `/api` calls with sandbox ids). Fixed: card buttons unclickable in Flow (vue-flow disables node pointer events without a node-click listener; a click on a card now opens it); cards overlapping and too small (wider spacing, start at a readable zoom from the left); dataset pill edges running behind cards (pills level with their consumer); side panel centred (dialog root justified right); `write_report` step missing from the CWL graph (step named like an output; catalogue spec added); Launch on a run assay now says to Reset
- [x] `make test` (all suites pass; frontend 364), `make lint` (0 errors), `make docs-check` (0 problems); glossary wording for planned datasets; `walkthrough.md` updated
- [x] Sync artifacts to `docs/artifacts/`; gitleaks dir scan of artifacts + `views/isa-project` (no leaks)
- [x] Plan revision 4 approved (from a grilling session): an assay can run many times (assay run); a planned dataset becomes real at Submit; consumers read the latest submitted run; cohort warning for measurements inputs; no "Load study design" button; new Assays description; commit as four atomic commits, no PR. `plan.md` updated

## Revision 4
- [x] Sync artifacts to `docs/artifacts/` (plan.md, tasks.md)
- [x] Failing specs: statuses with run vs submitted, `simulateLaunch`, `simulateSubmit`, `simulateRunStep` submitting each wave, edges planned until submit, `cohortWarnings` (9 red); model (`Sim` state); green (22)
- [x] Failing specs: card statuses, Submit, warning icon; panel warning and "Produced by" after submit; graph passes `submit`; card, graph, panel; green (19)
- [x] Failing specs: `StudyDesign` launch / submit / messages, no "Load study design" button; `StudyDesign.vue`; green (75 sandbox specs); `make lint-frontend` clean
- [x] `describeCategory("Assays")` text with a spec (red, then green); glossary rows (Assay, new Assay run, Planned dataset); `make docs-check` (0 problems)
- [x] Rebuild and restart `portal-frontend`; browser walk-through (Launch keeps edge dashed, Submit turns it solid and readies assay 2, Simulate, cohort warning on card and panel, no upload button, new description, 0 `/api` calls with sandbox ids)
- [x] `make test` (all suites pass; frontend 371), `make lint` (0 errors), `make docs-check` (0 problems); `walkthrough.md` updated
- [x] Sync artifacts to `docs/artifacts/`; gitleaks dir scan of artifacts, `views/isa-project` and the glossary (no leaks)
- [x] Four atomic Conventional Commits on `feat/isa-project-prototype` (no push, no PR): model, fixtures and adapter; dashboard sandbox and store; hub and assay views; docs and artifacts
