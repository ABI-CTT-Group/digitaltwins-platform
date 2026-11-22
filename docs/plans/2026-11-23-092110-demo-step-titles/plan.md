# Demo: number the breast pilot steps instead of calling them "Assay N"

## Context

The prototype study dashboard (`/study-dashboard`, Te Whatu Ora Radiology Reporting → Breast →
Breast Radiology Report → Te Whatu Ora Breast Pilot) is shown to an audience that may not know the
word "assay". The step titles come from the bundled example, so the change is in the data. The
titles become numbered plain names ("1. Cohort selection"). Other "assay" wording on the page stays
as it is.

Decisions settled with the user:
- Form: `N. Name` (number, full stop, sentence-case name). The unnumbered standalone step stays
  unnumbered: "Assay: Image visualisation" becomes "Image visualisation".
- Both studies in the example: Breast Pilot and Image pipeline test.
- Titles only. The breadcrumb "Assays", the status messages ("later assays") and the legend stay.
- Sentence case throughout ("Statistical Analysis" becomes "Statistical analysis", "breast app"
  becomes "Breast app").
- Messages that embed a title ("Ran 1. Cohort selection. Submit…") are accepted as they read.
- Bump `EXAMPLE_RELEASE` 2 → 3 so every browser, the demo host's included, reloads the example.
  Local sandbox edits to the example are reset; uploads are kept.

## Renames (`fixtures/example-breast-pilot.json`, `title` only; ids unchanged)

| id | Old | New |
|---|---|---|
| a-cohort | Assay 1 - Cohort selection | 1. Cohort selection |
| a-convert | Assay 2 - Image conversion | 2. Image conversion |
| a-initial-inference | Assay 3 - Initial inference | 3. Initial inference |
| a-breast-app | Assay 4 - Image annotation | 4. Image annotation |
| a-finetune | Assay 5 - Model fine-tuning | 5. Model fine-tuning |
| a-inference | Assay 6 - Inference | 6. Inference |
| a-breast-model | Assay 7 - Generate breast model | 7. Generate breast model |
| a-lesion-report | Assay 8 - Lesion position reporting | 8. Lesion position reporting |
| a-statistics | Assay 9 - Statistical Analysis | 9. Statistical analysis |
| a-visualise | Assay: Image visualisation | Image visualisation |
| a-pipeline-cohort | Assay 1: cohort selection | 1. Cohort selection |
| a-pipeline-convert | Assay 2: image conversion | 2. Image conversion |
| a-pipeline-visualise | Assay 3: image visualisation | 3. Image visualisation |
| a-pipeline-breast-app | Assay 4: breast app | 4. Breast app |

