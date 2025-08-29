<script setup lang="ts">
import { WorkflowStatus, WorkflowStatusMeta } from "./workflowStatus";

const props = defineProps<{ status: WorkflowStatus }>();

</script>

<template>
  <v-chip
    :color="WorkflowStatusMeta[status].bg"
    :text-color="WorkflowStatusMeta[status].text"
    label
  >
    {{ WorkflowStatusMeta[status].label }}
  </v-chip>
</template>

<style scoped>
</style>