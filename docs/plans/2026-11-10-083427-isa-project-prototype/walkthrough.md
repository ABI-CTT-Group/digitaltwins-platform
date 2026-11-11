# Walkthrough: ISA project prototype (frontend only)

Plan: [plan.md](plan.md) (revision 4). Tasks: [tasks.md](tasks.md). Branch: `feat/isa-project-prototype`.

This is a **frontend-only, throwaway prototype**. Every change is in the Vue portal. ISA projects come from one bundled example or a user's upload, and are kept in the browser's localStorage. Nothing calls the API, SEEK, Postgres, MinIO or Airflow.

## What a user sees

1. **Catalogue → "ISA project" card** (admin only, `Prototype` badge) opens `/catalogue/isa-project`, the ISA project hub.
   - **Upload ISA project (JSON)** takes a file in the draft schema (`schemaVersion: "0.1-draft"`, see `model/types.ts`). A bad file is rejected, with every problem listed.
   - Uploading a file whose project id is already listed asks before replacing it.
   - Each row shows the project's title, whether it is an Example or Uploaded, and its counts. The actions are **Open in study dashboard**, **Download JSON**, and **Remove** (uploads) or **Reset** (the example). Remove and Reset ask first.
2. **Study dashboard → "Study design sandbox"** is a programme shown to admins only, and only on the study dashboard. Under it are:
   - the one example, **Breast pilot (example)**, and any uploads, each as a project;
   - their investigations;
   - their studies.
3. **A sandbox study's Assays page** has a **List | Flow** toggle (remembered in this browser), **Simulate next run** and **Reset**. Uploads happen only from the catalogue's ISA project card, so this page has no upload button.
   - Both views show the same **assay cards**, styled like the real ones. Each card has:
     - its title and a type tag;
     - a status: needs configuring, waiting on earlier assays, ready to run, run but not submitted, or submitted (simulated);
     - a **Cohort** badge when it has a cohort warning;
     - the usual action buttons:
       - **Launch** simulates a run, and the assay becomes *run, not submitted*. Its outputs don't exist yet, so its edges stay dashed and later assays keep waiting.
       - **Submit** makes its planned datasets exist. Edges turn solid, and the assays that read them become ready.
       - Launch on a submitted assay says to Reset; Submit before Launch says to launch first.
       - **Monitor**, **Verify** and **Download** say they aren't part of the prototype.
   - **List**: a grid of cards in the study's order.
   - **Flow**: the cards left to right in dependency order.
     - Datasets already on the platform are pills, level with the assay they feed.
     - An edge between two assays is labelled with the dataset names it carries, and is **dashed while those datasets are still planned**.
     - The view starts at the left edge at a readable zoom. Zoom in, zoom out and fit buttons sit at the bottom left.
   - **Configuring**: the pencil, the expand icon, or (in Flow) a click on the card opens a right-hand side panel with:
     - the workflow, filtered to the assay's type;
     - **tools in this workflow**, with **View workflow** opening the CWL graph;
     - the inputs, where planned datasets from upstream assays in the same study are greyed with "Will be produced by …";
     - under an input, a **cohort warning** when it reads per-subject (measurements) data for fewer subjects than this assay runs, for example "Annotations will only cover subjects 1-10." It warns and never blocks; model inputs never warn;
     - the output dataset names;
     - the cohort.
   - **Simulate next run** runs and submits every ready assay as one wave. **Reset** clears the simulation, and so does any edit.
4. The page description for assays, on real and sandbox studies alike, now reads: "An Assay is a workflow configured to run against a study cohort. It can be run many times."

### The example: Breast pilot

This is a mock study of six assays, modelled on a reference sketch, with no loop:
1. cohort selection;
2. DICOM to NIfTI conversion;
3. annotate cases;
4. train segmentation;
5. breast pilot workflow;
6. analyse outputs.

Assay 5's segmentation-model input ships unset, so choosing the planned output of assay 4 can be shown. Assay 6 ships without a workflow.

## Domain model (revision 4, from a grilling session)

- **Assay run**: one execution of an assay. An assay is configured once and can run many times, and a loop round is another run of the same assay. Added to the glossary.
- **A planned dataset becomes real at Submit.** A run that has only finished doesn't count. A consumer reads the **latest submitted** run of its producer; to use one specific dataset, choose it as an ordinary input from the platform.
- **Cohort check**: for measurements inputs only, warn when the consumer's cohort includes subjects its producer doesn't run. An empty cohort means every subject.
- **One uploaded unit**: the ISA project. "Study design" stays informal.
- No ADR yet: these shape the future backend design, where the ADR belongs.

## Design notes

- **The dashboard seam** (`composables/useDashboardData.ts`): `getProgrammes()` appends the sandbox programme for admins after the cached real list. `getChildren()` answers any `isa-sandbox…` id from the store before any cache or API call. `DashboardView.vue` renders `StudyDesign` when the trail ends at a sandbox study.
- **Retired examples**: `ensureExamples()` drops stored examples that no longer ship, so browsers that held the earlier lung and breast examples now show only the breast pilot. Uploads are kept.
- **The graph model** (`studyGraph`) has one node per assay and per platform dataset, and one edge per pair of nodes, labelled with the planned datasets it carries. Layout is computed by hand from topological levels, so there is no new dependency.
- **The side panel** is a `v-dialog` styled as a right-hand sheet. The portal has no Vuetify layout for a navigation drawer.
- **Vue-flow** stops pointer events on nodes when nothing listens for node clicks. The graph listens, which is also what lets a click on a card open it.
- **`CWLWorkflowViewer`**:
  - It keys nodes by name, so a step named like a workflow input or output vanishes; a catalogue spec guards against that.
  - It draws its step nodes with a render function, so its own scoped styles never reach them, and the dialog styles them itself.
  - Both problems are in the shared component, which this prototype does not change.

## Verification

- `make test`: all suites pass. The frontend has 371 tests.
- `make lint` and `make docs-check` are clean.
- `portal-frontend` was rebuilt and restarted. A headless Firefox walk-through as an admin covered:
  - a browser seeded with the old lung example plus an upload, which then listed the upload and the breast pilot only;
  - Flow, then List;
  - the side panel, and picking the planned segmentation model for assay 5;
  - Launch on assay 1, then simulated waves turning edges solid;
  - fit to view;
  - View workflow;
  - the List view at phone width;
  - (revision 4) Launch assay 1, with the edge still dashed; Submit, with the edge solid and assay 2 ready; Simulate next run; assay 4's cohort widened, showing the warning on the card and in the panel; no upload button on the page; the new description.

  No `/api` request carried a sandbox id.
- Not checked in a browser: the researcher view, since there was no test user. `useDashboardData.spec.ts` covers the sandbox being hidden from non-admins.

## Follow-ups (outside this prototype)

- The real upload format (possibly a folder with `isa-project.json` at its root) and creating the SEEK project from it.
- The backend changes listed in the plan's "Out of scope" section.
- Loops (repeat a group of assays until a condition is met), simulating several runs of one assay, and a minimap.
- Resolving "latest submitted run" on the server, with an ADR for the assay run and planned dataset model.
- A study wider than the screen is panned at a readable zoom; the fit button shows all of it, smaller.
