# Worklists page (frontend prototype) replaces the clinician dashboard

## Context

Clinicians need a page that, once they open the project they work on, lists the cases they have to go
through. In a retrospective study, the job on each case is to check its annotation and either confirm it
or send it back for correction. A UI-only prototype was agreed as a standalone HTML page
(artifact `5vgpGJrik3bbGTGDDmH5rP`, version 2). This change rebuilds that page in the portal as
**Worklists** and puts it where the clinician dashboard is today.

There is no backend for cases or review decisions, and this change adds none. Like the ISA project
sandbox, it is a **frontend-only prototype** on example cases kept in the browser.

## Decisions settled in grilling (2026-11-13)

| Question | Decision |
|---|---|
| Scope | Frontend only. Example cases from a fixture; nothing reaches an API |
| Old page | New route `/worklists`. `/clinician-dashboard` redirects to it. The home card becomes "Worklists" |
| Term for what is checked | **Annotation** (the clinicians' word). The glossary keeps it apart from *FHIR annotation* |
| Landing after sign-in | Unchanged: everyone lands on the home page |
| Clinician-mode code in `DashboardView` | Left as is (`isClinicianView` and the "Auckland hospital" filter stay; they are unused once the route redirects) |
| Persistence | Decisions kept in this browser's localStorage, as the ISA sandbox store does |
| "Open in annotator" | Shows a message only; nothing is launched |
| Readers | One decision per case, shared by the project. "Reviewed by" shows who decided |

Defaults taken without asking (say if any is wrong):
- **Who can open it:** the same roles as the clinician dashboard today (`admin`, `researcher`, `clinician`).
- **Project picker:** shows the one example project from the fixture.
- **Where the work happens:** a new branch `feat/worklists-prototype` from `origin/main`, in a git worktree, so
  the uncommitted ISA sandbox work on `prototype` stays where it is.
- **No ADR:** a reversible, browser-only prototype with no real trade-off. The backend design will
  need one later.

## Page (as agreed in artifact v2)

- **Header:** a project switch ("Breast MRI lesion ground truth"), a "Your worklist" heading and a
  short description. The portal's own nav bar (`AuthNavBar`) replaces the artifact's fake top bar. One
  line states that this is a prototype with example cases and that decisions stay in this browser.
- **Progress row:** "14 of 36 cases reviewed", plus **Review next [10] cases** (a number input,
  default 10, capped at the number still to review) with a Start button and "N left to review".
- **Case list:** tabs for To review, Needs correction, Confirmed and All (with counts), and a search
  box. Columns are Case, Scan ("DCE-MRI"), Annotated by, Updated and Status. There is no laterality and
  no lesions column.
- **Review panel** (right, stacks on top on narrow screens): the case ID, its status pill, "Case 3 of 10
  in this batch" while a batch runs, its details (scan and slices, annotated by, reviewed by), and any
  correction note. Buttons: Open in annotator, Confirm annotation, Needs correction. Needs correction
  asks for a note before Send for correction. There is no scan image.
- **Behaviour:** Start takes the first N cases still to review. Each decision moves to the next case
  in the batch, and the last one shows "Batch finished: N cases reviewed". Choosing a case by hand
  leaves the batch.
- **Look:** the portal's tokens from `styles/style.css` (`--font-ui`, `--font-title`, `--text*`,
  `--line`, `--surface`, `--tone-needs`, `--accent-measurements` for confirmed), and the shared
  `.aurora-btn` buttons (with `--accent` set per button) instead of the artifact's `.btn`.

## Files

New, in `services/portal/frontend/src/views/worklists/`:
- `model/worklist.ts`: pure functions with the types `Case` and `ReviewStatus`
  (`review | needs | confirmed`): `counts`, `startBatch(cases, n)`, `decide(state, status, note)`
  (advances the batch or moves to the next case to review) and `filterCases(cases, tab, query)`.
- `fixtures/example-cases.json`: the 36 example cases from the artifact (sub-001 to sub-036, with
  the same preset statuses and correction notes).
- `worklistStore.ts`: a Pinia store seeded from the fixture. It persists decisions to localStorage
  with try/catch, following `views/isa-project/isaProjectStore.ts`.
