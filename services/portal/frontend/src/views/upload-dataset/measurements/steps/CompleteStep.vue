<template>
  <!-- Phase 7 stub — replaced in the CompleteStep commit. -->
  <div class="pa-4">
    <h3 class="text-cyan">Complete</h3>
    <p class="text-caption">Step 3 implementation pending (Task 7.1-7.4).</p>
  </div>
</template>

<script setup lang="ts">
import type { MeasurementResponse } from '@/models/types';

defineProps<{ measurement: MeasurementResponse }>();
defineEmits<{
  (e: 'backToAnnotation'): void;
  (e: 'done'): void;
  (e: 'retried', m: MeasurementResponse): void;
}>();
</script>
