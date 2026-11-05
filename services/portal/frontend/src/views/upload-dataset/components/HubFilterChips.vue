<template>
  <div class="hub-filter" role="group" aria-label="Show">
    <button
      v-for="f in HUB_FILTERS"
      :key="f.value"
      type="button"
      class="hub-filter__chip"
      :aria-pressed="modelValue === f.value"
      @click="emit('update:modelValue', f.value)"
    >
      {{ f.label }}<span v-if="f.value === 'needs' && counts.needs" class="hub-filter__count">{{ ' ' + counts.needs }}</span>
    </button>
  </div>
</template>

<script setup lang="ts">
import { HUB_FILTERS, type HubFilter } from './hubFilter';

defineProps<{ modelValue: HubFilter; counts: Record<HubFilter, number> }>();
const emit = defineEmits<{ (e: 'update:modelValue', value: HubFilter): void }>();
</script>

<style scoped>
.hub-filter { display: flex; flex-wrap: wrap; gap: 6px; }
.hub-filter__chip {
  padding: 6px 12px;
  border-radius: 8px;
  border: 1px solid var(--line);
  background: transparent;
  color: var(--text-dim);
  font-family: var(--font-ui);
  font-size: 0.875rem;
  font-weight: 500;
  cursor: pointer;
  transition: border-color 0.2s ease, color 0.2s ease, background 0.2s ease;
}
.hub-filter__chip:hover { color: var(--text); }
.hub-filter__chip[aria-pressed='true'] {
  border-color: color-mix(in srgb, var(--accent, var(--text)) 55%, transparent);
  background: rgba(255, 255, 255, 0.05);
  color: var(--text);
}
.hub-filter__chip:focus-visible { outline: 2px solid var(--accent, var(--text)); outline-offset: 2px; }
.hub-filter__count { font-variant-numeric: tabular-nums; color: var(--tone-needs); font-weight: 600; }
</style>
