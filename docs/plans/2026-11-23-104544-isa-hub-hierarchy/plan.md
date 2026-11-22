# ISA projects page: show the full hierarchy, tidy the card

## Context

The ISA projects page (`/catalogue/isa-project`, `IsaProjectHub.vue`) lists each project as one card:
title, a summary ("1 investigation, 2 studies, 14 assays"), five or six buttons, and each study's
assay chain. Problems seen on the current page:

- Investigations appear only as a count, so the ISA tree (project → investigation → study) isn't
  visible. Studies show only as a faint label beside their chain.
- The Breast Pilot chain is wider than the card and is cut off at "7. Ge…"; the horizontal scroll
  is easy to miss.
- The action row has up to six buttons of equal weight.

Decisions (from the questions):
- Hierarchy depth: project → investigation → study. Assays stay as the study's flow chain (chips);
  no per-assay rows, no datasets.
- Layout: an indented tree on each project card. Each study row keeps its flow chain under it.
- Links: an investigation row opens the study dashboard at that investigation, and a study row at
  that study (the trail the dashboard already understands). Assay chips stay display-only. No
  change to the study dashboard.
- Actions: Approve (uploads only) and "Open in study dashboard" stay as buttons. Download JSON,
  Download bundle, and Reset (examples) or Remove (uploads) move into a "More actions" (⋯) menu.
- Frontend-only prototype code. No shared components change (`CardUI.vue` keeps its scoped menu);
  the menu mirrors its look in the hub's own styles.

## Design

Keep the page's existing look (HubShell, aurora tokens, the ISA hub accent `#f0b97f`); the change
is structural, not a new theme.

- **One idea:** two line styles carry two meanings. Solid tree lines mean "contains" (the ISA
  hierarchy). Dashed lines mean "data flows into" (the assay chain, as today and as in the study
  dashboard's graph). The tree's rails sit at the left of the card, with the chains hanging off
  the study nodes.
- **Type:** the project title in `--font-title` (the page title's serif) at about 1.35rem, so each
  card is anchored. Investigation titles in `--font-ui` 600; study titles in `--font-ui` 500. The
  level and count follow each title as quiet sentence-case text: "investigation", "study,
  10 assays". No all-caps labels.
- **Colour:** existing tokens only: `--text`, `--text-dim`, `--text-faint`, `--line`, `--accent`.
  Tree rails in `--line`; a row's title takes `--accent` on hover/focus to show it links.
- **Layout:**
  ```
  Breast  (serif)                              [Open in study dashboard] [⋯]
  Example  1 investigation, 2 studies, 14 assays
  │
  └─ Breast Radiology Report   investigation
     ├─ Te Whatu Ora Breast Pilot   study, 10 assays
     │    1. Cohort ┄ 2. Conversion ┄┬ 3. Initial inference ┄ 4. … ┄ 5. …
     │                               └ Image visualisation
     │    ┄ 6. Inference ┄ 7. Generate breast model ┄ 8. … ┄ 9. …   (wraps, nothing cut off)
     └─ Image pipeline test   study, 4 assays
          1. Cohort ┄ 2. Conversion ┄┬ 3. Image visualisation
                                     └ 4. Breast app
  ```
  Left-aligned. An investigation with no studies says "No studies yet"; a study with no assays
  keeps the chain's "No assays yet".
- **Quality floor:** rows are buttons (keyboard reachable, visible focus ring in `--accent`); the
  chain keeps its `role="img"` readout; the card works at phone width (actions wrap under the
  title, the tree indents shrink).

## Steps (TDD)

Plan folder: `docs/plans/<YYYY-MM-DD-HHMMSS>-isa-hub-hierarchy/` with `plan.md` and `tasks.md`.
Tick each task as its check passes, and sync after every doc edit.

1. **Red:** in `__tests__/IsaProjectHub.spec.ts`:
   - "shows each project's investigations and their studies": the Breast row has one
     `[data-test=isa-investigation]` titled "Breast Radiology Report", holding two
     `[data-test=isa-study]` rows, "Te Whatu Ora Breast Pilot" (10 assays) and "Image pipeline
     test" (4 assays), each with its chain.
   - "opens an investigation in the study dashboard": clicking it pushes the trail
     `SANDBOX_ID,SANDBOX_ID:p-breast,SANDBOX_ID:p-breast:i-breast-radiology-report`.
   - "opens a study in the study dashboard": the trail goes one level further, to the study.
   - "says when an investigation has no studies": an upload with an empty investigation shows
     "No studies yet".
   - "keeps the downloads and reset/remove in a menu": the row shows no Download JSON / Download
     bundle / Reset button until the More actions button is clicked; then they are in the menu.
   - Update the existing tests that click `download-bundle`, `reset` and `remove` to open the
     menu first (the menu renders into `document.body`).
   → verify: `make test-frontend` fails on exactly those tests.
2. **Green:** in `IsaProjectHub.vue`:
   - Replace `row__chains` with the tree: investigations, then their studies, each study with its
     `StudyChain`. Reuse `open()`, extended to take the deeper ids and build the trail the way
     `sandbox.ts` ids are built (`SANDBOX_ID:project:investigation:study`).
   - Add the ⋯ menu (`v-menu`, `location="bottom end"`, `aria-label="More actions"`), mirroring
     `CardUI.vue`'s `.ucard__more` / `.ucard-menu` styles locally. Remove stays a danger item.
   - Project title in `--font-title`.
   In `components/StudyChain.vue`: drop the study label (the tree row now names the study) and let
   the columns wrap instead of scrolling. Update `StudyChain.spec.ts` if it asserts the label.
   → verify: `make test-frontend` passes; `make lint` passes.
3. **Glossary:** `docs/glossary.md`, "ISA project (prototype)": the Breast Pilot is now "the
   nine-assay breast pipeline plus an image visualisation after image conversion", not "a
   standalone image visualisation" (stale since the last change).
   → verify: `make docs-check` passes.
4. Rebuild and restart `portal-frontend` only, locally:
   `docker compose build portal-frontend && docker compose up -d --no-deps portal-frontend`.
   → verify: headless Firefox screenshots of `/catalogue/isa-project` at 1440px and 390px wide:
   the tree shows Breast → Breast Radiology Report → both studies; the Breast Pilot chain is not
   cut off; the ⋯ menu opens with the three actions; clicking the study row lands on the study
   page. Critique the screenshots and fix before reporting.

## Not in this plan

- Committing, pushing and deploying to the demo host: each needs a separate request.
- Per-assay rows, datasets, or an assay deep link into the study dashboard.

## Critical files

- `services/portal/frontend/src/views/isa-project/IsaProjectHub.vue`
- `services/portal/frontend/src/views/isa-project/components/StudyChain.vue`
- `services/portal/frontend/src/views/isa-project/__tests__/IsaProjectHub.spec.ts`
- `services/portal/frontend/src/views/isa-project/__tests__/StudyChain.spec.ts`
- Reference only: `views/upload-dataset/components/CardUI.vue` (menu look), `sandbox.ts` (trail ids)
- `docs/glossary.md`
