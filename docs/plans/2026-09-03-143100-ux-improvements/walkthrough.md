# UX Improvements for Download and Submit Buttons

This walkthrough covers the UI/UX changes made to the assay action bar, implementing inline loading states and establishing a visual hierarchy.

## Changes Made

### 1. State Tracking in `useAssayActions`
- Added two reactive maps: `downloadingMap` and `submittingMap` to track the state of individual assays by their `seekId`.
- The `download` and `submit` functions now actively toggle these states before and after API calls using `finally` blocks, while maintaining the toast notifications for status updates.

### 2. Enhanced `AssayActionBar` Component
- Introduced new `downloading` and `submitting` boolean properties.
- **Visual Hierarchy**: 
  - Primary actions (**Launch**, **Monitor**) now feature a solid green background (`.btn--primary`) to draw immediate attention.
  - Secondary actions (**Verify**, **Download**, **Submit**) use an outlined, tonal style (`.btn--secondary`) to signify they are alternative or lower-priority actions.
- **Inline Feedback**: The Download and Submit buttons dynamically render a `<v-progress-circular>` spinner when their respective loading prop is `true`, and they update their text (e.g. from "Download" to "Downloading...").
- **Double-Click Prevention**: The buttons are now dynamically disabled while the respective operation is in progress.

### 3. Prop Bindings
- Updated `AssayCard.vue` to pass `downloading` and `submitting` values from `useAssayActions` mapped to the specific `seekId` of the card.
- Updated `AssayReportView.vue` similarly so that the deep-linked assay report also benefits from inline loading states.

## Testing and Verification
- Navigating to the dashboard or an assay report will now reveal clearly distinct primary and secondary buttons.
- Triggering a download or submission will immediately disable the button for that specific assay, show a spinner, and display the toast notification, successfully handling background progress gracefully.
