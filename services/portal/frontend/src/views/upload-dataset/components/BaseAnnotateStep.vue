<template>
  <WorkflowAnnotate v-if="type === 'workflow'" :workflow="data" @close="$emit('close')" @annotation-submit="(id, annotation) => $emit('annotation-submit', id, annotation)" />
  <ToolAnnotate v-else :tool="data" @close="$emit('close')" @annotation-submit="(id, annotation) => $emit('annotation-submit', id, annotation)" />
</template>

<script setup lang="ts">
import WorkflowAnnotate from './WorkflowAnnotate.vue';
import ToolAnnotate from './ToolAnnotate.vue';

const props = defineProps<{
  type: 'workflow' | 'tool'
  data: any
}>();

const emit = defineEmits(["close", "annotation-submit"]);
</script>
