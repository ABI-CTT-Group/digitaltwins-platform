# Disable Monitor and Verify Buttons

This plan outlines the approach to conditionally disable the "Monitor" button (only enabling it for "script" assays) and to temporarily disable the "Verify" button with appropriate tooltips explaining the states.

## Proposed Changes

### `frontend/src/views/dashboard/components/AssayActionBar.vue`
- Add an `isScript` boolean to the component's `defineProps`.
- **Monitor Button**:
  - Add `!isScript` to the `:disabled` condition (in addition to `!canMonitor`).
  - Wrap the button in a `<span>` and a `<v-tooltip>` that displays "Monitor is only available for script assays" when `isScript` is false.
- **Verify Button**:
  - Change the `:disabled` condition to `true` permanently for now.
  - Wrap the button in a `<span>` and a `<v-tooltip>` that displays "Verify is not implemented yet".

### `frontend/src/views/dashboard/components/AssayCard.vue`
- Create a new computed property `isScript`: 
  `const isScript = computed(() => (props.data.tag ?? "").toLowerCase().includes("script"));`
- Pass `:is-script="isScript"` to the `<AssayActionBar>` component.

### `frontend/src/views/dashboard/report/AssayReportView.vue`
- Create a new computed property `isScript`: 
  `const isScript = computed(() => (detail.value?.workflow.type ?? "").toLowerCase().includes("script"));`
- Pass `:is-script="isScript"` to the `<AssayActionBar>` component.

## Verification Plan

### Manual Verification
- **AssayCard (Dashboard)**: Check non-script assays. The Monitor button should be disabled, and hovering over it should display the "only available for script assays" tooltip. For script assays, it should behave as before.
- **AssayReport (Detail View)**: Check the same behavior on the detail page.
- **Verify Button**: On all assays, the Verify button should be disabled, and hovering over it should display the "not implemented yet" tooltip.
