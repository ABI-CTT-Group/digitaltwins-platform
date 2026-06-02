<template>
  <!-- Uploading: 4-stage progress with current-stage highlight -->
  <v-card v-if="status === 'uploading' || status === 'pending'" variant="tonal" color="cyan-darken-3" class="pa-5 text-center">
    <div class="text-h6 text-cyan-lighten-2 mb-2">Submitting "{{ live.name }}"</div>
    <v-progress-linear indeterminate color="cyan" class="my-3" />
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
    <div class="text-caption text-cyan-lighten-3">
      We are pushing your dataset to MinIO and registering it with the FHIR
      server. This usually finishes within a minute.
    </div>
  </v-card>

  <!-- Completed -->
  <v-card v-else-if="status === 'completed'" variant="tonal" color="cyan-darken-3" class="pa-5 text-center">
    <v-icon size="80" color="green-lighten-1" class="mb-3">mdi-check-circle-outline</v-icon>
    <div class="text-h5 text-green-lighten-3 mb-2">"{{ live.name }}" is ready</div>
    <div class="text-caption text-grey-lighten-1 mb-4">
      Dataset uploaded to MinIO and registered on FHIR.
    </div>
    <div class="d-flex justify-center ga-2">
      <v-btn variant="tonal" color="cyan" prepend-icon="mdi-check" @click="emit('done')">
        Done
      </v-btn>
    </div>
  </v-card>

  <!-- submit_failed: stages 1-3 failed; user goes back to Annotation -->
  <v-card v-else-if="status === 'submit_failed'" variant="tonal" color="amber-darken-3" class="pa-5">
    <v-icon size="60" color="amber-lighten-1" class="mb-2">mdi-alert-circle-outline</v-icon>
    <div class="text-h6 text-amber-lighten-3 mb-1">Upload couldn't complete</div>
    <div class="text-caption text-amber-lighten-4 mb-3">
      Stage failed: <strong>{{ stageLabel(live.failureStage) }}</strong>
    </div>
    <v-alert
      v-if="live.failureMessage"
      type="warning"
      variant="tonal"
      class="mb-3"
    >
      <pre class="failure-msg">{{ live.failureMessage }}</pre>
    </v-alert>
    <div class="d-flex flex-wrap ga-2">
      <v-btn variant="tonal" color="cyan" prepend-icon="mdi-arrow-left" @click="emit('backToAnnotation')">
        Back to annotation
      </v-btn>
      <v-btn
        variant="tonal"
        color="amber"
        prepend-icon="mdi-refresh"
        :loading="retrying"
        @click="handleRetrySubmit"
      >
        Retry submit
      </v-btn>
    </div>
  </v-card>

  <!-- fhir_failed: stages 4-6 failed; MinIO retained; retry inline -->
  <v-card v-else-if="status === 'fhir_failed'" variant="tonal" color="amber-darken-3" class="pa-5">
    <v-icon size="60" color="amber-lighten-1" class="mb-2">mdi-database-alert-outline</v-icon>
    <div class="text-h6 text-amber-lighten-3 mb-1">Dataset stored, FHIR registration failed</div>
    <div class="text-caption text-amber-lighten-4 mb-3">
      Stage failed: <strong>{{ stageLabel(live.failureStage) }}</strong>
    </div>
    <div class="d-flex flex-column ga-1 mb-3">
      <div
        v-for="stage in stages"
        :key="stage.key"
        class="d-flex align-center ga-2"
      >
        <v-icon
          :color="stage.key === live.failureStage ? 'red' : 'green-lighten-1'"
          size="20"
        >
          {{ stage.key === live.failureStage ? 'mdi-close-circle' : 'mdi-check-circle' }}
        </v-icon>
        <span class="text-caption">{{ stage.label }}</span>
      </div>
    </div>
    <v-alert
      v-if="live.failureMessage"
      type="warning"
      variant="tonal"
      class="mb-3"
    >
      <pre class="failure-msg">{{ live.failureMessage }}</pre>
    </v-alert>
    <div class="d-flex flex-wrap ga-2">
      <v-btn
        variant="tonal"
        color="amber"
        prepend-icon="mdi-refresh"
        :loading="retrying"
        @click="handleRetryFhir"
      >
        Retry FHIR registration
      </v-btn>
      <v-btn variant="text" color="cyan" prepend-icon="mdi-view-list" @click="emit('done')">
        View in registry
      </v-btn>
    </div>
  </v-card>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onBeforeUnmount, watch } from 'vue';
