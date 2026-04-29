<template>
  <WorkflowInfo v-if="type === 'workflow'" @cancel="$emit('cancel')" @submit="(data) => $emit('submit', data)" />
  <ToolInfo v-else @cancel="$emit('cancel')" @submit="(data) => $emit('submit', data)" />
</template>

<script setup lang="ts">
import WorkflowInfo from './WorkflowInfo.vue';
import ToolInfo from './ToolInfo.vue';

const props = defineProps<{
  type: 'workflow' | 'tool'
}>();

const emit = defineEmits(["cancel", "submit"]);
</script>
