<template>
  <!-- Phase 6 stub — replaced in the AnnotationStep commit. -->
  <div class="pa-4">
    <h3 class="text-cyan">Annotation</h3>
    <p class="text-caption">Step 2 implementation pending (Task 6.1-6.8).</p>
  </div>
</template>

<script setup lang="ts">
import type { MeasurementResponse } from '@/models/types';

defineProps<{ measurement: MeasurementResponse }>();
defineEmits<{
  (e: 'submitted', m: MeasurementResponse): void;
  (e: 'cancel'): void;
}>();
</script>