- `WorklistsView.vue`: the page, with its header, progress row and batch form.
- `components/CaseTable.vue`: the tabs, search and table.
- `components/CaseReviewPanel.vue`: the case details, the decision buttons and the correction note.
- `__tests__/worklist.spec.ts`, `__tests__/worklistStore.spec.ts`, `__tests__/WorklistsView.spec.ts`.

Changed:
- `router/index.ts`: add the `/worklists` route (`name: "Worklists"`, the same `requiresAuth` and roles,
  with a comment marking it a frontend-only prototype). Replace the `ClinicianDashboard` route with
  `{ path: "/clinician-dashboard", redirect: { name: "Worklists" } }`.
- `views/home/home.cards.ts`: rename the "Clinician dashboard" card to "Worklists", with the action
  `{ name: 'Worklists' }` and the description "Go through your project's cases and confirm each
  annotation, or send it back for correction."
- `layouts/Default.vue`: `dashboardTitle` returns "Worklists" for that route.
- Tests that reference the `ClinicianDashboard` name, if any (check `__tests__` and the router tests).

Docs (same PR):
- `docs/glossary.md`: add **Worklist (prototype)**, **Case**, **Annotation** and **Review decision**.
  Annotation is defined as the marks drawn on a case's images, such as a lesion outline, and is kept
  apart from *FHIR annotation*. The wording is in the "Glossary" section below.
- `docs/codemap.md` and `services/portal/README.md`: add `worklists/` (frontend-only prototype) to the
  views list, and say that `dashboard/` is now the study dashboard only.
- `docs/plans/<YYYY-MM-DD-HHMMSS>-worklists-prototype/`: `plan.md` (this plan), `tasks.md` (a checklist
  ticked as work proceeds) and `walkthrough.md` at the end. Sync after every edit. No secrets and no
  local paths.

## Glossary (draft wording)

- **Worklist (prototype):** the cases of one project that still need a clinician's review decision,
  with progress through them. Shared by everyone on the project: one decision per case. Only a frontend
  prototype exists, on example cases kept in the browser.
- **Case:** one subject of a study, reviewed as a unit on a worklist (for example `sub-012`).
- **Annotation:** the marks drawn on a case's images, such as a lesion outline, by a model or a person.
  Not to be confused with a *FHIR annotation*, which describes a dataset.
- **Review decision:** a clinician's verdict on a case's annotation: **Confirmed**, or **Needs correction**
  with a note saying what to fix. A case with no decision is **To review**.

## Order of work (TDD)

1. Create the branch and worktree, and create the plan folder with `plan.md` and `tasks.md`.
   Verify: the folder exists and `git status` is clean apart from it.
2. Red: write `worklist.spec.ts` covering batch capping, advancing, the batch-finished case, filtering
   and counts. Then green with `model/worklist.ts`. Verify: `make test-frontend` passes.
3. Red: write `worklistStore.spec.ts` (seeded from the fixture, a decision survives a reload, a
   storage error falls back to the fixture). Then green with the store.
4. Red: write `WorklistsView.spec.ts` (the tab counts render, Start 10 selects the first case to
   review and shows "Case 1 of 10", Confirm advances, Needs correction without a note is refused). Then
   green with the view and its components.
5. Change the router, the home card and `Default.vue`, then fix any specs that reference
   `ClinicianDashboard`.
6. Update the docs (glossary, codemap, portal README) and sync the plan folder.

## Verification

- `make test-frontend`, `make lint` (eslint and vue-tsc) and `make docs-check` all pass. Compare lint
  output with `main`.
- Rebuild and restart only the portal: `docker compose up -d --build portal-frontend`.
- Open `http://localhost/worklists` and `http://localhost/clinician-dashboard` (which should redirect)
  and screenshot both with headless Firefox through Playwright, signing in to Keycloak from env vars,
  at desktop and phone widths. Check the following:
  - Start with 10 runs a batch.
  - Confirm and Send for correction update the counts.
  - A reload keeps the decisions.
  - The home page shows the Worklists card.
- No commit until you ask.
