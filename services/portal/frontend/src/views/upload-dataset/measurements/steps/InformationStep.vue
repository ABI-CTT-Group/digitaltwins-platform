<template>
  <!-- Phase 5 stub — replaced in the InformationStep commit. -->
  <div class="pa-4">
    <h3 class="text-cyan">Information</h3>
    <p class="text-caption">Step 1 implementation pending (Task 5.1-5.2).</p>
  </div>
</template>

<script setup lang="ts">
import type { MeasurementResponse } from '@/models/types';

defineEmits<{
  (e: 'created', m: MeasurementResponse): void;
  (e: 'cancel'): void;
}>();
</script>
