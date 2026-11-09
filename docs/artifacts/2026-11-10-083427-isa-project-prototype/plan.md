# ISA project prototype (frontend only): plan, revision 4

> **Scope: a frontend-only prototype.** Every change is in the Vue portal (`services/portal/frontend`), and every piece of data comes from bundled fixture files. There are no changes to the API, builder, Postgres, SEEK, MinIO or Airflow, and nothing is read from or written to them. The one exception, decided in R4, is the wording of one line on the real assays page (D25).

## Context

The study dashboard should:

1. Walk programme → project → investigation → study → assay.
2. Load a study design, show it, and **configure every assay in one place**.
3. Let assay 1 declare the datasets it will produce, and offer them as inputs to assay 2 **before they exist**, shown greyed out.
4. Show **which tools are in the workflow** chosen for an assay.

Building the backend for this now, against today's SEEK link (Assay → SOP → Workflow), would be wasted if the SEEK and ISA integration is redesigned. Today:
- outputs have no stable ids;
- an input can only point at a dataset that already exists;
- produced datasets aren't linked back to the output that made them.

So the first step is a **frontend-only throwaway prototype**. It agrees the UX, the domain terms and a draft "ISA project" format with stakeholders.

Revisions 1–3 are built and staged on `feat/isa-project-prototype`:
- the ISA project hub at `/catalogue/isa-project`;
- the "Study design sandbox" programme in `/study-dashboard`, with one example, "Breast pilot";
- List and Flow views of a sandbox study's assays, with configuration in a side panel;
- 364 frontend tests passing.

**Revision 4** comes from a grilling session on the domain model. It makes clear that an assay can run many times, that a planned dataset becomes real at **Submit**, and that a consumer reads the **latest submitted** run. The prototype's simulation, its cohort check and the wording are brought in line with that.

## Decisions

| # | Decision |
|---|---|
| D1 | A throwaway UX demo. No backend, database, SEEK or MinIO changes. |
| D2 | The study dashboard gets one small, test-covered seam that adds the sandbox programme. Real programmes are unaffected. |
| D3 | Data comes from fixtures behind one adapter interface. ISA projects, including uploads and edits, are kept in a Pinia store saved to this browser's localStorage. |
| D4 | Users will eventually upload a whole **ISA project** (format still to be agreed), and each upload becomes its own SEEK project. The prototype accepts one JSON file. |
| D5 | An admin-only "ISA project" card on `/catalogue` (`Prototype` badge) opens an upload/list hub. |
| D6 | One example, "Breast pilot (example)", with simple mock assays. Retired examples are pruned from browsers that stored them. |
| D8 | An assay may only use planned datasets from assays in **the same study**. |
| D10 | The panel lists the workflow's tools; "View workflow" opens `CWLWorkflowViewer.vue` in a dialog. |
| D11 | The panel edits the workflow, inputs, outputs and cohort. |
| D12 | Work happens on `feat/isa-project-prototype`. |
| D13 | `/study-dashboard` shows the frontend-only **"Study design sandbox"** programme to admins only. |
| D14–D16 | List and Flow views of the same assay cards. Flow draws labelled edges, dashed while planned. Configuration happens in a right-hand side panel. |
| D17 | **No loops** in the prototype. |
| D18 | **R4: an assay can run many times.** One execution is an **assay run**. A loop round (as in the reference image) is another run of the same assay, not a new assay. |
| D19 | **R4: a planned dataset becomes real at Submit**, when a run's outputs are submitted. A run that has finished but isn't submitted doesn't count, and approval isn't waited for. |
| D20 | **R4: a consumer reads the latest submitted run** of the assay producing its input. Pinning one specific dataset is done by choosing it as an ordinary input from the platform. |
| D21 | **R4: the cohort check warns and never blocks.** It applies only to **measurements** inputs, which are per subject. It fires when the consumer's cohort includes subjects outside the producer's cohort; an empty cohort means every subject. Models are not per subject, so they are never warned about. |
| D22 | **R4: the ISA project is the only thing a user uploads.** There is no separate "study design" upload, and "study design" stays informal (not a glossary term). **The assays page's "Load study design" button is removed**: uploads happen only through the catalogue's ISA project card. |
| D23 | **R4: the simulation adds a Submit step.** Launch takes a ready assay to *run, not submitted*: its edges stay dashed and downstream assays still wait. Submit on the card takes it to *submitted*: edges turn solid and downstream assays become ready. **Simulate next run** does both for every ready assay. |
| D24 | **R4: Launch on a submitted assay** says "already submitted (simulated). Reset to start again." A second run is documented, not simulated. |
| D25 | **R4: the real assays page's description changes** from "An Assay is a single workflow execution against a study cohort." to "An Assay is a workflow configured to run against a study cohort. It can be run many times." |
| D26 | **R4: delivery.** After revision 4, commit on the branch as four atomic Conventional Commits, with **no push and no PR yet**. |

My own defaults:
- **No ADR yet.** D18–D20 shape the future backend, so they become an ADR when that design starts. In a throwaway prototype they are easy to undo.
- **The example stays realistic.** Assay 4 trains on subjects 1–10 with labels for 1–10, so the example ships with no cohort warning. The walk-through triggers one by widening a cohort.
- **The card's other actions:** Monitor, Verify and Download still say "Not part of the prototype". **Submit** is now simulated.
  - Submit on an assay not yet run says "Launch it first."
  - Submit on an assay already submitted says it already is.

## Domain terms: glossary updates (`docs/glossary.md`)

