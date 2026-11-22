# Study dashboard: a clinician view and a researcher view, chosen by role

## Context

The demo has two prototype dashboards, each with its own home card and route:
- **`/study-dashboard`** (`StudyDashboardPrototype.vue`) drills down through the ISA projects:
  programmes, then projects, investigations and studies. It is admin only.
- **`/clinician-dashboard`** (`worklists/StudyListView.vue`) lists the studies to review. Each one
  opens a worklist at `/clinician-dashboard/studies/:id`.

The user wants one study dashboard whose content depends on who signs in:
- A clinician sees today's clinician dashboard.
- A researcher sees today's study dashboard.
- An admin sees both.

The demo uses only the admin account, so the admin needs a way to switch between the two views.

UI only: both dashboards stay frontend prototypes on browser data. Shared production components
(`DashboardHeader`, `LevelGrid`, `AuthNavBar`, the auth store) don't change.

## Decisions (from the questions)

- **Switch:** a segmented control, "View as: Clinician | Researcher". It is not a toggle switch:
  this is a choice between two equal views, and both names stay visible.
- **Who sees the switch:** anyone who holds both views. Admin counts as both, and so does a user
  with both the researcher and clinician roles.
  - A clinician-only user sees only the clinician view, with no switch.
  - A researcher-only user sees only the researcher view, with no switch.
- **Which view opens:**
  1. A `?view=clinician|researcher` in the URL wins, if the user may see that view.
  2. Otherwise, a `?trail=` means the researcher view. This keeps the ISA projects page's "Open in
     study dashboard" links correct.
  3. Otherwise, the last view chosen in this browser.
  4. Otherwise, the researcher view.
- **Where the switch is:** at the top of both views, at every drill-down level, but not on a
  worklist. Choosing a view opens that view's top level, so a researcher trail is dropped.
- **Entry:** one home card, "Study dashboard", and the "Clinician dashboard" card goes.
  `/clinician-dashboard` redirects to `/study-dashboard?view=clinician`.
- **Worklist URL:** it moves to `/study-dashboard/reviews/:studyId`.
  - The old `/clinician-dashboard/studies/:studyId` redirects there.
  - `/worklists` redirects to the clinician view.
  - "All studies" goes back to `/study-dashboard?view=clinician`.
- **Naming:** the clinician view's heading becomes "Study dashboard". Its lede stays "Choose a study
  to review its cases.". The nav bar says "Study Dashboard" on the dashboard and the worklist.

## Model

New folder `services/portal/frontend/src/views/study-dashboard/`:

- **`dashboardView.ts`:**
  - `type DashboardView = "clinician" | "researcher"`.
  - `viewsFor({ admin, researcher, clinician })` returns `DashboardView[]`, clinician first to
    match the switch. Admin gives both.
  - `chooseView(views, { asked, hasTrail, stored })` follows the order in the decisions above.
  - `useStudyDashboardView()` reads the auth store (`hasAdminRole`, `hasResearcherRole`,
    `hasClinicianRole`), the route query and `localStorage["study-dashboard-view"]`. Every storage
    access is wrapped in try/catch.
    - It returns `{ views, view, choose(v) }`.
    - `choose` stores `v` and does `router.push({ name: "StudyDashboardPrototype", query: { view: v } })`,
      which drops the trail and keeps browser back working.
  - `useDashboardNavigation` already spreads `route.query`, so `?view` survives drilling down.
- **`StudyDashboardPage.vue`:** the `/study-dashboard` route component. It renders `StudyListView`
  for the clinician view and `StudyDashboardPrototype` for the researcher view.
- **`ViewAsSwitch.vue`:** presentational, with props `views` and `modelValue`; it emits
  `update:modelValue`.
  - Renders nothing when `views.length < 2`.
  - Otherwise it is a `<fieldset>` with a "View as" legend and two radio inputs styled as segments
    (`[data-test=view-as]`, `[data-test=view-as-clinician|researcher]`).
  - Native radios give arrow-key movement and screen-reader state for free.
  - `StudyDashboardPrototype.vue` and `StudyListView.vue` each get an empty `<slot name="toolbar" />`
    at the top of their content, and `StudyDashboardPage` fills it with the switch. The views stay
    free of router and auth code, so their own specs don't change, and both are prototype files.
    (Changed during the build: the first draft put `<ViewAsSwitch />` straight into each view.)