Check the fixture for any other string built from those titles (for example the
`datasetName: "<title> outputs"` that `isaProject.ts:284` builds only when a workflow changes, so
it isn't stored), and update any that is stored.

## Steps (TDD)

Plan folder: `docs/plans/<YYYY-MM-DD-HHMMSS>-demo-step-titles/` with `plan.md` and `tasks.md`.
Tick each task as its check passes, and sync after every doc edit.

1. **Red:** update the expectations that read titles from the fixture to the new titles. These are
   `isaProjectSource.spec.ts` (the two title tables), `isaProjectStore.spec.ts:104`,
   `BundleUploadDialog.spec.ts:70`, and any fixture-derived expectations in `StudyChain.spec.ts`,
   `StudyDesign.spec.ts` and `AssayPanel.spec.ts`. Leave specs that build their own inline fixture
   (for example `SandboxAssayCard.spec.ts`) alone. Add an assertion that no example assay title
   matches `/^Assay\b/`.
   → verify: `make test-frontend` fails on exactly those expectations.
2. **Green:** edit the 14 titles in the fixture and set `EXAMPLE_RELEASE = 3` in
   `adapter/isaProjectSource.ts`.
   → verify: `make test-frontend` passes, and `make lint` matches main.
3. Update the code comment `platformRun.ts:22` ("Assay 8 reuses Assay 4's GUI tool") to name the
   steps the new way, and check `docs/glossary.md` (the ISA project entry) for the old title wording.
   → verify: `make docs-check` passes.
4. Rebuild and restart `portal-frontend` only:
   `docker compose build portal-frontend && docker compose up -d portal-frontend`.
   → verify: open the linked page (headless Firefox screenshot). The graph cards, the side panel
   and the "Produced by" lines show the numbered titles, and the old example was replaced without
   a manual Reset.

## Out of scope (mention, don't change)

- The platform's own SEEK mock assays are named "Mock Assay 3: initial inference" etc.
  (`util/populate-isa-mock-assays.sh`). They show on `/study-dashboard-platform` and in Airflow,
  not on this page.
- Deploying to the demo host, and committing: each needs a separate request.

## Critical files

- `services/portal/frontend/src/views/isa-project/fixtures/example-breast-pilot.json`
- `services/portal/frontend/src/views/isa-project/adapter/isaProjectSource.ts` (`EXAMPLE_RELEASE`)
- `services/portal/frontend/src/views/isa-project/platformRun.ts` (comment only)
- Specs under `services/portal/frontend/src/views/isa-project/__tests__/`

---

# Part 2: no "mock" where the demo audience can see it

Status: Part 1 is done (titles, release bump, tests, rebuild). Part 2 waits for approval.

## Context

The demo may also show Airflow, Jupyter, SEEK, the platform dashboard and the portal catalogue. The
stand-in steps (3, 5, 6, 7, 9) come from `examples/workflow/workflow_mock_*`, registered by
`util/populate-isa-mock-assays.sh`, and "mock" shows in these places:

- Airflow: the DAG display names ("Mock inference", "Mock breast model generation"), the `mock`
  tag, the task log lines ("… finished (mock)"), and the Code tab (file names and docstrings).
- Jupyter: the notebook files `mock_*.ipynb`, their "# Mock …" headings and "done (mock)" prints.
- SEEK and the platform dashboard: the study "Breast pilot mockups" and the assays "Mock Assay N: …".
- The catalogue, SEEK and the prototype's workflow picker: the workflow and tool names
  (`workflow_mock_inference`, `tool_mock_skin_inference`, …).
- The output datasets: `mock_initial_inference`, `mock_inference` and `mock_breast_model`.

Decisions settled with the user:
- Rename the packages, files and wording in the repo, so registering them again stays clean.
- The DAG display names match the step titles. The tag `mock` becomes `breast-pilot`.
- Output files keep a truthful note without the word: "Placeholder for <output>; nothing was
  computed." File names keep the `_placeholder` suffix, and the notebook's `docs/mock_output.txt`
  becomes `docs/placeholder.txt`. Nobody sees the note unless they open an output file.
- SEEK: the study becomes "Te Whatu Ora Breast Pilot", and the assays become "3. Initial inference",
  "5. Model fine-tuning", "6. Inference", "7. Generate breast model" and "9. Statistical analysis".
- Live roll-out: swap through the platform API, locally only. The demo host is a later, separate
  request.

## New names

| Old | New |
|---|---|
| `workflow_mock_inference` (DAG "Mock inference") | `workflow_breast_inference` (DAG "Inference") |
| `workflow_mock_breast_model` (DAG "Mock breast model generation") | `workflow_breast_model` (DAG "Generate breast model") |
| `workflow_mock_model_finetuning`, `mock_model_finetuning.ipynb` | `workflow_model_finetuning`, `model_finetuning.ipynb` |
| `workflow_mock_statistical_analysis`, `mock_statistical_analysis.ipynb` | `workflow_statistical_analysis`, `statistical_analysis.ipynb` |
| `tool_mock_<step>` (9 tools: .py, .cwl and CWL `label`) | `tool_<step>` |
| CWL labels "Workflow - Mock inference", "Tool - mock skin inference", … | "Workflow - Inference", "Tool - skin inference", … |
| outputs `mock_initial_inference`, `mock_inference`, `mock_breast_model` | `initial_inference`, `inference`, `breast_model` |

None of the new names is registered locally yet (checked).

## Steps

1. **Red:** point the tests at the new names: `services/api/tests/test_example_workflows.py` (package
   list) and `isaProjectSource.spec.ts:104-111` (catalogue names). Add a test in
   `test_example_workflows.py` that no file name or text file in those four packages contains "mock"
   (case-insensitive), including the strings inside the `.xlsx` files.
   → verify: `make test-api` and `make test-frontend` fail on exactly those tests.
2. **Green, repo:** `git mv` the four packages and their files. Reword the DAG docstrings, display
   names, tags, tool `run()` messages, placeholder text, notebook headings, prints and output file,
   READMEs, CHANGES and CWL labels. Edit the SDS spreadsheets' "mock" cells (titles, descriptions)
   with openpyxl in a throwaway container. In the portal's `fixtures/catalogue.json`, rename the
   workflow and tool `name`s; the ids (`wf-mock-*`, `t-mock-*`) stay, since nobody sees them.
   → verify: `make test-api`, `make test-frontend`, and `make lint` pass.
3. **Populate script and docs:** in `util/populate-isa-mock-assays.sh`, use the new package names,
   study title, assay titles and output names (the script keeps its file name, which the audience
   never sees). Update `docs/glossary.md`, `docs/codemap.md`, `util/SCRIPTS.md` and the
   `platformRun.ts` comment. Bump `EXAMPLE_RELEASE` to 4, since the catalogue names changed.
   → verify: `make docs-check` passes; `bash -n` on the script.
4. **Swap script:** add `util/swap-isa-mock-workflows.sh`. It is re-runnable on any host and
   authenticates like the populate script. It takes the assay ids as a variable (default 46–50), finds the
   old workflows by name, and has a dry-run mode. Steps:
   1. Register the four renamed packages through `POST /datasets?category=workflows`.
   2. Re-save assays 46–50 through `POST /assays` with the new workflow ids, the same inputs and
      cohort as now (read from `GET` first), and the renamed outputs.
   3. Retitle the study and the five assays with `rails runner`, as the populate script does.
   4. `DELETE /datasets/{uuid}?delete_tools=true` for the four old workflows. This also removes their
      tools, MinIO files, SEEK entries and Airflow DAG folders.
   5. `DELETE /datasets/{uuid}` for the submitted `mock_*` output datasets.

   Steps 4 and 5 delete data, so the script asks before each unless `-y` is passed. Add the script to
   `util/SCRIPTS.md`, marked destructive.
   → verify: `make docs-check`; a dry run prints the plan with the right ids.
5. **Run it locally** (asking before the deletions). Then remove `assay_47/` and `assay_50/` from the
   admin user's Jupyter workspace (asking first). Notebook staging only adds missing files, so the old
   `mock_*.ipynb` would otherwise stay beside the new ones.
   → verify: Airflow lists "Inference" and "Generate breast model" tagged `breast-pilot`, and none of
   the old DAGs. Launch step 6 from the prototype, then check its logs and the
   placeholder text. Launch step 5 and check the notebook in Jupyter. Check the SEEK study and assay
   titles, and that the catalogue shows no "mock" workflows or tools. Re-run
   `grep -ri mock` on the live names. Rebuild and restart `portal-frontend` (catalogue fixture). Take
   screenshots of Airflow and the prototype.
6. **Wrap-up:** sync this plan and tasks to `docs/plans/`, and record the swap-versus-patch choice as
   an ADR only if it turns out to matter beyond this demo. It's a one-off ops choice, so probably
   not.

## Not in this part

- Running the swap on the demo host (`nectar-test_demo`): a separate request, after the local check.
- Committing.
- The `wf-mock-*` and `t-mock-*` ids in the prototype fixture, which nobody sees.

## What changed during Part 2

- SEEK titles workflows and tools by their CWL `label` ("Workflow - Mock inference"), not the
  folder name. So the orphaned link SOPs were titled "Workflow link: Workflow - Mock …". The swap
  script finds them by the old workflow ids, not by title, and deletes them before the workflows.
  SEEK cleanup in the platform's delete is best-effort, and a SOP could otherwise keep an old
  workflow alive in SEEK.
- The swap script's prompt skips (doesn't fail) when there is no terminal, so run it with `-y`
  where nobody can answer.
