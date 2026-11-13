<template>
  <span class="pill" :class="`pill--${status}`">{{ STATUS_LABEL[status] }}</span>
</template>

<script setup lang="ts">
import { STATUS_LABEL, type ReviewStatus } from "../model/worklist";

defineProps<{ status: ReviewStatus }>();
</script>

<style scoped>
.pill { display: inline-flex; align-items: center; gap: 6px; font-size: 0.8125rem; font-weight: 600; white-space: nowrap; }
.pill::before { content: ""; width: 7px; height: 7px; border-radius: 50%; background: currentColor; }
.pill--review { color: var(--text-dim); }
.pill--review::before { background: transparent; border: 1.5px solid currentColor; }
.pill--confirmed { color: var(--accent-measurements); }
.pill--needs { color: var(--tone-needs); }
</style>