## Routes (`router/index.ts`)

- `/study-dashboard`:
  - It keeps the name `StudyDashboardPrototype`, so the ISA projects page's links keep working.
  - Its component becomes `StudyDashboardPage`.
  - `requiresRoles` becomes `['admin', 'researcher', 'clinician']`.
- `/study-dashboard/reviews/:studyId`:
  - Named `ClinicianStudyWorklist`, the same name as before, and still uses `WorklistsView` with
    `props: true`.
  - `requiresRoles` is `['admin', 'clinician']`, since the clinician view is not a researcher's.
- Redirects:
  - `/clinician-dashboard` and `/worklists` go to `{ name: "StudyDashboardPrototype", query: { view: "clinician" } }`.
  - `/clinician-dashboard/studies/:studyId` goes to the new worklist path.
- The `ClinicianDashboard` route name goes. Its users were `WorklistsView`'s back links,
  `layouts/Default.vue` and `home.cards.ts`.

## Design

The switch sits quietly in the dashboard's existing aurora look (`--font-ui`, `--text`,
`--text-faint`, the hub accent and line tokens), with nothing new to draw the eye.

```
                                        View as  ┌───────────┬────────────┐
                                                 │ Clinician │ Researcher │
                                                 └───────────┴────────────┘
Study dashboard › Programmes (2)                         ← researcher view header (unchanged)
```

- **Position:** a right-aligned row above each view's header, in the same spot in both views, so it
  doesn't move when the view changes. Below 600px it is left-aligned and the segments share the
  full width.
- **Track:** a 36px pill with a 1px line border and a faint fill.
- **Chosen segment:** filled with the accent at low alpha, in accent text at weight 600. The other
  segment is in `--text-faint`, and its text brightens on hover.
- **Labels:** sentence case and no icons. "View as" is in `--text-faint`.
- **Focus:** a visible `:focus-visible` ring on the chosen segment.
- **Motion:** only a 150ms background change on the segments, with none under
  `prefers-reduced-motion`.

## Steps (TDD)

Plan folder: `docs/plans/<YYYY-MM-DD-HHMMSS>-study-dashboard-views/`, holding `plan.md` and
`tasks.md`. Tick each task as its check passes, and sync after every doc edit.

1. **Red:**
   - **`study-dashboard/__tests__/dashboardView.spec.ts`:**
     - `viewsFor` for each role mix: admin, researcher only, clinician only, researcher and
       clinician, and none.
     - `chooseView`: `?view` wins; a `?view` for a view the user lacks is ignored; a trail means
       researcher; a stored view is used; the fallback is researcher; a clinician-only user always
       gets clinician.
   - **`study-dashboard/__tests__/StudyDashboardPage.spec.ts`**, mounted with a router and a mocked
     auth store:
     - A clinician sees the study list and no switch.
     - A researcher sees the programmes and no switch.
     - An admin sees the switch, with Researcher chosen on the first visit.
     - Choosing Clinician shows the study list, sets `?view=clinician` and stores the choice.
     - A later visit opens Clinician.
     - `?trail=` opens Researcher.
   - **`router/__tests__/worklists_routes.spec.ts`**, rewritten:
     - The new paths, the role lists and the three redirects.
     - `/study-dashboard` resolves to `StudyDashboardPage`.
   - **`WorklistsView.spec.ts` and `StudyListView.spec.ts`:**
     - The back link targets `/study-dashboard?view=clinician`.
     - Rows link to `/study-dashboard/reviews/<id>`.
     - The heading is "Study dashboard".
   - **Home cards:** a test, or extending an existing one: one "Study dashboard" card for the three
     roles and no "Clinician dashboard" card.

   → verify: `make test-frontend` fails on exactly these tests.
