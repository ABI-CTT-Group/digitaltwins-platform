<template>
  <!-- 6-stage upload progress with current-stage highlight. Purely presentational:
       polls the measurement to a terminal state, then emits done/failed. -->
  <div class="text-center">
    <div class="text-h6 label-aqua mb-2">Submitting "{{ live.name }}"</div>
    <v-progress-linear indeterminate color="#5fd6e8" class="my-3" />
    <div class="d-flex justify-center flex-wrap ga-2 my-3">
      <v-chip
        v-for="(stage, idx) in stages"
        :key="stage.key"
        :color="stageColor(idx)"
        :variant="stageVariant(idx)"
        :prepend-icon="stageIcon(idx)"
      >
        {{ stage.label }}
      </v-chip>
    </div>
    <div class="text-caption text-muted">
      We are pushing your dataset to MinIO and registering it with the FHIR
      server. This usually finishes within a minute.
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount } from 'vue';
import { useGetMeasurement } from '@/bootstrap/measurement_api';
import type {
  MeasurementFailureStage,
  MeasurementResponse,
} from '@/models/types';

const props = defineProps<{ measurement: MeasurementResponse }>();
const emit = defineEmits<{
  (e: 'done', m: MeasurementResponse): void;
  (e: 'failed', m: MeasurementResponse): void;
}>();

// `live` mirrors the latest server view while the 6-stage pipeline runs.
const live = ref<MeasurementResponse>({ ...props.measurement });

// Stage order matches the backend's 5 failure_stage strings.
const stages: Array<{ key: MeasurementFailureStage; label: string }> = [
  { key: 'staging', label: 'Preparing dataset' },
  { key: 'fhir_build', label: 'Building fhir.json' },
  { key: 'upload', label: 'Uploading to storage' },
  { key: 'finalize', label: 'Finalizing endpoint URLs' },
  { key: 'fhir_push', label: 'Registering with FHIR' },
];

// We only know the *current* stage on failure (the server records failure_stage).
// While running, show motion with no specific stage highlighted.
const failureIdx = computed(() => {
  if (!live.value.failureStage) return -1;
  return stages.findIndex((s) => s.key === live.value.failureStage);
});

const stageColor = (idx: number) => {
  if (failureIdx.value === idx) return '#ff6b6b';
  if (failureIdx.value > -1 && idx < failureIdx.value) return '#6fd49a';
  return '#5fd6e8';
};

const stageVariant = (idx: number) => (failureIdx.value === idx ? 'flat' : 'tonal');

const stageIcon = (idx: number) => {
  if (failureIdx.value === idx) return 'mdi-close-circle';
  if (failureIdx.value > -1 && idx < failureIdx.value) return 'mdi-check-circle';
  return 'mdi-circle-outline';
};

let pollHandle: number | undefined;

const isTerminal = (s: string) =>
  s === 'completed' || s === 'submit_failed' || s === 'fhir_failed';

const clearPolling = () => {
  if (pollHandle) {
    window.clearInterval(pollHandle);
    pollHandle = undefined;
  }
};

const poll = async () => {
  try {
    const fresh = await useGetMeasurement(props.measurement.id);
    live.value = fresh;
    if (isTerminal(fresh.status)) {
      clearPolling();
      if (fresh.status === 'completed') emit('done', fresh);
      else emit('failed', fresh);
    }
  } catch (err) {
    console.error('Measurement polling failed:', err);
  }
};

onMounted(() => {
  if (isTerminal(live.value.status)) {
    if (live.value.status === 'completed') emit('done', live.value);
    else emit('failed', live.value);
    return;
  }
  pollHandle = window.setInterval(poll, 1500);
});

onBeforeUnmount(clearPolling);
</script>

<style scoped>
.label-aqua { color: #5fd6e8; }
.text-muted { color: #7f97a1; }
</style>
