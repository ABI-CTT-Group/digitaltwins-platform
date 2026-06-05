<template>
  <v-card flat class="pa-3 mb-3 patient-card">
    <div class="d-flex align-center justify-space-between mb-2">
      <div class="text-subtitle-2 label-aqua">
        Patients ({{ selected.length }} / {{ patients.length }} selected)
      </div>
      <v-switch
        :model-value="allSelected"
        color="#5fd6e8"
        density="compact"
        hide-details
        :label="allSelected ? 'Deselect all' : 'Select all'"
        @update:model-value="toggleAll"
      />
    </div>

    <div v-if="!patients.length" class="text-caption text-muted">
      No patients to annotate yet.
    </div>

    <div class="d-flex flex-wrap ga-2">
      <v-chip
        v-for="p in patients"
        :key="p"
        :color="selected.includes(p) ? '#5fd6e8' : '#9fb4bf'"
        :variant="selected.includes(p) ? 'flat' : 'tonal'"
        :prepend-icon="selected.includes(p) ? 'mdi-checkbox-marked' : 'mdi-checkbox-blank-outline'"
        @click="toggle(p)"
      >
        {{ p }}
      </v-chip>
    </div>
  </v-card>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = defineProps<{
  patients: string[];
  selected: string[];
}>();

const emit = defineEmits<{
  (e: 'update:selected', next: string[]): void;
}>();

const allSelected = computed(
  () => props.patients.length > 0 && props.selected.length === props.patients.length,
);

const toggle = (name: string) => {
  const next = props.selected.includes(name)
    ? props.selected.filter((p) => p !== name)
    : [...props.selected, name];
  emit('update:selected', next);
};

const toggleAll = (next: boolean | null) => {
  emit('update:selected', next ? [...props.patients] : []);
};
</script>

<style scoped>
.patient-card {
  background: rgba(95, 214, 232, 0.05) !important;
  border: 1px solid rgba(95, 214, 232, 0.2);
}
.label-aqua { color: #5fd6e8; }
.text-muted { color: #7f97a1; }
</style>
