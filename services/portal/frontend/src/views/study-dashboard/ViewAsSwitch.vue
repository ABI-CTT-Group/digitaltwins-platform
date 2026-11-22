<template>
  <div v-if="views.length > 1" class="viewas-row">
    <fieldset class="viewas" data-test="view-as">
      <legend class="viewas__legend">View as</legend>
      <div class="viewas__track">
        <label v-for="v in views" :key="v" class="viewas__option">
          <input
            type="radio"
            name="study-dashboard-view"
            :value="v"
            :checked="v === modelValue"
            :data-test="`view-as-${v}`"
            @change="emit('update:modelValue', v)"
          />
          <span>{{ LABELS[v] }}</span>
        </label>
      </div>
    </fieldset>
  </div>
</template>

<script setup lang="ts">
import type { DashboardView } from "./dashboardView";

defineProps<{ views: DashboardView[]; modelValue: DashboardView }>();
const emit = defineEmits<{ "update:modelValue": [view: DashboardView] }>();

const LABELS: Record<DashboardView, string> = { clinician: "Clinician", researcher: "Researcher" };
</script>

<style scoped>
.viewas-row { display: flex; justify-content: flex-end; margin-bottom: 20px; }
.viewas {
  display: flex; align-items: center; gap: 12px;
  margin: 0; padding: 0; border: 0; min-width: 0;
  font-family: var(--font-ui);
}
.viewas__legend {
  float: left; padding: 0;
  font-size: 0.85rem; color: var(--text-faint);
}
.viewas__track {
  display: flex; height: 36px; padding: 3px;
  border: 1px solid var(--line); border-radius: 999px;
  background: var(--surface);
}
.viewas__option { position: relative; display: flex; }
.viewas__option input {
  position: absolute; inset: 0; opacity: 0; margin: 0; cursor: pointer;
}
.viewas__option span {
  display: flex; align-items: center; padding: 0 16px;
  border-radius: 999px;
  font-size: 0.9rem; color: var(--text-faint);
  transition: background-color 150ms ease, color 150ms ease;
}
.viewas__option:hover span { color: var(--text-dim); }
.viewas__option input:checked + span {
  background: color-mix(in srgb, var(--accent-tools) 16%, transparent);
  color: var(--accent-tools); font-weight: 600;
}
.viewas__option input:focus-visible + span { outline: 2px solid var(--accent-tools); outline-offset: 2px; }

@media (max-width: 600px) {
  .viewas-row { justify-content: flex-start; }
  .viewas { flex: 1; }
  .viewas__track { flex: 1; }
  .viewas__option { flex: 1; }
  .viewas__option span { flex: 1; justify-content: center; }
}
@media (prefers-reduced-motion: reduce) {
  .viewas__option span { transition: none; }
}
</style>
