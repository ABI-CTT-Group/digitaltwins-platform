# Plan: Demo prep (no "prototype" on screen, one study dashboard)

## Context
An important demo runs on the demo host (`nectar-test_demo`, now on `prototype` e5c0a9ad). The audience must
not see the word "prototype", and the demo shows only one study dashboard: the prototype one (ISA projects).
After the demo the user may come back to integrate the prototypes, so code comments keep saying
"prototype"; only on-screen text changes.

## What branch `prototype` has prototyped (21 commits ahead of main; all frontend-only)
| Area | Pages | What it does |
|---|---|---|
| ISA projects | `/catalogue/isa-project` (hub, admin) | Upload an ISA project (JSON or bundle folder/.zip), list, download, approve dialog; kept in localStorage |
| Study design | `/study-dashboard-prototype` (admin) | Study dashboard for the browser's ISA projects: Programme "ISA projects" → project → investigation → study → StudyDesign (List / Flow views, assay panel). The Test Project example is **linked**: Launch/Submit/Monitor/Verify/Download run the real platform assays |
| Clinician dashboard | `/clinician-dashboard`, `/clinician-dashboard/studies/:id` | Study list → per-study worklist with example cases, slice preview, confirm / send back; kept in localStorage |
| Workflow assembler | catalogue tile | "Prototype" badge only (badge already on main) |

## Settled decisions (grilling)
| # | Decision |
|---|---|
| Q1 | One dashboard = the prototype page. The real "Study dashboard" card leaves the home page |
| Q2 | URL swap: `/study-dashboard` opens the prototype page; the real dashboard moves to unlisted `/study-dashboard-platform`; old `/study-dashboard-prototype` redirects to `/study-dashboard` |
| Q3 | Remove the caveat notes (dashboard, hub, unlinked study design, both clinician pages, approve dialog). Keep the linked-study note (no "prototype" in it) |
| Q4 | Drop the catalogue "Prototype" badges and reword the ISA tile; reword the click messages; reword the bundle placeholder text |
| Q5 | Changes go on `prototype` itself (no demo branch); the reopened PR carries them |
| Q6 | Page and home card stay admin-only |
| Q7 | The single home card reuses the real card's title and description ("Study dashboard", "Enables clinicians to collaborate…"); only its route and roles change |
| Q8 | Commit only; ask before pushing or deploying to the demo host |

Defaults (not asked): route names stay (`StudyDashboard` = real, `StudyDashboardPrototype` = ISA page),
they're not visible. Code comments keep "prototype". Tiles with `requireRoles: []` already show a bare lock
(e.g. the first catalogue card); Workflow assembler will match them once its badge goes. No ADR (easily
reversed, demo-driven). For the reopened PR's Merge Danger: the URL swap and the hidden real dashboard must
be reverted before anything merges to main.

## Steps (TDD: update/add the failing test first each time)
1. **Plan folder** `docs/plans/2026-11-20-<HHMMSS>-demo-without-prototype-wording/` with `plan.md` and
   `tasks.md` (one box per step, ticked as each check passes; sync after each doc change).
2. **Routes** (`router/index.ts`): `StudyDashboardPrototype` at `/study-dashboard` (admin);
   `StudyDashboard` at `/study-dashboard-platform` (roles unchanged); redirect `/study-dashboard-prototype`
   → `{ name: "StudyDashboardPrototype" }` (like the `/worklists` redirect).
   → test: `router/__tests__/study_dashboard_prototype_routes.spec.ts`.
3. **Home** (`views/home/home.cards.ts`): one card "Study dashboard" with the real card's location and
   description, `requireRoles: ['admin']`, route `StudyDashboardPrototype`; the "(prototype)" card goes.
   → test: `views/home/__tests__/home.cards.spec.ts` (one study dashboard card; no title/description matches /prototype/i).
4. **Catalogue** (`views/catalogue/catalogue-dashboard-view.vue`): remove `prototype: true` from both tiles,
   and the now-unused `prototype` field and its badge branch; ISA tile text "Open one in the study dashboard…".
   → test: `catalogue-dashboard-view.spec.ts` (no "Prototype" text; ISA tile shows the admin lock).
5. **Page text**, no "prototype" on screen:
   - `StudyDashboardPrototype.vue`: root label "Study dashboard"; remove the note.
   - `IsaProjectHub.vue`: subtitle "…open it in the study dashboard…"; remove the note.
   - `StudyDesign.vue`: remove the unlinked note; message → "`${action}` isn't available for this assay yet."
   - `components/IsaApproveDialog.vue`: remove the hint.
   - `worklists/StudyListView.vue`, `worklists/WorklistsView.vue`: remove the notes; toast → "The annotator
     isn't connected yet."
   - `adapter/isaBundleWriter.ts`: `PLACEHOLDER` → "Placeholder: replace it with the real one."
   - Remove CSS and imports these removals orphan (`.note`, `.proto`, etc.) only if nothing else uses them.
   → tests: the matching specs (`StudyDashboardPrototype`, `IsaProjectHub`, `StudyDesign`, `IsaApproveDialog`,
   `StudyListView`, `WorklistsView`, `isaBundleWriter`) assert the new text and `not.toMatch(/prototype/i)`.
6. **Docs**: `docs/glossary.md` (ISA project row), `docs/codemap.md:~323`, `services/portal/README.md:142`:
   the ISA page is "Study dashboard" at `/study-dashboard`, the only one on the home page; the real dashboard
   is at `/study-dashboard-platform`, not linked. The README's end-user guide (step 1, `/study-dashboard`)
   stays as is; it describes the real dashboard on main.
7. **Rebuild** `portal-frontend` locally: `docker compose up -d --build portal-frontend` (named service only).

## Verification
- `make test-frontend`, `make lint`, `make docs-check` (after `git add` of the new plan files).
- `grep -rniE "prototype" services/portal/frontend/src --include=*.vue` shows only comments (no template text);
  also check `.ts` strings shown to users (home cards, catalogue, toasts, bundle text).
- Headless Firefox as admin: home shows one "Study dashboard" card → `/study-dashboard` with root crumb
  "Study dashboard" and the "ISA projects" programme; drill to Test Study; Monitor on an unlinked assay shows
  the new message; catalogue tiles have no "Prototype" badge; ISA hub and both clinician pages have no notes;
  `/study-dashboard-prototype` redirects; `/study-dashboard-platform` still shows the real dashboard.
- Commit (Conventional Commits, plans in the same commit set). Then ask before pushing and before updating
  the demo host.
