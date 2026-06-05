<template>
  <button type="button" class="back-link" :class="{ 'back-link--sticky': sticky }" @click="go">
    <v-icon icon="mdi-arrow-left" size="18"></v-icon>
    <span>{{ label }}</span>
  </button>
</template>

<script setup lang="ts">
import { useRouter } from "vue-router";

// Explicit, labelled "up" navigation. Prefer a DETERMINISTIC parent route via
// `to` (by name) so it can't overshoot. `back` is for true leaf pages that are
// only ever reached by push from one ambiguous parent (e.g. an assay report
// opened from either the study OR clinician dashboard) — there history.back()
// is the correct "return to where I came from". Replaces the old context-blind
// floating BackIcon.
const props = defineProps<{
  label: string;
  to?: string;
  query?: Record<string, unknown>;
  back?: boolean;
  /** Pin the link to the top of the scroll container so it stays reachable as
   *  the page scrolls (opt-in; consumers that don't pass it are unaffected). */
  sticky?: boolean;
}>();

const router = useRouter();
const go = () => {
  if (props.back || !props.to) {
    router.back();
    return;
  }
  router.push({ name: props.to, query: props.query as never });
};
</script>

<style scoped>
.back-link {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 7px 14px 7px 11px;
  border: 1px solid rgba(120, 200, 220, 0.16);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.03);
  color: #a4bac4;
  font-family: "Hanken Grotesk", system-ui, sans-serif;
  font-size: 0.85rem;
  font-weight: 600;
  letter-spacing: 0.01em;
  cursor: pointer;
  transition: color 0.25s ease, border-color 0.25s ease, background 0.25s ease;
}
.back-link:hover {
  color: #e9f2f5;
  border-color: rgba(95, 214, 232, 0.45);
  background: rgba(255, 255, 255, 0.05);
}
/* Pinned variant — sticks just below the navbar while the page scrolls. Opaque
   so scrolling content stays readable behind the pill (no backdrop-filter: the
   bar would re-blur on every scroll frame). */
.back-link--sticky {
  position: sticky;
  top: 12px;
  z-index: 6;
  align-self: flex-start;
  background: rgba(8, 18, 26, 0.92);
  box-shadow: 0 8px 20px -12px rgba(0, 0, 0, 0.7);
}
.back-link--sticky:hover {
  background: rgba(12, 24, 34, 0.95);
}
.back-link .v-icon {
  transition: transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}
.back-link:hover .v-icon {
  transform: translateX(-3px);
  color: #5fd6e8;
}
</style>
