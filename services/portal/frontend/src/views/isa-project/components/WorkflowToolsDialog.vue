<template>
  <v-dialog :model-value="modelValue" max-width="1000" @update:model-value="(v: boolean) => emit('update:modelValue', v)">
    <v-card v-if="workflow" class="wf-dialog">
      <v-card-title class="wf-dialog__title">{{ workflow.name }}</v-card-title>
      <v-card-subtitle>Each box is a step that runs one tool. Arrows show how data flows between steps.</v-card-subtitle>
      <v-card-text>
        <CWLWorkflowViewer :workflow="workflow.cwl" />
      </v-card-text>
      <v-card-actions>
        <v-spacer />
        <v-btn variant="text" @click="emit('update:modelValue', false)">Close</v-btn>
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import CWLWorkflowViewer from "@/components/domain/workflow/CWLWorkflowViewer.vue";
import type { CatalogueWorkflow } from "../model/types";

defineProps<{ modelValue: boolean; workflow: CatalogueWorkflow | null }>();
const emit = defineEmits<{ (e: "update:modelValue", v: boolean): void }>();
</script>

<style scoped>
.wf-dialog__title { font-family: var(--font-title); font-weight: 500; }

/* CWLWorkflowViewer builds its step nodes with a render function, so its own scoped styles never
   reach them; style them here so each step (one tool) is readable. */
.wf-dialog :deep(.step-node) {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 160px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--line);
  border-left: 4px solid var(--accent-tools);
  background: #0d2230;
  color: var(--text);
}
.wf-dialog :deep(.step-label) { flex: 1; text-align: center; font-weight: 600; }
.wf-dialog :deep(.port-container) { display: flex; flex-direction: column; gap: 6px; }
</style>
