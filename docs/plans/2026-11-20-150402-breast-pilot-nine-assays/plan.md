# Plan: 9-assay breast pilot with real mock workflows

## Context
The demo study dashboard (`/study-dashboard`, ISA example "Te Whatu Ora Breast Pilot") shows 4 assays
linked to the Test Project's platform assays (41 cohort, 42 conversion, 43 visualisation, 45 breast app).
The demo needs to show the full breast pipeline as 9 assays. The 5 assays that don't exist yet become
**real mock platform workflows**: their Airflow steps or notebook cells wait about 10 s and pass. The
original 4 assays, with their flow, move to a separate study. Image visualisation becomes a standalone
assay in the pilot study.

Real reference: the platform's "Assay 4 - Initial inference" (SEEK assay 39 in study 9; DAG `workflow_39`)
runs `download_samples` → `skin_inference` → `outer_rib_inference` → `sternum_inference` →
`lesion_inference`.

## Settled decisions (grilling)
| # | Decision |
|---|---|
| G1 | Mock assays are **real platform workflows** (sleep DAGs and notebooks), not portal-only fakes |
| G2 | The mocks live in a **new SEEK study "Breast pilot mockups"** under Test Project (project 12) → Test Investigation (investigation 10). The populate script creates it. It sits apart from Test Study (41 to 45) and from the real breast pilot study 9, which is untouched. Its workflows are imported into project 12. The original dashboard shows it only if you drill into Test Project |
| G3 | Pilot study = the 9-assay pipeline plus a standalone "Assay: Image visualisation". A new sibling study, **"Image pipeline test"**, keeps the original 4 assays, their links and their titles unchanged |
| G4 | **Assay 8** reuses Assay 4's GUI tool for now: it links to platform assay 45 (lesion curator) until the real tool is uploaded |
| G5 | Wiring (Flow edges): see the table below |
| G6 | Titles are written as the user gave them: "Assay 1 - Cohort selection" … "Assay 9 - Statistical Analysis", "Assay: Image visualisation" |
| G7 | Mock steps: 3 and 6 use the real five steps; 5: load annotations, fine-tune the skin, outer rib, sternum and lesion models, export models; 7: point cloud generation, mesh fitting; 9: load reports, compute summary statistics, plot results |
| G8 | About **10 s per step**; every step passes |
| G9 | The packages are committed in `examples/workflow/`, and a `util/` populate script imports them and creates and configures the assays |
| G10 | Mocks write **tiny placeholder outputs**, so Submit creates small real datasets |
| G11 | Link ids stay hard-coded (`platformRun.ts`). The demo host gets the platform and its data together later, so the ids match (a separate step, done only on an explicit ask) |

### Pilot study wiring (G5)
| ISA assay | Type | Platform link | Reads (planned ← assay / existing) | Produces |
|---|---|---|---|---|
| Assay 1 - Cohort selection | notebook | 41 | ds-dicom | curated_dataset |
| Assay 2 - Image conversion | script | 42 | ← 1 curated | nifti_output, nrrd_output |
| Assay 3 - Initial inference | script | new mock | ← 2 nifti; pretrained models (existing) | skin, outer_rib, sternum, lesion segmentations |
| Assay 4 - Image annotation | gui | 45 | ← 2 nrrd; ← 3 lesion → `model_predicted_LPS_nii`; the rest as today | today's 12 outputs |
| Assay 5 - Model fine-tuning | notebook | new mock | ← 4 clinician_validated_nii_LPS; pretrained models | fine-tuned models |
| Assay 6 - Inference | script | new mock (same workflow as 3) | ← 2 nifti; ← 5 fine-tuned models | segmentations |
| Assay 7 - Generate breast model | script | new mock | ← 6 skin, outer rib, sternum | point cloud, breast mesh |
| Assay 8 - Lesion position reporting | gui | 45 | ← 7 breast mesh; ← 6 lesion | lesion position report |
| Assay 9 - Statistical Analysis | notebook | new mock | ← 8 report | statistics summary |
| Assay: Image visualisation | gui | 43 | ds-dicom only | volview_output |

