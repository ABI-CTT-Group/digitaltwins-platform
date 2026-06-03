<template>
  <v-dialog
    :model-value="modelValue"
    max-width="560"
    :persistent="phase === 'progress'"
    @update:model-value="onDialogToggle"
  >
    <v-card color="cyan-darken-4" class="pa-2">
      <!-- Confirm: ask before kicking off the upload -->
      <template v-if="phase === 'confirm'">
        <v-card-title class="text-cyan-lighten-2">Approve & upload?</v-card-title>
        <v-card-text>
          <p class="mb-2">
            This will upload <strong>"{{ measurement?.name }}"</strong> to MinIO and
            register it with the FHIR server. This step cannot be undone from here
            (you would have to delete and re-create the dataset).
          </p>
          <v-alert
            v-if="errorText"
            type="error"
            variant="tonal"
            class="mt-2"
            :text="errorText"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" :disabled="submitting" @click="close">Cancel</v-btn>
          <v-btn
            color="cyan"
            variant="tonal"
            prepend-icon="mdi-cloud-upload"
            :loading="submitting"
            :disabled="submitting"
            @click="handleApprove"
          >
            Approve & upload
          </v-btn>
        </v-card-actions>
      </template>

      <!-- Progress: 6-stage upload animation -->
      <template v-else-if="phase === 'progress' && liveMeasurement">
        <v-card-text class="pa-5">
          <SubmitProgress
            :measurement="liveMeasurement"
            @done="onDone"
            @failed="onFailed"
          />
        </v-card-text>
      </template>

      <!-- Result: terminal outcome -->
      <template v-else-if="phase === 'result'">
        <v-card-text class="pa-5 text-center">
          <v-icon size="64" :color="resultIconColor" class="mb-2">{{ resultIcon }}</v-icon>
          <div class="text-h6 mb-1" :class="resultTitleClass">{{ resultTitle }}</div>
          <div class="text-caption text-grey-lighten-1">{{ resultDetail }}</div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn color="cyan" variant="tonal" @click="close">Close</v-btn>
        </v-card-actions>
      </template>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import SubmitProgress from './SubmitProgress.vue';
import { useMeasurementSubmit } from '@/bootstrap/measurement_api';
import type { MeasurementResponse } from '@/models/types';

const props = defineProps<{
  modelValue: boolean;
  measurement: MeasurementResponse | null;
}>();
const emit = defineEmits<{
  (e: 'update:modelValue', v: boolean): void;
  // Emitted once the approval flow settles (success or failure). The parent
  // refreshes the registry list so card buttons reflect the new status.
  (e: 'finished'): void;
}>();

type Phase = 'confirm' | 'progress' | 'result';
const phase = ref<Phase>('confirm');
const submitting = ref(false);
const errorText = ref('');
const liveMeasurement = ref<MeasurementResponse | null>(null);
const finalStatus = ref<string>('');

// Reset to a clean confirm state every time the dialog opens.
watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      phase.value = 'confirm';
      submitting.value = false;
      errorText.value = '';
      liveMeasurement.value = null;
      finalStatus.value = '';
    }
  },
);

async function handleApprove() {
  if (!props.measurement || submitting.value) return;
  submitting.value = true;
  errorText.value = '';
  try {
    // submit flips the row to `uploading` and returns it; SubmitProgress polls
    // from there to a terminal state.
    const uploading = await useMeasurementSubmit(props.measurement.id);
    liveMeasurement.value = uploading;
    phase.value = 'progress';
  } catch (err: any) {
    errorText.value =
      err?.response?.data?.detail || err?.message || 'Failed to start upload.';
  } finally {
    submitting.value = false;
  }
}

function onDone(m: MeasurementResponse) {
  finalStatus.value = m.status;
  phase.value = 'result';
}

function onFailed(m: MeasurementResponse) {
  finalStatus.value = m.status;
  phase.value = 'result';
}

const resultIcon = computed(() =>
  finalStatus.value === 'completed' ? 'mdi-check-circle-outline' : 'mdi-alert-circle-outline',
);
const resultIconColor = computed(() =>
  finalStatus.value === 'completed' ? 'green-lighten-1' : 'amber-lighten-1',
);
const resultTitleClass = computed(() =>
  finalStatus.value === 'completed' ? 'text-green-lighten-3' : 'text-amber-lighten-3',
);
const resultTitle = computed(() => {
  switch (finalStatus.value) {
    case 'completed': return 'Approved & uploaded';
    case 'fhir_failed': return 'Stored, FHIR registration failed';
    case 'submit_failed': return 'Upload could not complete';
    default: return 'Finished';
  }
});
const resultDetail = computed(() => {
  switch (finalStatus.value) {
    case 'completed':
      return 'Dataset uploaded to MinIO and registered on FHIR.';
    case 'fhir_failed':
      return 'The dataset is stored in MinIO. Use "Retry FHIR" on the card to finish registration.';
    case 'submit_failed':
      return 'Nothing was uploaded. You can edit the annotation and approve again.';
    default:
      return '';
  }
});

function onDialogToggle(v: boolean) {
  // Block outside-click / esc dismissal mid-upload (dialog is persistent then).
  if (phase.value === 'progress') return;
  if (!v) close();
}

function close() {
  emit('update:modelValue', false);
  // Tell the parent to refresh whenever we actually ran something.
  if (phase.value === 'result') emit('finished');
}
</script>