- **Assay** (existing row): add "An assay can run many times; each execution is an assay run."
- **Assay run** (new row): one execution of an assay's workflow against its cohort. Its outputs collect in the workspace; submitting them turns them into datasets. Runs are kept per assay. The row links to the existing `Workspace` row.
- **Planned dataset (prototype)** (row updated):
  - It becomes a real dataset when a run of its assay is **submitted**.
  - An assay that uses it reads the **latest submitted** run.
  - For a measurements dataset, only the producer's subjects are covered.
- **"Study design"** is not added (D22).

## Revision 4: what changes

| Path (under `services/portal/frontend/src/`) | Change |
|---|---|
| `views/isa-project/model/isaProject.ts` | The simulation state becomes `Sim = { ran: string[]; submitted: string[] }`. `AssayStatus` gains `ran` and `submitted` (replacing `done`). An assay is `ready` when every producer is **submitted**. New functions: `simulateLaunch`, `simulateSubmit`, and `simulateRunStep`, which runs and submits every ready assay. `studyGraph` keeps an edge planned until its producer is submitted. New `cohortWarnings(study, assayId)` returns `{ port, datasetName, producerTitle, subjects }[]` for measurements inputs (D21), using `formatCohort`. |
| `views/isa-project/components/SandboxAssayCard.vue` | Status text for `ran` ("Run, not submitted") and `submitted` ("Submitted (simulated)"). Submit emits `submit`. A warning icon with a tooltip appears when the assay has cohort warnings (`data-test=cohort-warning`). |
| `views/isa-project/components/StudyGraph.vue` | Passes the `sim` state and the `submit` event through. |
| `views/isa-project/components/AssayPanel.vue` | Takes `sim` instead of `done`. "Produced by" is shown once the producer is submitted. Under each input it shows that input's cohort warning, for example "Annotations will only cover subjects 1-10." |
| `views/isa-project/StudyDesign.vue` | Holds `sim`, and handles launch, submit, the next-run wave and the messages (D23, D24). The **Load study design** button is removed (D22); the "study not found" message keeps its link to the hub. The legend gains "Run, not submitted". |
| `composables/useDashboardData.ts` | The `describeCategory("Assays")` text changes (D25). |
| `docs/glossary.md` | The rows above. |
| Artifacts | `plan.md` (revision 4) and `tasks.md` (revision 4 tasks), then `walkthrough.md`. |

## Steps (revision 4, TDD)

1. Add revision 4's tasks to `tasks.md`, then sync `plan.md` and `tasks.md` to `docs/artifacts/2026-11-10-083427-isa-project-prototype/`.
2. Model:
   - Failing specs in `isaProject.spec.ts`:
     - the statuses (a producer that has run but isn't submitted keeps its consumer blocked);
     - `simulateLaunch` and `simulateSubmit`;
     - `simulateRunStep` submitting each wave;
     - edges planned until submit;
     - `cohortWarnings`, which warns for a measurements input with a wider consumer cohort, not for a model input, and not when the producer's cohort is empty.
   - Then implement it. → verify: `make test-frontend`.
3. Card, graph and panel:
   - Failing specs: the card's new statuses, Submit emitting, the warning icon; the panel's warning text and "Produced by" only after submit; the graph passing `submit` through.
   - Then implement them. → verify: the suite.
4. `StudyDesign`:
   - Failing specs:
     - Launch → run, not submitted;
     - Submit → submitted, and the downstream assay becomes ready;
     - Submit before Launch says "Launch it first";
     - Launch on a submitted assay says to Reset;
     - the page has no "Load study design" button; the existing spec for it is replaced by one checking it is absent.
   - Then implement it. → verify: the suite and `make lint-frontend`.
5. The `describeCategory` text, with a spec, and the glossary rows. → verify: `make docs-check`.
6. Rebuild and restart `portal-frontend` only. Headless walk-through as admin:
   - Launch assay 1: the edge stays dashed;
   - Submit: the edge turns solid and assay 2 becomes ready;
   - Simulate next run;
   - widen assay 4's cohort to see the warning on the card and in the panel;
   - the real assays page shows the new description.
7. `make test`, `make lint`, `make docs-check`. Update `walkthrough.md`, sync the artifacts and run gitleaks.
8. Make four atomic Conventional Commits on `feat/isa-project-prototype`, with no push and no PR (D26):
   1. `feat(portal): ISA project model, fixtures and adapter (prototype)`
   2. `feat(portal): study design sandbox in the study dashboard (prototype)`
   3. `feat(portal): ISA project hub and sandbox assay views (prototype)`
   4. `docs: ISA project prototype glossary, codemap and artifacts`

   Each commit's files are checked for secrets first, and each commit passes `make test-frontend` on its own where its files allow.

## Verification

- `make test` passes, including the new specs; the real dashboard specs pass, and the only change to them is the description text.
- `make lint`, `make docs-check`, and gitleaks on the artifacts folder and the changed sources are clean.
- Manual check:
  - a planned edge stays dashed after Launch and turns solid only after Submit;
  - the cohort warning appears only for measurements inputs;
  - nothing under `/api` is called for sandbox pages;
  - real programmes and their assay cards behave as before, apart from the description line.

## Draft schema (`isa-project.json`, version `0.1-draft`): unchanged

`project`, then `investigations[].studies[].assays[]`. Each assay has `id`, `title`, `type`, `workflowId`, `cohort`, `inputs[{port, source: existing|planned|null}]` and `outputs[{port, datasetName, category}]`.

## Out of scope (for the follow-up backend design, and its ADR)

- The real upload format, including the folder layout.
- Creating the SEEK project, investigations, studies and assays.
- Stable ids on `assay_output`, the input → planned dataset link, and linking produced datasets back to their outputs and runs.
- Resolving "latest submitted run" (D20) on the server, and one dataset per output port in script runs.
- Loops, simulating several runs of one assay, a minimap.
