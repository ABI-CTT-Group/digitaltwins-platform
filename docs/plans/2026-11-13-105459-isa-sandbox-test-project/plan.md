# Study design sandbox: rebase the example on the real Test Project (frontend only)

## Context

The study design sandbox (`/study-dashboard?trail=isa-sandbox,...`) and the ISA project hub
(`/catalogue/isa-project`) ship one made-up example, "Breast pilot", whose six mock assays and
workflows match nothing on the platform. Stakeholders compare the sandbox with the real
**Test Project** (`/study-dashboard?trail=7,12,10,11`), so the example should mirror it:

```
Test Assay 1: cohort selection ─► Test Assay 2: image conversion ─┬─► Test Assay 3: image visualisation
                                                                  └─► Test Assay 4: breast app
```

**Frontend only.** Every change is in `services/portal/frontend` (fixtures, sandbox model,
components and specs), plus the glossary and the plan folder. Nothing changes in the API, builder,
Postgres, SEEK, MinIO or Airflow. The real data below was only read from them.

## Real data (read from SEEK study 11, Postgres `assay*`, MinIO CWL)

| Assay | Workflow (type, tools) | Inputs | Outputs → dataset |
|---|---|---|---|
| 1 cohort selection | `workflow_mri_curation` (notebook; `tool_mri_curation`) | `raw_dataset` ← test_dicom | `curated_dataset` → test_curated_dataset |
| 2 image conversion | `workflow_image_conversion` (script; `tool_dicom_to_nifti`, `tool_dicom_to_nrrd`) | `dicom_input` ← **planned** A1 `curated_dataset` | `nifti_output`, `nrrd_output` → test_converted |
| 3 image visualisation | `workflow_volview` (gui; `tool_volview`) | `dicom_file` ← **planned** A2 `nifti_output` | `output` → test_volview_output |
| 4 breast app | `workflow_Lesion-Ground-Truth-Curator` (gui; `tool_Lesion-Ground-Truth-Curator`) | `contrast_pre_nrrd` ← **planned** A2 `nrrd_output`; 14 others ← test_data_breast_app; `breast_surface_glb` ← test_model_breast_app | 12 ports → test_breast_app_output |

All ports are `measurements`. The CWL ports come from the real workflow files in MinIO.

## Decisions (grilling, 2026-11-13)

| # | Decision |
|---|---|
| E1 | **Scope:** swap the data, plus targeted design where the new shape strains the UI (the A2 fork, an assay with 16 inputs and 12 outputs) and a chain preview on the hub. |
| E2 | **Replace** "Breast pilot" with one example, **"Test Project (example)"**. New ids: `p-test-project` / `i-test` / `s-test` / `a-cohort`, `a-convert`, `a-visualise`, `a-breast-app`. `ensureExamples` already prunes the retired example from browsers that stored it, so the old sandbox URL shows "study not found" with its link to the hub. |
| E3 | **Wiring:** as in the table. Only `contrast_pre_nrrd` reads A2. The other breast app inputs stay on existing datasets. |
| E4 | **Titles:** spelling fixed and every assay numbered ("Test Assay 2: image conversion", "Test Assay 3: image visualisation", "Test Assay 4: breast app"). Workflow, tool and port names are copied verbatim. |
| E5 | **Cohorts:** A1 `[]` (every subject), A2–A4 `[1]`. The page loads with no cohort warning. |
| E6 | **Shared dataset names, as on the real platform:** several output ports of one assay can promise the **same** dataset. Each port fills one part of it, and the **port name serves as that part's sample type**, so the schema stays `0.1-draft`. Labels read `test_converted / nrrd_output`. |
| E7 | **Catalogue:** real items only: the 4 workflows, 5 tools and 5 `test_*` datasets (`test_dicom`, `test_curated_dataset`, `test_converted`, `test_data_breast_app`, `test_model_breast_app`). Because the real `test_curated_dataset` exists, A2's picker offers it alongside the planned one, which shows D20 (pin a dataset, or read the latest submitted run). |
| E8 | **Panel:** inputs are grouped by source, and a group of 4 or more inputs starts collapsed. Each row keeps its own picker; there is no bulk set. Outputs are grouped by dataset name, with one name field per group that renames every port in it. |
| E9 | **Hub:** each row gains a chain preview of its studies' assays. |

