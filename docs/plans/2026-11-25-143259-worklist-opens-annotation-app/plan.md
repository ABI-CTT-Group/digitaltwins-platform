# Open the annotation app from the clinician worklist

Status: done

Branch: prototype

## Context

On the clinician worklist (`/study-dashboard/reviews/breast-mri-reading`), Start only begins a batch of
cases in the review panel, and each case's "Open in annotator" only says the annotator isn't connected
yet. Both should open the annotation app: the GUI tool of the platform assay behind the example's
"4. Image annotation" step, SEEK assay 45, at `/tool-view?assay=45`.

## Steps

1. Change the worklist tests: Start opens `/tool-view?assay=45` in a new tab and still starts the batch;
   a batch size that isn't valid opens nothing; "Open in annotator" opens the same page.
2. In `WorklistsView.vue`, open that page from `start()` once the batch has started, and from the review
   panel's `open` event, in place of the "isn't connected yet" message.

## Decisions

- Start does both: it opens the app in a new tab, as Launch does on the dashboard, and keeps the batch
  so decisions are still recorded in the worklist (chosen by the user).
- "Open in annotator" opens the same app (chosen by the user). The app opens on the assay's own cohort,
  not on the chosen case, and the batch size isn't passed to it.
- The assay id 45 is hard-coded, like the ids in `views/isa-project/platformRun.ts`; it is the same on
  this host and the demo host. Before a merge to main this needs the same treatment as those ids.
