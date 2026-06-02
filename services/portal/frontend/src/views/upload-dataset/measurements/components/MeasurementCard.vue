<template>
  <!-- Phase 8 stub — replaced in the MeasurementCard commit. -->
  <v-card class="pa-3 ma-2" variant="outlined" min-width="280">
    <div class="text-subtitle-2">{{ measurement.name }}</div>
    <div class="text-caption">status: {{ measurement.status }}</div>
  </v-card>
</template>

<script setup lang="ts">
import type { MeasurementResponse } from '@/models/types';

defineProps<{ measurement: MeasurementResponse }>();
defineEmits<{
  (e: 'delete', id: string): void;
  (e: 'retryFhir', id: string): void;
}>();
</script>