### Defaults (not asked; flagged for review)
- **Platform side:**
  - 4 mock workflow packages: `workflow_mock_inference` (script, shared by 3 and 6), `workflow_mock_model_finetuning` (notebook), `workflow_mock_breast_model` (script) and `workflow_mock_statistical_analysis` (notebook).
  - 5 new SEEK assays in the "Breast pilot mockups" study, titled "Mock Assay 3: initial inference", "Mock Assay 5: model fine-tuning", "Mock Assay 6: inference", "Mock Assay 7: generate breast model" and "Mock Assay 9: statistical analysis".
- **Platform inputs are fixed**, as for 41 to 45: each mock reads existing datasets that have samples for cohort {1}.
  - Inference: test_converted, `nifti` sample type, plus the existing pretrained models dataset.
  - The others: test_curated_dataset, `pre`.
  - A mock doesn't read what the previous assay just submitted. The pilot study's existing note already says this.
- **Script mock DAG:**
  - Follows `docs/workflow-dag-authoring.md`, with `dag_id = Path(__file__).parent.name`.
  - Has one task per step with the real task names; each task runs `time.sleep(10)`.
  - The last task writes a small text file to each `conf["output_prefixes"][name]`, as `services/airflow/dags/workflow_9000.py` does.
  - The CWL has one tool CWL per step, so the package validates (`services/api/src/digitaltwins/workflows/validation.py`).
- **Notebook mock:** one cell per step, each with a markdown title and `time.sleep(10)`. The last cell writes a minimal SDS folder to `outputs/datasets/<name>/`.
- **Stored examples get replaced.** The example gets a version number, and `ensureExamples()` replaces any stored example whose version is older. Uploaded projects are kept. This way a browser that already has the old example picks up the new one.
- Assay 8 and Assay 4 share platform assay 45. Their ISA statuses stay separate.
- No ADR: the prototype is throwaway.

## Steps (TDD: write the failing spec first for each frontend step)
1. **Plan folder** `docs/plans/2026-11-20-<HHMMSS>-breast-pilot-nine-assays/` with `plan.md` and `tasks.md`; sync it after every doc change.
2. **Mock workflow packages** in `examples/workflow/workflow_mock_*`. The SDS root files are copied from `workflow_image_conversion`; the packages hold `primary/*.cwl`, `code/` and a README.
   → Verify with the package validator (`validate_workflow_package` in `validation.py`, run in a throwaway API test container), and add a small API test that validates every `examples/workflow/workflow_mock_*`.
3. **Populate script** `util/populate-isa-mock-assays.sh`, modelled on `util/populate-cpu-burn-assay.sh` and using the same password-grant auth from env vars. For each package it:
   - imports it (`POST /api/datasets?category=workflows&workflow_type=…&seek_project_id=12`; admin, so it auto-deploys);
   - first, once: creates the "Breast pilot mockups" SEEK study in investigation 10, with a project-visible policy;
   - creates the SEEK assay in that study with one type tag and a project-visible policy;
   - configures it (`POST /api/assays` with `link_workflow: true`);
   - prints the new SEEK assay ids.

   Add it to `util/SCRIPTS.md`. **Running it changes local platform data** (local only).
   → Verify that the DAGs appear in Airflow, that each script mock's Launch → Monitor → Submit works, and that each notebook mock stages into JupyterHub.
4. **Fixture** `fixtures/example-breast-pilot.json`:
   - The pilot study gets 10 assays wired as in the table.
   - A new study `s-image-pipeline-test`, "Image pipeline test", holds the original 4 assays with new ids (`a-test-*`) and their original titles and links.
   - `fixtures/catalogue.json` gains the mock workflows, their steps and tools, and the datasets for pretrained models, fine-tuned models, segmentations, the breast model, the report and the statistics.
   → Update `isaProjectSource.spec.ts`, `StudyGraph.spec.ts`, `StudyDesign.spec.ts`, `IsaProjectHub.spec.ts` ("1 investigation, 2 studies, 14 assays"), `BundleUploadDialog.spec.ts` and `StudyChain.spec.ts`.