My defaults, flagged for review:
- `setWorkflow` now names every new output `${assay.title} outputs` (one shared dataset per assay, like the real "New dataset" default) instead of one dataset per port.
- Existing-dataset inputs still pick a dataset only, not a sample type. The real breast app picks 14 sample types from `test_data_breast_app`, but adding that would need a schema change, so it is out of scope.
- Flow edges from a platform dataset that feeds several inputs are labelled with the count ("14 inputs").
- No ADR: the prototype is throwaway. E6 joins D18–D20 as input to the backend ADR.
- Work on the current `prototype` branch. No commits until asked.

## Design (frontend-design pass)

The sandbox lives inside the portal's Aurora theme (dark surface, Hanken Grotesk / `--font-title`,
category accents `--accent-measurements` and others, type-tag colours from the real assay cards).
A targeted change inherits those tokens and adds no new palette. Its one new visual idea is that
**the hub's chain preview and the Flow view speak the same line language**: solid for submitted,
dashed for planned, and a fork drawn as a branch rather than a list. A user who has seen one can
read the other.

**Flow view (`StudyGraph` / `studyGraph`)**
- A platform-dataset node sits in the column just before its first consumer, instead of always in column 0. `test_data_breast_app` and `test_model_breast_app` then sit beside A4 and don't send a long edge across the graph.
- Planned edge labels show `dataset / port` (E6), so the fork reads `test_converted / nifti_output` and `test_converted / nrrd_output`.

**Side panel (`AssayPanel`)**
```
Inputs
 ▾ From Test Assay 2 · test_converted (planned)        1
     contrast_pre_nrrd   [test_converted / nrrd_output ▾]
 ▸ Platform dataset test_data_breast_app              14
 ▾ Platform dataset test_model_breast_app              1
     breast_surface_glb  [test_model_breast_app ▾]
 ▾ Not chosen yet                                      0   (shown only when non-empty, always open)
Outputs
   test_breast_app_output  [name field]   12 ports: mask_meta_json, …
```
- Group headers are buttons with `aria-expanded`. The count sits on the right.
- Moving an input to another source moves it to that group. A group the user opened stays open.

**Hub chain preview (`StudyChain.vue`, new)**
```
Test Project (example)                 [Open in study dashboard] [Download JSON] [Reset]
Example · 1 investigation, 1 study, 4 assays
Test Study   (1 cohort selection)┄┄(2 image conversion)┄┬┄(3 image visualisation)
                                                        └┄(4 breast app)
```
- Chips use the assay-type tag colour. Connectors are dashed (planned), because the hub has no run state.
- It reuses `studyGraph` columns, so the layout logic is shared with Flow view. On a phone the columns wrap.
- It is decorative-plus-label: the chain has an `aria-label` listing the assays in run order.

Self-review against the brief: the plan adds no new colours, cards or motion. Its one bold choice is
the shared line language. I rejected numbered step badges on the chips, because the titles already
carry the numbers.

## Changes (paths under `services/portal/frontend/src/views/isa-project/`)

