# UX Improvements for Download and Submit Buttons

This plan outlines the changes to improve the UX of the assay action buttons by adding inline loading states, blocking double-clicks, and establishing a clear visual hierarchy based on our discussion.

## Proposed Changes

### `frontend/src/composables/useAssayActions.ts`
- Add two module-scoped reactive variables: `downloadingMap` and `submittingMap` of type `Record<string, boolean>` to track the loading state per assay `seekId`.
- Update the `download` and `submit` functions to set these states to `true` when starting, and reset them to `false` in a `finally` block.
- Export these maps so components can bind to them.

### `frontend/src/views/dashboard/components/AssayActionBar.vue`
- Add `downloading` and `submitting` boolean props.
- Add `<v-progress-circular>` spinners to the "Download" and "Submit" buttons, bound to these new props.
- Update the `:disabled` attributes for "Download" and "Submit" to also disable when their respective loading state is true.
- **Visual Hierarchy Styling**: 
  - Change the default `.btn` class to an outlined/ghost style (for secondary actions like Verify, Download, Submit).
  - Add a `.btn--primary` class with the current solid green background for the primary actions (Launch, Monitor).
  - Apply the appropriate classes to the buttons.

### `frontend/src/views/dashboard/components/AssayCard.vue`
- Bind the new props to `AssayActionBar`: `:downloading="actions.downloadingMap.value[data.seekId]"` and `:submitting="actions.submittingMap.value[data.seekId]"`.

### `frontend/src/views/dashboard/report/AssayReportView.vue`
- Bind the new props to `AssayActionBar`: `:downloading="actions.downloadingMap.value[assayId]"` and `:submitting="actions.submittingMap.value[assayId]"`.

## Verification Plan

### Manual Verification
- View an assay in the dashboard or report page.
- Check that "Launch" and "Monitor" buttons are solid green, while "Verify", "Download", and "Submit" are outlined.
- Click "Download" and "Submit". Verify that a spinner appears on the button, the button text updates if applicable, the button is disabled during the operation, and the spinner disappears when it completes.
- Ensure that triggering an action on one assay does not trigger the loading state on a different assay.
