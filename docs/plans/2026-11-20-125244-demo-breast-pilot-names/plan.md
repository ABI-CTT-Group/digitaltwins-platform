# Plan: Demo names for the example ISA project

## Context
For the demo, the example ISA project must read as the Te Whatu Ora breast pilot, with no "test" anywhere
the audience can see (page text, dataset names, URL). UI-only: the portal's example fixture and the
dashboard's programme card. No API, SEEK or database change. The linked platform assays (SEEK 41, 42, 43,
45) keep their SEEK titles ("Test Assay ..."), so pages that come from the platform (Monitor, Airflow,
SEEK) may still say "Test"; the user chose portal text only.

## Decisions
| # | Decision |
|---|---|
| Q1 | Programme "Te Whatu Ora Radiology Reporting"; project "Breast"; investigation "breast Radiology report"; study "Te Whatu Ora Breast Pilot" (as given by the user) |
| Q2 | Assay titles drop "Test " ("Assay 1: cohort selection", ...) |
| Q3 | Dataset names drop "test_" (dicom, curated_dataset, converted, volview_output, data_breast_app, model_breast_app, breast_app_output); dataset ids `ds-test-*` → `ds-*` (they name bundle folders) |
| Q4 | URL ids renamed: programme `te-whatu-ora-radiology-reporting` (was `isa-sandbox`), `p-breast`, `i-breast-radiology-report`, `s-breast-pilot` |
| Q5 | SEEK data untouched (portal text only) |

Defaults: the example's internal id becomes `example-breast-pilot` (fixture file renamed to match), so
browsers holding the old stored copy drop it and load the new one (`ensureExamples` drops examples that no
longer ship). Programme description loses its "nothing here is saved to the platform" caveat, like the notes
removed earlier. The ISA hub keeps its title "ISA projects". Code comments are updated where they name the
example.

## Steps
1. Tests first: the example has no /test/i in any visible title, dataset name or id; programme name and
   breadcrumb names match Q1 (`sandbox.spec.ts`, `isaProjectSource.spec.ts`) → red.
2. Rename across `views/isa-project/` (code, fixtures, tests) and `composables/__tests__/useDashboardData.spec.ts`:
   ids, dataset names, titles, example id and fixture file; programme name/id in `sandbox.ts`;
   `platformRun.ts` key; bundle demo title and `BundleUploadDialog.vue` text → green.
3. Docs: glossary ISA project row (programme name, example name).
4. Rebuild `portal-frontend`; verify `make test-frontend`, `make lint`, `make docs-check`, headless Firefox
   (dashboard trail, study page, no "test"/"prototype" in page text or URL).
5. Commit on explicit ask only.
