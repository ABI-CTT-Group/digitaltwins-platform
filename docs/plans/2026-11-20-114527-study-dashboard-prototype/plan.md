# Plan: Study dashboard (prototype)

## Context
The UI-only ISA sandbox is wired into the real study dashboard (`/study-dashboard`) through shared
production code. `composables/useDashboardData.ts:8-10, 96, 107-110` adds the sandbox programme and reads
its children from the browser store. `views/dashboard/DashboardView.vue:14-15, 41-42, 68-73, 89` swaps
`LevelGrid` for `StudyDesign` at a sandbox study. These hooks are already on `main` (PR #396). They break
the UI-only boundary and add to PR #401's Merge Danger.

Goal: a separate page, **Study dashboard (prototype)**, that shows only the ISA projects in the browser
store and looks like the real dashboard. The real dashboard goes back to production-only code.

## Settled decisions (grilling)
| # | Decision |
|---|---|
| Q1 | Page name "Study dashboard (prototype)" (the root crumb label) |
| Q2 | Shows every ISA project in the store: the Test Project example and uploads |
| Q3 | Full Programme → Project → Investigation → Study path, one programme card at the root |
| Q4 | Sandbox removed entirely from `/study-dashboard` |
| Q5 | Programme card renamed "Study design sandbox" → **"ISA projects"** (same as the hub title) |
| Q6 | Route `/study-dashboard-prototype`, name `StudyDashboardPrototype`, admin only |
| Q7 | Entry points: hub's Open button + a home page card "Study dashboard (prototype)" next to the real "Study dashboard" card (admin). Revised after the first build: not a catalogue card |
| Q8 | Reuse the one-line prototype note (as on the hub and worklists); no new banner |

Defaults (not asked): branch `prototype`. The internal id `isa-sandbox` and the `sandbox*` function names
stay as they are (not user-facing). `StudyDesign` and the Test Project's real launches don't change.
Visual design reuses the portal's existing dashboard look (frontend-design: the point is to mirror the
real page). No ADR: a routine, easily reversed move. Commit only on explicit ask.

## Approach: compose existing parts, don't copy the dashboard
Reused unchanged: `DashboardHeader`, `LevelGrid` (`views/dashboard/components/`), `StudyDesign`,
`useDashboardNavigation` (it rewrites `?trail=` on the current route, so it works at any path),
`BREADCRUMB_ORDER`, `sandboxProgramme`, `sandboxChildren`, `parseSandboxId` (`views/isa-project/sandbox.ts`),
`useIsaProjectStore().ensureExamples()`.

### Steps (TDD: failing test first each time)
1. **Plan folder**: create `docs/plans/<YYYY-MM-DD-HHMMSS>-study-dashboard-prototype/` with `plan.md`
   (this plan) and `tasks.md` (one box per step; tick each box as soon as its check passes).
2. **Trail resolver in `sandbox.ts`**: add `resolveSandboxTrail(trail, entries)` → `{ items, breadcrumbs,
   currentCategory }`. Root = `[sandboxProgramme()]`. Walk with `sandboxChildren`, stopping at an id it
   can't find (like `loadTrail`). Rename the programme to "ISA projects".
   → test: `views/isa-project/__tests__/sandbox.spec.ts` (name, full walk, stale trail truncation).
3. **New view `views/isa-project/StudyDashboardPrototype.vue`** (~60 lines): `DashboardHeader`
   (`root-label="Study dashboard (prototype)"`), the one-line note "Prototype: ISA projects are kept in
   this browser only.", `StudyDesign` when the trail ends at a study, otherwise `LevelGrid`. Fixes a stale
   URL with `nav.goToDepth` like `DashboardView`. Never calls the API or `loadAssayList`.
   → test: `views/isa-project/__tests__/StudyDashboardPrototype.spec.ts` (move the sandbox case out of
   `DashboardView.spec.ts`: study trail → `StudyDesign` props; root → one "ISA projects" card; no API calls).
4. **Route** in `router/index.ts`: `/study-dashboard-prototype`, `StudyDashboardPrototype`,
   `meta: { requiresAuth: true, requiresRoles: ['admin'] }`, with a "Frontend-only prototype" comment
   like the others.
5. **Entry points**: `IsaProjectHub.vue:138` pushes `StudyDashboardPrototype`, and the hub subtitle names
   the new page. Update the catalogue's ISA project card description.
   → test: `IsaProjectHub.spec.ts:61` expectation.
5b. **Home card (revision)**: no catalogue card for the page. Add "Study dashboard (prototype)" to
   `views/home/home.cards.ts` right after "Study dashboard" (same image, `requireRoles: ['admin']`,
   route `StudyDashboardPrototype`).
   → test: `views/home/__tests__/home.cards.spec.ts`.
6. **Remove the sandbox from the real dashboard**: delete the sandbox import and branches in
   `useDashboardData.ts` and `DashboardView.vue`. Drop the sandbox tests from `useDashboardData.spec.ts`
   and `DashboardView.spec.ts`, keeping the real-study tests (an admin now sees only API programmes).
7. **Docs** (domain-modeling: the glossary is updated as part of the change):
   - `docs/glossary.md` "ISA project (prototype)": they now appear in "Study dashboard (prototype)" at
     `/study-dashboard-prototype` under the "ISA projects" programme; the real study dashboard doesn't
     show them.
   - `docs/codemap.md:321-322` and `services/portal/README.md:142`: same wording change.
8. **Rebuild** `portal-frontend` only: `docker compose up -d --build portal-frontend` (named service,
   not a blanket up).

## Verification
- `make test-frontend`, then `make lint`, then `make docs-check` (after `git add` of new files).
- `grep -rn "isa-project\|sandbox" services/portal/frontend/src/views/dashboard services/portal/frontend/src/composables`
  returns nothing outside tests.
- After the rebuild, sign in as admin (headless Firefox screenshots):
  `/study-dashboard` shows no "ISA projects" card. `/study-dashboard-prototype` shows the prototype note
  and one "ISA projects" card; drilling to Test Study shows the study design. The hub's Open and the home page
  card both land there; the catalogue has no Study dashboard card. Uploading an ISA project in the hub makes it appear in the new page.
- Afterwards: offer to update PR #401's Merge Danger (an outward action, so ask first).
