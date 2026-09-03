# Disabling Verify and Monitor Buttons

This walkthrough covers the changes made to the "Verify" and "Monitor" buttons in the dashboard.

## Changes Made

### 1. Verify Button
- The "Verify" button is now permanently disabled.
- Added a tooltip over the button that displays "Verify is not implemented yet" to inform users why it cannot be clicked.

### 2. Monitor Button
- The "Monitor" button now conditionally checks if the given assay is a "script" type.
- If the assay is not a script, the button is disabled.
- Added a tooltip over the button that displays "Monitor is only available for script assays" when it is disabled.

### 3. State Passing
- Updated both the dashboard view (`AssayCard.vue`) and the detail view (`AssayReportView.vue`) to calculate an `isScript` boolean based on the assay's workflow tag and pass it down to the action bar components.

## Testing and Verification
- You can now rebuild the frontend container to test these changes.
- In the dashboard, hover over the disabled Verify button to see the "not implemented" tooltip.
- Hover over the Monitor button on an assay that does not have the "script" tag to see the "only available for script assays" tooltip.
