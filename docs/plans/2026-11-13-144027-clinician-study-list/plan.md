# Plan: Clinician dashboard study list (UI-only prototype)

Branch: `prototype` (the same branch; no worktree). Plan folder after approval:
`docs/plans/2026-11-13-144027-clinician-study-list/` (`plan.md`, `tasks.md`, later `walkthrough.md`).

## Context

`/clinician-dashboard` opens straight onto one worklist. Its header has a "Project: Breast MRI lesion ground
truth (example)" switcher that only shows a toast. Clinicians should first see the studies they review, then
open one to reach its worklist. In this prototype there is one study, **Breast MRI reading**, and it uses the
existing 36 example cases.

Decisions made in grilling:
- **A worklist belongs to a study**, not a project. The project switcher goes, and the glossary changes to match.
- **Nested routes.** `/clinician-dashboard` shows the study list, and
  `/clinician-dashboard/studies/breast-mri-reading` shows that study's worklist. `/worklists` still redirects to
  `/clinician-dashboard`.
- **Each row shows** the study name, a one-line purpose, "15 of 36 reviewed" with a thin progress bar,
  "21 to review", and the date of the last decision. All of it is read live from the browser store.
- **Straight to code**, checked with screenshots. No mockup artifact first.
- The list still shows when there is only one study. Opening the study is never automatic.

Scope stays inside `views/worklists/`, the router, `Default.vue`'s title and the docs. No shared production
components change ([[ui-only-prototype-boundary]]). No ADR is needed: this is a routine change with no real
alternatives weighed.

## Design

The list copies the worklist page's look: the same tokens (`--surface`, `--line`, `--text-dim`, `--font-title`,
`--accent-measurements`), the same padding and the same 1200px column, so the two pages read as one place.

```
Clinician dashboard                       (h1, --font-title)
Choose a study to review its cases.       (lede)
Prototype with example cases. ...         (same flask note as the worklist)

┌──────────────────────────────────────────────────────────────┐
│ Breast MRI reading                         21 to review       │  ← the whole row is one RouterLink
│ Check lesion annotations on DCE-MRI scans                     │
│ ▓▓▓▓▓▓▓░░░░░░░░  15 of 36 reviewed     Last decision 13 Nov   │
└──────────────────────────────────────────────────────────────┘
```

- The rows sit in a plain list (`<ul>`), not cards. Each is one link with a visible keyboard focus ring.
  The progress bar is a `<progress>` element, so screen readers get the value.
- On the worklist, the project switcher becomes a back link ("All studies", with `mdi-arrow-left`) plus the
  study name. "Your worklist" and the rest of the page stay as they are.
- An unknown study id shows "There is no study called <id>." with a link back to all studies.

## Changes (TDD: red first for each)

1. **Model** `views/worklists/model/worklist.ts`: add `lastDecision(cases): string | null`, the latest
   `updated` among decided cases. Test it in `__tests__/worklist.spec.ts`.
2. **Fixture and store**
   - `fixtures/example-cases.json`: replace `project` with
     `study: { id: "breast-mri-reading", title: "Breast MRI reading", purpose: "Check lesion annotations on DCE-MRI scans" }`.
   - `worklistStore.ts`: drop `projectTitle` from the persisted state and export the study as a constant
     (`STUDY`), so a stale title in localStorage can't shadow the new one. `cases` and `decide` stay the same.
   - Update `__tests__/worklistStore.spec.ts` (the title assertion).
3. **Study list** `views/worklists/StudyListView.vue` (new), with `__tests__/StudyListView.spec.ts`. The tests
   check: one row named "Breast MRI reading"; "15 of 36 reviewed" and "21 to review"; the link's `to` is
   `{ name: "ClinicianStudyWorklist", params: { studyId: "breast-mri-reading" } }` (using `RouterLinkStub`);
   and a decision made in the store shows in the counts.
4. **Worklist** `WorklistsView.vue`: take a `studyId` prop (the route uses `props: true`). Replace the project
   switcher with the back link and study name, and show the unknown-study message. Update
   `__tests__/WorklistsView.spec.ts`: `render()` passes `studyId` and stubs `RouterLink`. Add tests for the back
   link and for an unknown id.
5. **Router** `router/index.ts`:
   - `ClinicianDashboard` at `/clinician-dashboard` now uses `StudyListView`.
   - Add `ClinicianStudyWorklist` at `/clinician-dashboard/studies/:studyId`, with `WorklistsView`,
     `props: true` and the same `requiresAuth` and roles.
   - Keep the `/worklists` redirect. Extend `router/__tests__/worklists_routes.spec.ts` to cover both routes.
6. **Nav title** `layouts/Default.vue`: `ClinicianStudyWorklist` also shows "Clinician Dashboard".
7. **Docs**
   - `docs/glossary.md`:
     - Worklist: "the cases of one *study*". The dashboard lists the clinician's studies and opens each
       study's worklist.
     - Review decision: "shared by the study".
   - `docs/codemap.md` and `services/portal/README.md`: one-line mentions of the study list.
   - New plan folder; sync it after every plan edit.

The home card's title and its `ClinicianDashboard` target don't change.

## Verification

- `make test-frontend` and `make lint` (lint compared to its state before the change), then `make docs-check`
  after `git add` of the new files.
- Rebuild and restart only the portal frontend: `docker compose up -d --build portal-frontend`.
- Take screenshots with headless Firefox ([[headless-firefox-screenshots]]):
  - the study list at desktop and at phone width;
  - clicking the row opens the worklist;
  - confirming a case and going back to the list updates its counts;
  - browser back works;
  - `/worklists` lands on the list.
- `walkthrough.md` in the plan folder, with no local paths and no local ops.
- Nothing is committed unless you ask. Commits would be atomic: feat (code and tests), then docs.
