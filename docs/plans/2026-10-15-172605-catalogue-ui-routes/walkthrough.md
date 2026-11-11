# Walkthrough: catalogue UI routes, titles and source default

## Request

- Move the catalogue pages under `/catalogue`.
- Drop "Hub" from the page titles.
- In the tool and workflow registration forms, show *Local Folder* first and select it by default.
- Label the tool form's name field "Tool Name *".
- Remove the "DigitalTWINS · AI Platform" eyebrow from the catalogue page.
- Update the existing docs to match.
- Follow-up:
  - Fix the "Workflow assembler" card. Its `herf` (`WorkflowToolsViewer`) named no route, so the card did nothing when clicked. It was briefly marked *Coming soon*; the final change is below.
  - Use "My Workflow Name" as the workflow form's name placeholder.
  - Move the unlinked prototype page `/catalogue-dashboard-tools` (route `ToolsViewer`) to `/catalogue/workflow-assembler`. Open it from the assembler card, which shows a *Prototype* badge.
  - Redirect the bare `/upload-dataset` parent route, which rendered a blank page, to `/catalogue`.

## Changes

| Before | After |
|---|---|
| `/catalogue-dashboard` | `/catalogue` |
| `/upload-dataset/measurements` | `/catalogue/measurements` |
| `/upload-dataset/measurements/:id/preview` | `/catalogue/measurements/:id/preview` |
| `/upload-dataset/models` | `/catalogue/models` |
| `/upload-tool-dataset` | `/catalogue/tools` |
| `/upload-workflow-dataset` | `/catalogue/workflows` |
| Measurements Hub / Models Hub / Tool Hub / Workflow Hub | Measurements / Models / Tools / Workflows |
| Source radio: Git URL (default), Local Folder | Local Folder (default), Git URL |
| Tool form: "Workflow Name *" | "Tool Name *" (the workflow form keeps "Workflow Name *") |
| Workflow form placeholder: "My Tool Name" | "My Workflow Name" |
| `/catalogue-dashboard-tools` (prototype, not linked) | `/catalogue/workflow-assembler` |
| `/upload-dataset` (blank page) | redirects to `/catalogue` |
| "Workflow assembler" card: Open (broken link) | *Prototype* badge; opens `/catalogue/workflow-assembler` for any signed-in user |

- Pages link to each other by route name, so only [router/index.ts](../../../services/portal/frontend/src/router/index.ts) changes paths. The old paths are not redirected. Nothing in the repository (nginx, backends, Keycloak, docs other than ADRs and artifacts) links to them, so only external bookmarks are affected.
- The FHIR preview path moved with its Measurements page; the request did not name it.
- `CommonInfoForm` takes a `type` prop (`tool` | `workflow`) from `BaseInformationStep` to pick the name label.
- The approval dialog's "the Tool/Workflow Hub keeps it going" now says "the Tools/Workflows page keeps it going".
- The docs updated are `docs/populating_data.md`, `docs/workflow-dag-authoring.md`, `examples/workflow/workflow_image_conversion/README.md` and `services/portal/README.md` (source table order and default).
- ADRs (`docs/decisions/`) and earlier artifacts keep the old names, because they are point-in-time records.
- Code identifiers such as `useToolHub` and the test descriptions are unchanged.

## Verification

- New specs: `router/__tests__/catalogue_routes.spec.ts`, `components/__tests__/CommonInfoForm.spec.ts` and `catalogue/__tests__/catalogue-dashboard-view.spec.ts`, plus a default-source case in `BaseInformationStep.spec.ts`. They failed before the change.
- Existing `BaseInformationStep` tests that drive the git path now set the source to git explicitly.
- Full vitest suite: 29 files, 151 tests pass. `vite build` succeeds. vue-tsc reports 14 errors, the pre-existing baseline, none of them in the changed files.