| Path | Change |
|---|---|
| `fixtures/example-test-project.json` (new), `fixtures/example-breast-pilot.json` (delete) | The Test Project example (E2–E6). |
| `fixtures/catalogue.json` | Real workflows, tools, datasets and CWL (E7). |
| `adapter/isaProjectSource.ts` | The examples map points at the new fixture. |
| `model/isaProject.ts` | `inputOptions` labels planned options `dataset / port`. `studyGraph` places a source node one column before its first consumer, labels planned edges `dataset / port`, and gives existing edges a count label when a source feeds more than one input. New `inputGroups(study, catalogue, assayId)` and `outputGroups(assay)`. `setWorkflow` uses a shared default dataset name. |
| `components/AssayPanel.vue` | Grouped inputs and outputs (E8). |
| `components/StudyChain.vue` (new), `IsaProjectHub.vue` | Chain preview (E9). |
| `sandbox.ts` | No logic change. Check the description text still fits. |
| `__tests__/*.spec.ts`, `views/dashboard/__tests__/DashboardView.spec.ts`, `composables/__tests__/useDashboardData.spec.ts` | Move fixture-dependent specs from the Breast pilot ids to the Test Project ids. |
| `docs/glossary.md` | **Planned dataset (prototype)**: "A dataset an assay promises. Each of the assay's output ports fills one part of it, and several ports can fill the same dataset; an input chooses one port's part." The rest of the row is unchanged. |
| `docs/codemap.md` | Mention the example only if it is named there. |
| `docs/plans/2026-11-13-105459-isa-sandbox-test-project/` | `plan.md`, `tasks.md`, then `walkthrough.md`. |

## Steps (TDD)

1. Create the plan folder with `plan.md` (this plan) and `tasks.md`, and run gitleaks on it. → verify: the files exist.
2. Fixtures and adapter. Write failing specs first: `isaProjectSource.spec` (the example lists "Test Project (example)" and validates against the catalogue; its A2 has both ports in `test_converted`), and `isaProjectStore.spec` (a stored `example-breast-pilot` is pruned). Then write the fixtures. → verify: the new specs pass under `make test-frontend` (fixture-id specs elsewhere may fail until step 5).
3. Model. Write failing specs in `isaProject.spec` for:
   - the `dataset / port` labels in `inputOptions` and on edges;
   - the source column placement;
   - the "14 inputs" count label;
   - `inputGroups` (order, the planned and existing groups, the "not chosen" group);
   - `outputGroups`;
   - the `setWorkflow` default name.

   Then implement them.
4. Panel and hub. Write failing specs first:
   - `AssayPanel.spec`: groups render, a group of 4 or more starts collapsed and toggles, and renaming an output group renames every port in it;
   - `StudyChain.spec` and `IsaProjectHub.spec`: the A2 fork renders as two branches, and the aria-label lists the assays in order.

   Then implement them.
5. Move the remaining fixture-dependent specs (`StudyDesign`, `StudyGraph`, `SandboxAssayCard`, `sandbox`, `DashboardView`, `useDashboardData`) to the new ids. → verify: `make test-frontend`, `make lint-frontend`.
6. Glossary row. → verify: `make docs-check`.
7. Rebuild and restart **only** `portal-frontend` (`docker compose up -d --build portal-frontend`). Check the result with headless Firefox screenshots as admin:
   - the hub row and its chain;
   - the sandbox Flow view, with the fork and the sources beside A4;
   - the breast app panel, with its groups;
   - the List view;
   - Launch then Submit on A1 turns the edge solid, and Simulate next run;
   - widening A3's cohort shows a warning.

   Compare with the real Test Project page.
8. `make test`, `make lint`, `make docs-check`. Write `walkthrough.md`, tick `tasks.md`, sync the plan folder and run gitleaks. Don't commit until asked.

## Verification

- `make test`, `make lint` and `make docs-check` pass. Real dashboard specs change only in fixture ids, if at all.
- Manual checks:
  - the sandbox study shows 4 assays with real workflow and tool names;
  - A2's picker offers both the real `test_curated_dataset` and the planned `test_curated_dataset / curated_dataset`;
  - the A2 fork edges are labelled by port;
  - the breast app panel shows 3 groups, with the 14-input group collapsed;
  - the hub chain draws the fork;
  - the network tab shows no `/api` calls for sandbox pages.

## Out of scope (backend ADR later)

- Sample types on existing-dataset inputs.
- Real `sampleName` on outputs that differs from the port.
- Loading examples from the live API.
- Any change to the real assay pages.
