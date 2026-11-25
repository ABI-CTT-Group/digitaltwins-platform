# Remove the mock-up note from the clinician view

Status: done

Branch: prototype

## Context

The clinician view of the study dashboard (`/study-dashboard?view=clinician`) and each study's worklist
(`/study-dashboard/reviews/<id>`) show a dashed note: "Mock-up. The cases and scans are examples, not real
patients, and your decisions stay in this browser." It was added on 2026-11-23. The note is no longer wanted
on these pages, so both pages drop it.

## Steps

1. Change the two view tests so they expect no mock-up note on the study list or the worklist.
2. Remove `MockupNote` from `StudyListView.vue` and `WorklistsView.vue`, and delete
   `views/worklists/components/MockupNote.vue`, which nothing else uses.

## Decisions

- Developer docs (`docs/codemap.md`, `services/portal/README.md`) still call the clinician view a mock-up.
  That describes the code (example cases in the browser), not what the page shows, so they stay.
