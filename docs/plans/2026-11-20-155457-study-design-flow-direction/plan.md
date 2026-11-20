# Study design: title, flow direction toggle, Flow as default

Branch: `prototype` (work here, no new branch). Frontend only, in `services/portal/frontend`.

## Context

On the demo study dashboard (`/study-dashboard`, the assay level of a study such as the breast
pilot):

1. The title "Assays (study design)" should read **"Study design"**.
2. The flow view is always laid out left to right. Users should be able to switch between
   **Top to bottom** and **Left to right**. Top to bottom is the default.
3. **Flow** should be the default view. It already is in code, but each browser remembers its last
   view (`localStorage` key `isa-study-design-view`), so a browser that once picked List keeps
   opening on List.

Decisions (agreed with the user):
- The title changes on both pages that use the shared `DashboardHeader`: `/study-dashboard` and
  `/study-dashboard-platform`. Both already show "Assays (study design)" on this branch. The count
  stays "9 assays".
- The view and the direction are still remembered per browser, under **new storage keys**, so every
  browser (the demo audience's included) opens once on Flow, top to bottom.
- The direction switch is a second segmented control in the toolbar, next to List | Flow, shown only
  in Flow: `[ ↓ Top to bottom | → Left to right ]` (`mdi-arrow-down` / `mdi-arrow-right` with a label).
- Top to bottom: the canvas grows to about 80% of the window height (never below 640px). It opens at
  the first assay, centred horizontally, and the user pans down. Dataset pills sit above the assay
  they feed; assays at the same level (a fork) form one row.

No ADR (easy to reverse, no real trade-off). No glossary change (no new domain term).

## Changes

### 1. Title: `src/views/dashboard/components/DashboardHeader.vue`
- `const title = …` → `"Study design"` for `currentCategory === "Assays"`.
- Update `__tests__/DashboardHeader.spec.ts` (first, so it fails red).

### 2. Direction in the graph: `src/views/isa-project/components/StudyGraph.vue`
- New prop `direction: "TB" | "LR"`.
- Layout: `studyGraph()` already gives every node a `column` (the run order) and a `row` (its
  position inside that level). Keep that, and map it to screen axes by direction:
  - LR (unchanged): x = `column * COLUMN_WIDTH`, y = centred `row * ROW_HEIGHT`.
  - TB: y = `column * 420` (card height plus room for the edge labels),
    x = centred `row * 390` (card width plus a gap).
- Dataset pills: LR keeps today's placement (in the column before the first reader, level with the
  upper half of its card, below the last card in a shared column). In TB a pill sits just above the
  card it feeds (110 above), right of the card's centre (+250) so it stays clear of the label on the
  edge coming in; pills above the same step move along by 240. One small per-direction spacing
  table drives both.
  (Changed during the browser check: the first version put TB pills a whole step above their reader,
  which left a large gap, and the first offsets collided with the edge labels.)
- Handles: `Position.Top`/`Bottom` for TB, `Left`/`Right` for LR (assay target and source,
  source-pill source).
- `place()`: no change needed. It already centres a study that fits and otherwise starts at its
  top-left corner, so TB starts at the top edge.
- Re-place when `direction` changes (it already re-places when node positions change, so this comes
  free through the positions watcher).
- `.graph--tb { height: max(640px, 80vh); }`.
- Update the file-header comment ("left to right") to say both directions.
- `DatasetEdge.vue` needs no change: `getSmoothStepPath` reads the handle positions it is given.

### 3. Toggle + defaults: `src/views/isa-project/StudyDesign.vue`
- `VIEW_KEY` → a new key (e.g. `isa-study-design-view-v2`); default `"flow"`.
- New `direction` ref, key `isa-study-design-direction`, default `"TB"`. Read and write it inside
  try/catch, like `readView`/`setView`.
- Toolbar: a second `.views` segmented control (same styling, `role="group"`,
  `aria-label="Flow direction"`, `aria-pressed`, `data-test="dir-tb"` / `dir-lr`), shown with
  `v-if="view === 'flow'"`.
- Pass `:direction="direction"` to `<StudyGraph>`.

## TDD order

1. Red: tests
   - `DashboardHeader.spec.ts`: h1 is "Study design"; count still "5 assays".
   - `StudyDesign.spec.ts`:
     - opens on Flow with `direction` "TB" when nothing is stored;
     - a stored legacy `isa-study-design-view = "list"` is ignored (Flow shown);
     - clicking Left to right passes "LR" and is remembered after a remount;
     - the direction control is absent in List view.
   - `StudyGraph.spec.ts`:
     - existing left-to-right tests pass `direction: "LR"` and still hold;
     - TB: each producer is above its consumers (y increases), and the fork (visualise and breast
       app) shares one y;
     - TB: the platform dataset read by the first assay sits just above it, over its card;
     - TB: the breast app's platform datasets sit side by side just above it, below the convert card,
       right of the breast app card's centre.
2. Green: changes 1–3.
3. Refactor; `make test-frontend`, `make lint`.

## Plan docs (repo rule)

Create `docs/plans/<YYYY-MM-DD-HHMMSS>-study-design-flow-direction/` with `plan.md` (this plan) and
`tasks.md` (one box per step, ticked as each passes, including "Sync plans to docs/plans/"). Commit
only when the user asks.

## Verification

- `make test-frontend` and `make lint` pass (compare lint with the branch's current state).
- `make docs-check` after `git add` of the plan folder.
- Rebuild and restart only the frontend: `docker compose build portal-frontend && docker compose up -d portal-frontend`
  (no blanket `up -d`).
- Browser (headless Firefox screenshots, Keycloak sign-in from env vars) on
  `/study-dashboard?trail=…:s-breast-pilot`:
  - the title reads "Study design";
  - it opens on Flow, top to bottom, even with the old `isa-study-design-view=list` still in storage;
  - switching to Left to right gives today's layout, and the choice survives a reload;
  - top to bottom: the nine-assay pilot is readable, pills sit above their assays, edge labels don't
    overlap cards, and the canvas is taller;
  - check the "Image pipeline test" study too (the fork and the breast app's dataset pills).
  Review the screenshots and adjust the spacing constants if labels collide.
