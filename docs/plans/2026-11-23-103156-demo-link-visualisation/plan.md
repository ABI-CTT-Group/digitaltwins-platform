# Demo: link "Image visualisation" after "2. Image conversion"

## Context

In the prototype study page (`/study-dashboard`, Te Whatu Ora Breast Pilot), "Image visualisation"
(`a-visualise`) stands alone. Its one input reads the existing dataset `ds-converted`, so the graph
draws no edge into it. The user wants it to follow "2. Image conversion" and to have nothing after
it.

Decisions:
- The input `dicom_file` reads the planned `a-convert/nifti_output`, as `a-pipeline-visualise` already
  does in the Image pipeline test study. VolView opens NIfTI.
- The title stays "Image visualisation" (unnumbered); the edge from step 2 shows where it sits.
- No step reads `a-visualise`'s output, so it has no next step. This is already true, and a test
  keeps it so.
- Its platform link (`a-visualise` → SEEK assay 43 in `platformRun.ts`) stays. Launch runs the
  platform assay's own saved configuration, so no platform data changes.
- In the sandbox, the input now shows as planned ("Will be produced by 2. Image conversion") until
  step 2's outputs are submitted, like the other steps that read step 2.

## Steps (TDD)

Plan folder: `docs/plans/<YYYY-MM-DD-HHMMSS>-demo-link-visualisation/` with `plan.md` and `tasks.md`.
Tick each task as its check passes, and sync after every doc edit.

1. **Red:** in `__tests__/isaProjectSource.spec.ts` ("lays the pilot study out …"):
   - Rename the test: the visualisation now follows image conversion.
   - Add `"a-convert/nifti_output -> a-visualise/dicom_file"` to the `planned(study)` list, at the
     end (fixture order).
   - Change the `visualise.inputs` expectation to the planned source.
   - Keep the assertion that no step reads `a-visualise`.

   Then check the other specs that load the example (`StudyChain`, `StudyDesign`, `StudyGraph`,
   `AssayPanel`, `isaProjectStore`) for expectations about the standalone visualise, edge counts, or
   graph layout.
   → verify: `make test-frontend` fails on exactly those expectations.
2. **Green:**
   - Fixture `fixtures/example-breast-pilot.json`: change `a-visualise`'s input source to
     `{ "kind": "planned", "assayId": "a-convert", "port": "nifti_output" }`.
   - `adapter/isaProjectSource.ts`: bump `EXAMPLE_RELEASE` 4 → 5, so every browser, the demo host's
     included, reloads the example. Local sandbox edits to the example are reset; uploads are kept.
   → verify: `make test-frontend` passes; `make lint` passes.

   What changed: the example no longer reads the existing dataset `ds-converted` anywhere, so its
   bundle carries 4 datasets, not 5. `isaBundleWriter.spec.ts` and `BundleUploadDialog.spec.ts`
   count one dataset fewer.
3. Rebuild and restart `portal-frontend` only, locally:
   `docker compose build portal-frontend && docker compose up -d --no-deps portal-frontend`.
   → verify: a headless Firefox screenshot of the study page shows an edge from "2. Image conversion"
   to "Image visualisation", and no edge out of it. The side panel shows the input as planned from
   step 2.

## Not in this plan

- Deploying to the demo host, and committing: each needs a separate request. Deploying means pulling
  on the demo checkout and rebuilding `portal-frontend` there; no data swap is needed.

## Critical files

- `services/portal/frontend/src/views/isa-project/fixtures/example-breast-pilot.json` (`a-visualise`)
- `services/portal/frontend/src/views/isa-project/adapter/isaProjectSource.ts` (`EXAMPLE_RELEASE`)
- `services/portal/frontend/src/views/isa-project/__tests__/isaProjectSource.spec.ts`