2. **Green:**
   - `dashboardView.ts`, `ViewAsSwitch.vue` and `StudyDashboardPage.vue`.
   - The routes.
   - Add the `toolbar` slot to both views.
   - `StudyListView`: its heading becomes "Study dashboard".
   - `WorklistsView`: its back links go to `{ name: "StudyDashboardPrototype", query: { view: "clinician" } }`.
   - `home.cards.ts`: drop the Clinician dashboard card and widen the Study dashboard card's roles.
   - `layouts/Default.vue`: title "Study Dashboard" for `StudyDashboardPrototype` and
     `ClinicianStudyWorklist`.

   → verify: `make test-frontend` and `make lint` pass.
3. **Docs:**
   - **`docs/glossary.md`:**
     - New row "Study dashboard view (prototype)" defining the two views and who sees which.
     - The "Worklist (prototype)" row uses the new URLs.
     - The "ISA project (prototype)" row says the projects appear in the researcher view.
   - **`services/portal/README.md` and `docs/codemap.md`:** the `worklists` and `isa-project` lines,
     plus the new `study-dashboard` folder.

   → verify: `make docs-check` passes.
4. **Rebuild** and restart `portal-frontend` only.

   → verify with headless Firefox as admin, at 1440px and 390px:
   - The first visit shows the Researcher view with the switch.
   - Choosing Clinician shows the study list, and a reload keeps Clinician.
   - Opening a worklist works, and "All studies" returns to the clinician view.
   - Drilling into a programme keeps the switch.
   - The ISA projects page's study link opens the researcher view at that study.
   - `/clinician-dashboard` redirects.

   Critique the screenshots and fix anything wrong before reporting. The clinician-only and
   researcher-only paths are covered by the unit tests, since the demo has only the admin account.

## Added during the build

- **Mock-up note (asked mid-build):** the clinician view's study list shows a note: "Mock-up. This
  view runs on example cases kept in this browser, and review decisions aren't sent to the
  platform." It has a dashed edge, like a sketch.
  - On review it was made neutral, dropping amber: on these pages amber already means "to review" and
    "needs correction". The note became one `worklists/components/MockupNote.vue` (`role="note"`),
    also shown on each worklist under its lede, since that is where review decisions are made and
    links can land there directly.
  - On a copy review its text became "Mock-up. The cases and scans are examples, not real patients,
    and your decisions stay in this browser.", written from the reader's side and covering the
    drawn scan image.
  - The review panel's image is a drawing, so its caption "Slice N / M" became "Illustration, not a
    scan", and its screen-reader label became "Illustration of the annotation on <case>, not a
    scan". The slice count still shows in the Scan row. "Open in annotator" stays as it is: it
    already says it isn't connected when clicked.
  - This reverses the earlier "no prototype wording" rule for this view only. The study rows still
    never say it.
  - The researcher view gets no note, since its assays really run.
- **Nav bar title:** `layouts/Default.vue` passes a title that `AuthNavBar` doesn't show. Its
  mapping was updated only so it no longer names the removed `ClinicianDashboard` route; no title
  appears on screen.

## Not in this plan

- Changing Keycloak roles or users, the auth store, or the platform's own dashboard at
  `/study-dashboard-platform`.
- Committing, pushing or deploying to the demo host: each needs a separate request.

## Critical files

- `services/portal/frontend/src/views/study-dashboard/` (new): `dashboardView.ts`,
  `StudyDashboardPage.vue`, `ViewAsSwitch.vue` and their tests
- `services/portal/frontend/src/router/index.ts`, `router/__tests__/worklists_routes.spec.ts`
- `services/portal/frontend/src/views/isa-project/StudyDashboardPrototype.vue`
- `services/portal/frontend/src/views/worklists/StudyListView.vue`, `WorklistsView.vue` and their
  specs
- `services/portal/frontend/src/views/home/home.cards.ts`, `layouts/Default.vue`
- `docs/glossary.md`, `docs/codemap.md`, `services/portal/README.md`
- Reused: `store/auth_store.ts` (`hasAdminRole`, `hasResearcherRole`, `hasClinicianRole`) and
  `composables/useDashboardNavigation.ts` (it keeps other query keys)
