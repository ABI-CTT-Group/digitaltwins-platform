# Walkthrough: Worklists prototype

Branch `feat/worklists-prototype`, from `main` at `cda93505`. This is a frontend-only prototype: no API,
builder or database change.

## What changed

- **New page `/worklists`** (`services/portal/frontend/src/views/worklists/`). It shows a project's cases
  for clinicians to review, with one review decision per case:
  - `model/worklist.ts`: pure rules for counts, the tab and search filter, "Review next N cases" (capped
    at the cases still to review) and where review goes after a decision.
  - `worklistStore.ts`: a Pinia store seeded from `fixtures/example-cases.json` (36 example cases, as in
    the agreed artifact prototype). It persists to localStorage with `pinia-plugin-persistedstate`, as
    the ISA sandbox store does.
  - `WorklistsView.vue`: the header with the project switch, progress and the batch form.
    `components/CaseTable.vue`: the tabs, search and table. `components/CaseReviewPanel.vue`: the case
    details, Open in annotator (a message only), Confirm annotation, and Needs correction (which needs a
    note). `components/StatusPill.vue` is shared by the table and the panel.
- **Router:** `Worklists` at `/worklists` keeps the clinician dashboard's roles (`admin`, `researcher`,
  `clinician`), and `/clinician-dashboard` redirects to it. The `ClinicianDashboard` route name is gone.
- **Home card:** "Clinician dashboard" is now "Worklists". `layouts/Default.vue` titles the route
  "Worklists".
- **Docs:** the glossary gains Annotation, Case, Review decision and Worklist (prototype), with
  Annotation kept apart from FHIR annotation. The codemap and the portal README list `worklists/`.

## Differences from the plan

- **Toasts:** the portal's existing toasts (`vue-toastification`) are used instead of the artifact's
  own toast.
- **StatusPill:** added `components/StatusPill.vue`, because the table and the panel show the same pill.
- **Store spec:** there is no storage-error test. `pinia-plugin-persistedstate` handles a failing
  localStorage itself.
- **Router spec:** added `router/__tests__/worklists_routes.spec.ts` (the route, its roles and the
  redirect).
- **Left as is, as decided:** `DashboardView`'s clinician mode (`isClinicianView` and the "Auckland
  hospital" filter) is no longer reachable from any route. The study dashboard still hides that
  programme.

## Verification

- `make test-frontend`: 64 files and 395 tests pass, including 21 new tests.
- `make lint`: passes (ruff, eslint, vue-tsc).
- `make docs-check`: 0 problems.
- `portal-frontend` was rebuilt and restarted on its own. Headless Firefox (Playwright), signed in, at
  1440 px and 400 px wide, showed:
  - `/clinician-dashboard` redirects to `/worklists`.
  - A batch of 3 shows "Case 2 of 3 in this batch" after one Confirm.
  - Needs correction opens the note form.
  - After a reload the progress still reads 16 of 36.
  - On a phone, the review panel stacks above the list.