5. **Links** `platformRun.ts`: map every linked ISA assay in both studies to its SEEK id. The new mock ids come from step 3; Assay 4 and Assay 8 both map to 45.
   → `platformRun.spec.ts`.
6. **Example refresh** in `isaProjectStore.ts` (the version bump described above).
   → Store spec: a stored old example is replaced, and an uploaded project is kept.
7. **Layout check (design pass):**
   - The pilot study's Flow view is 9 columns deep, and `place()` pans below zoom 0.7.
   - Check in a headless Firefox screenshot that the chain reads well and the standalone visualisation card sits apart in column 1. Adjust only the layout constants if needed. List view needs no change.
8. **Docs:**
   - `docs/glossary.md`: the ISA project row covers the two studies and the mock assays.
   - `services/airflow/README.md` or `examples/` README: a line about the mock workflows.
   - `util/SCRIPTS.md`.
9. **Rebuild** `portal-frontend` locally (`docker compose up -d --build --no-deps portal-frontend`).

## Verification
- `make test-frontend`, `make test-api` (the package validation test), `make lint`, `make docs-check` (after `git add`), and `make gitleaks`.
- Headless Firefox as admin, at `/study-dashboard` → Breast → Breast Radiology Report:
  - The pilot study shows 10 cards and the Flow edges as in the table.
  - Launching Assay 3 gives a Monitor link to Airflow, where 5 tasks each take about 10 s and succeed. Submit then unlocks the next assays.
  - Assay 5 opens JupyterHub with the mock notebook.
  - "Image pipeline test" shows the original 4 assays and their flow.
  - `/study-dashboard-platform?trail=5,11,8,9` is unchanged.
- Commit only on an explicit ask. Ask again before pushing, and before moving the platform and its data to the demo host.

## Outcome (what changed from the plan while building)
- **Assay 8 uses the lesion curator's ports** (it reuses Assay 4's GUI tool). It reads `contrast_pre_nrrd`
  ← Assay 2, `model_predicted_LPS_nii` ← Assay 6's lesion segmentation and `breast_surface_glb` ← Assay 7's
  breast mesh; the rest as Assay 4. Its outputs fill `lesion_position_report`, and Assay 9 reads that dataset's
  `mask_meta_json`.
- **The standalone image visualisation reads the existing `converted` dataset**, which is what its platform assay
  (43) is configured with, so it doesn't share a source node with Assay 1 in the Flow view.
- **Example ids:** the pilot keeps `a-cohort`, `a-convert`, `a-breast-app` and `a-visualise` and adds
  `a-initial-inference`, `a-finetune`, `a-inference`, `a-breast-model`, `a-lesion-report` and `a-statistics`.
  The "Image pipeline test" study uses `a-pipeline-*` (assay ids must be unique across studies).
- **Platform outputs are all `measurements`.** The ISA fixture shows the fine-tuned models as a `models`
  dataset, so Assay 6's model inputs can read it.
- **The notebook mocks copy their input dataset** to `outputs/datasets/<output>/` (plus a note in `docs/`),
  so Submit uploads a valid SDS dataset without extra packages.
- **`make test-api` now mounts `examples/workflow` read-only**, for `tests/test_example_workflows.py`, which checks
  every example package registers and deploys as is.
- **The study dashboard passes platform links only for the open study's assays** (the link table now covers both
  studies).
- **The stored example is replaced when its release changes** (`EXAMPLE_RELEASE` in `adapter/isaProjectSource.ts`);
  edits to the old example are dropped, uploads are kept.
- The new SEEK assay ids come from running the populate script locally; they are in `platformRun.ts`. The demo
  host needs the same platform data (deployed with it) for those ids to match.
- The Flow view of the 9-assay pilot needs panning, as the 4-assay study did; the layout constants are unchanged.