- Airflow keeps a deleted workflow's DAG in its database, marked stale. Airflow 3's DAG list hides
  it; `airflow dags delete` removes its run history.
- The SDS spreadsheets' descriptions now say "A placeholder workflow for demos … Nothing is
  computed.", and their keywords say "placeholder" instead of "mock".
- No ADR: the swap is a one-off data change for demo items, made with existing APIs.

---

# Part 3: drop the platform wording from the study page

The user asked to remove two things from the Te Whatu Ora Breast Pilot study page for the demo:

- The note under the toolbar: "Launch, Submit and Download run the linked platform assays with
  their platform configuration. Changes you make here stay in this browser, and later platform
  assays keep reading the datasets they were configured with." (`StudyDesign.vue`, with its
  `.design__note` style.)
- The "Platform assay N" link on each linked card (`components/SandboxAssayCard.vue`, with its
  `.card__platform` styles). The link opened `/launched-assay?assayId=N`; the side panel and the
  actions still work without it.

The steps still run their linked platform assays; only the wording goes.

Steps:
1. **Red:** `StudyDesign.spec.ts` expects no "platform assay" text on the linked study;
   `SandboxAssayCard.spec.ts` expects no `platform-assay` link on a linked card.
   → verify: `make test-frontend` fails on exactly those two.
2. **Green:** remove the note and the link with their styles.
   → verify: `make test-frontend` (527) and `make lint` pass.
3. Rebuild and restart `portal-frontend`; screenshot the page.
   → verify: neither text shows; Launch is still enabled on the linked cards.

---

# Part 4: deploy to the demo host (platform and data)

The user asked to deploy Parts 1–3 to the demo host, both the platform and the data.

1. Bring the demo checkout up to these changes; rebuild and restart `portal-frontend` only
   (`up -d --no-deps portal-frontend`).
   → verify: the served bundle has the numbered titles and the renamed workflows, and no
   "Platform assay" or note text.
2. Run `util/swap-isa-mock-workflows.sh` there: `-n` first, then `-y`. A host without `zip` needs a
   PATH shim that calls `python3 -m zipfile -c`.
   → verify: SEEK titles have no "mock"; Airflow shows "Inference" and "Generate breast model"
   tagged `breast-pilot`, with no import errors.
