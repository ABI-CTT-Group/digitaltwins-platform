<template>
  <!-- Asked for on 2026-11-23: unlike the researcher view, nothing in the clinician view runs on the platform. -->
  <p class="mockup" role="note" data-test="mockup-note">
    <strong>Mock-up.</strong> The cases and scans are examples, not real patients, and your decisions stay in this browser.
  </p>
</template>

<style scoped>
/* A dashed edge, like a sketch, on pages whose other borders are all solid. No colour: on these pages
   amber already means "to review" and "needs correction". */
.mockup {
  margin: 20px 0 0; padding: 10px 14px; max-width: 62ch;
  border: 1px dashed color-mix(in srgb, var(--text-dim) 45%, transparent); border-radius: 8px;
  color: var(--text-dim); font-size: 0.9rem; line-height: 1.5;
}
.mockup strong { color: var(--text); font-weight: 600; }
</style>
