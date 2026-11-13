# Walkthrough: Clinician dashboard study list

The clinician dashboard now opens on a list of studies. Opening a study shows its worklist. The prototype has
one study, **Breast MRI reading**, which holds the existing 36 example cases.

## What changed

- `/clinician-dashboard` (`ClinicianDashboard`) shows `StudyListView.vue`. Each study is one row and one link.
  A row shows the study name, its purpose, "N of 36 reviewed" with a progress bar, "N to review" and the date
  of the last decision. The counts come from the same browser store as the worklist, so a decision shows up on
  the list straight away.
- `/clinician-dashboard/studies/:studyId` (`ClinicianStudyWorklist`) shows `WorklistsView.vue`, which takes
  `studyId` as a prop.
  - The "Project" switcher is gone. In its place are an "All studies" back link and the study name.
  - An unknown id shows "There is no study called <id>." and a link back.
- `/worklists` still redirects to `/clinician-dashboard`. The nav bar shows "Clinician Dashboard" on both pages.
- The fixture has a `study` (id `breast-mri-reading`) in place of `project`. The store exports it as `STUDY`
  and no longer persists a title, so a title saved in the browser earlier can't override the new one.
- `lastDecision(cases)` in `model/worklist.ts` gives the latest date on a decided case.
- Glossary: a worklist holds the cases of one *study*, and a review decision is shared by the study. The code map
  and the portal README describe the list.

## Verified

- `make test-frontend`: all 70 test files pass. The new tests cover `lastDecision`, `StudyListView`, the back
  link, the unknown study, and both routes.
- `make lint` and `make docs-check` pass with no problems.
- Rebuilt and restarted `portal-frontend`. Headless Firefox screenshots confirmed:
  - `/worklists` lands on the list;
  - the row opens the study's worklist;
  - confirming a case and going back moves the list to 16 of 36;
  - at 390px wide the page has no horizontal scroll.

## Follow-up: slice preview in the review panel

The review panel shows an image again: a drawn axial breast MRI slice with the annotation outlined in cyan,
labelled with the case's middle slice ("Slice 56 / 112"). It is `components/SlicePreview.vue`. The drawing is
a stand-in, not the case's scan; the prototype has no images. It had been dropped from the original mockup.
A test in `WorklistsView.spec.ts` checks that it follows the case under review.

The slice image and the annotation outline both follow the case number, so each case looks different. For the
image, that means the tissue's width and depth, the bright patch and the strands. For the outline, its place,
size and shape, as in the first mockup. A test checks that two cases get a different image and outline. On all
36 example cases, every outline fits inside the tissue.
