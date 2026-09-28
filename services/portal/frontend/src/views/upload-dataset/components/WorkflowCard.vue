<template>
  <CardUI
    :title="workflow.name"
    kind="Workflow"
    accent="#7fb2f0"
    :is-deleting="isDeleting"
    :menu-items="menuItems"
  >
    <template #description>{{ workflow.description || 'No description provided.' }}</template>

    <template #meta>
      <span v-if="workflow.version" class="aurora-chip">v{{ workflow.version }}</span>
      <span v-if="workflow.author" class="aurora-chip">{{ workflow.author }}</span>
      <span v-if="workflow.status" class="aurora-chip" :style="{ '--chip': auroraStatus(workflow.status) }">
        {{ workflow.status }}
      </span>
      <span v-if="workflow.createdAt" class="aurora-chip ms-auto">{{ formatDate(workflow.createdAt) }}</span>
    </template>
  </CardUI>
</template>

<script setup lang="ts">
import { computed, ref, toRef } from 'vue'
import { WorkflowResponse } from '@/models/types';
import CardUI, { type UCardMenuItem } from './CardUI.vue';
import { formatDate } from './utils';

const props = defineProps<{
  workflow: WorkflowResponse
}>()

const workflow = toRef(props, "workflow")
const isDeleting = ref(false)

const emit = defineEmits(["submit-approve", "delete"])

// Aurora status palette — soft tonal chips keyed by lifecycle state.
const auroraStatus = (s?: string) => {
  switch (s) {
    case "pending": return "#ffb74d"
    case "building": return "#5fd6e8"
    case "failed": return "#ff6b6b"
    case "completed": return "#6fd49a"
    default: return "#9fb4bf"
  }
}

const menuItems = computed<UCardMenuItem[]>(() => [
  { label: 'Submit to approval', icon: 'mdi-send-check-outline', onClick: onSubmit },
  { label: 'Delete workflow', icon: 'mdi-trash-can-outline', danger: true, onClick: onDelete },
])

const onSubmit = () => emit("submit-approve", workflow.value.id)
const onDelete = () => {
    isDeleting.value = true;
    emit("delete", workflow.value.id)
}
</script>