// @ts-ignore - vue-toastification ships without type declarations
import { useToast } from 'vue-toastification';
import {
  useGetMeasurement,
  useMeasurementRetryFhir,
  useMeasurementSubmit,
} from '@/bootstrap/measurement_api';
import type {
  MeasurementFailureStage,
  MeasurementResponse,
} from '@/models/types';

const props = defineProps<{ measurement: MeasurementResponse }>();
const emit = defineEmits<{
  (e: 'backToAnnotation'): void;
  (e: 'done'): void;
  (e: 'retried', m: MeasurementResponse): void;
}>();

const toast = useToast();

// `live` mirrors the latest server view of the measurement — props are the
// snapshot at entry, but submit / retry flips the row server-side and we want
// the UI to follow.
const live = ref<MeasurementResponse>({ ...props.measurement });
const retrying = ref(false);

const status = computed(() => live.value.status);

// Stage order matches the backend's 5 failure_stage strings. We collapse
// staging + fhir_build into a single user-facing chip ("Preparing fhir.json")
// because the user can't act on the difference between them and surfacing
// both makes the bar feel busier than it needs to be.
const stages: Array<{ key: MeasurementFailureStage; label: string }> = [
  { key: 'staging', label: 'Preparing dataset' },
  { key: 'fhir_build', label: 'Building fhir.json' },
  { key: 'upload', label: 'Uploading to storage' },
  { key: 'finalize', label: 'Finalizing endpoint URLs' },
  { key: 'fhir_push', label: 'Registering with FHIR' },
];

const stageLabel = (key?: string | null): string =>
  stages.find((s) => s.key === key)?.label || key || 'Unknown stage';

// Heuristic for the in-progress UI: we don't have a server-side "current
// stage" while running, only on failure. Treat any uploading row as "in
// flight on the first as-yet-unfailed stage", giving the user a sense of
// motion even if we can't pinpoint exactly which stage is running.
const failureIdx = computed(() => {
  if (!live.value.failureStage) return -1;
  return stages.findIndex((s) => s.key === live.value.failureStage);
});

const stageColor = (idx: number) => {
  if (failureIdx.value === idx) return 'red-lighten-2';
  if (failureIdx.value > -1 && idx < failureIdx.value) return 'green-lighten-2';
  return 'cyan-lighten-3';
};

const stageVariant = (idx: number) => {
  if (failureIdx.value === idx) return 'flat';
  if (failureIdx.value > -1 && idx < failureIdx.value) return 'tonal';
  return 'tonal';
};

const stageIcon = (idx: number) => {
  if (failureIdx.value === idx) return 'mdi-close-circle';
  if (failureIdx.value > -1 && idx < failureIdx.value) return 'mdi-check-circle';
  return 'mdi-circle-outline';
};

// Watch props.measurement for parent-triggered changes (e.g. retried path).
watch(
  () => props.measurement,
  (next) => {
    live.value = { ...next };
  },
);

let pollHandle: number | undefined;

const isTerminal = (s: string) =>
  s === 'completed' || s === 'submit_failed' || s === 'fhir_failed';

const poll = async () => {
  try {
    const fresh = await useGetMeasurement(props.measurement.id);
    live.value = fresh;
    if (isTerminal(fresh.status)) {
      clearPolling();
    }
  } catch (err) {
    console.error('Measurement polling failed:', err);
  }
};

const ensurePolling = () => {
  if (pollHandle || isTerminal(live.value.status)) return;
  pollHandle = window.setInterval(poll, 1500);
};

const clearPolling = () => {
  if (pollHandle) {
    window.clearInterval(pollHandle);
    pollHandle = undefined;
  }
};

onMounted(() => {
  if (!isTerminal(live.value.status)) {
    ensurePolling();
  }
});

onBeforeUnmount(clearPolling);

async function handleRetrySubmit() {
  if (retrying.value) return;
  retrying.value = true;
  try {
    const updated = await useMeasurementSubmit(props.measurement.id);
    live.value = updated;
    ensurePolling();
    emit('retried', updated);
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.message || 'Retry failed';
    toast.error(`Retry submit failed: ${detail}`);
  } finally {
    retrying.value = false;
  }
}

async function handleRetryFhir() {
  if (retrying.value) return;
  retrying.value = true;
  try {
    const updated = await useMeasurementRetryFhir(props.measurement.id);
    live.value = updated;
    ensurePolling();
    toast.success('Retrying FHIR registration…');
    emit('retried', updated);
  } catch (err: any) {
    const detail = err?.response?.data?.detail || err?.message || 'Retry failed';
    toast.error(`Retry FHIR failed: ${detail}`);
  } finally {
    retrying.value = false;
  }
}
</script>

<style scoped>
.failure-msg {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.4;
  margin: 0;
  max-height: 200px;
  overflow: auto;
}
</style>
