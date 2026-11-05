<template>
  <CardUI
    :title="measurement.name"
    kind="Measurement"
    accent="#62d3b0"
    :menu-items="menuItems"
  >
    <template #description>{{ measurement.description || 'No description provided.' }}</template>

    <template #meta>
      <span class="aurora-chip" :style="{ '--chip': registration.color }" :title="registration.title">{{ registration.label }}</span>
      <span v-if="measurement.createdAt" class="aurora-chip ms-auto">{{ formatDate(measurement.createdAt) }}</span>
    </template>

    <template v-if="measurement.status === 'fhir_failed'" #action>
      <button
        type="button"
        class="aurora-btn aurora-btn--sm"
        style="--accent: #ffb74d"
        :disabled="retrying"
        @click.stop="onRetryFhir"
      >
        <v-progress-circular v-if="retrying" indeterminate size="13" width="2" color="#ffb74d" />
        <v-icon v-else icon="mdi-refresh" size="15" /> Retry FHIR
      </button>
    </template>
  </CardUI>
</template>

<script setup lang="ts">
import { computed, ref, toRef } from 'vue';
import CardUI, { type UCardMenuItem } from '../../components/CardUI.vue';
import { formatDate } from '../../components/utils';
import { measurementRegistrationTag } from '../../components/cardTags';
import type { MeasurementResponse } from '@/models/types';

const props = defineProps<{ measurement: MeasurementResponse }>();
const emit = defineEmits<{
  (e: 'delete', m: MeasurementResponse): void;
  (e: 'cancelUpload', m: MeasurementResponse): void;
  (e: 'resumeUpload', id: string): void;
  (e: 'retryFhir', id: string): void;
  (e: 'approve', m: MeasurementResponse): void;
  (e: 'edit', m: MeasurementResponse): void;
  (e: 'preview', m: MeasurementResponse): void;
  (e: 'export', m: MeasurementResponse): void;
}>();

const retrying = ref(false);
const measurement = toRef(props, 'measurement');

// Button visibility matrix. MinIO is uploaded once status leaves
// pending/submit_failed; `uploading` disables every action to prevent races.
const busy = computed(() => measurement.value.status === 'uploading');
const notUploaded = computed(
  () => measurement.value.status === 'pending' || measurement.value.status === 'submit_failed',
);
const showApproval = computed(() => !!measurement.value.hasAnnotation && notUploaded.value);
const showEdit = computed(() => notUploaded.value);
const showAnnotationActions = computed(() => !!measurement.value.hasAnnotation);

const registration = computed(() => measurementRegistrationTag(measurement.value));

const menuItems = computed<UCardMenuItem[]>(() => {
  // A pending_upload row is a placeholder for an in-flight chunked upload. The
  // only meaningful action is to abort it — which must go through /upload/cancel
  // (drops the tmp parts + row), not the generic delete.
  if (measurement.value.status === 'pending_upload') {
    return [
      { label: 'Resume upload', icon: 'mdi-play-circle-outline', onClick: onResumeUpload },
      { label: 'Cancel upload', icon: 'mdi-close-circle-outline', danger: true, onClick: onCancelUpload },
    ];
  }

  const items: UCardMenuItem[] = [];
  if (showApproval.value) {
    items.push({ label: 'Approval (upload to MinIO)', icon: 'mdi-cloud-upload-outline', disabled: busy.value, onClick: onApprove });
  }
  if (showEdit.value) {
    items.push({ label: 'Edit annotation', icon: 'mdi-pencil-outline', disabled: busy.value, onClick: onEdit });
  }
  if (showAnnotationActions.value) {
    items.push({ label: 'Preview fhir.json', icon: 'mdi-code-json', disabled: busy.value, onClick: onPreview });
    items.push({ label: 'Export annotation', icon: 'mdi-download-outline', disabled: busy.value, onClick: onExport });
  }
  if (measurement.value.status === 'fhir_failed') {
    items.push({ label: 'Retry FHIR registration', icon: 'mdi-refresh', onClick: onRetryFhir });
  }
  items.push({ label: 'Delete measurement', icon: 'mdi-trash-can-outline', danger: true, disabled: busy.value, onClick: onDelete });
  return items;
});

const onApprove = () => emit('approve', measurement.value);
const onEdit = () => emit('edit', measurement.value);
const onPreview = () => emit('preview', measurement.value);
const onExport = () => emit('export', measurement.value);
// The hub confirms both before acting.
const onDelete = () => emit('delete', measurement.value);
const onCancelUpload = () => emit('cancelUpload', measurement.value);
const onResumeUpload = () => emit('resumeUpload', measurement.value.id);
const onRetryFhir = () => {
  retrying.value = true;
  emit('retryFhir', measurement.value.id);
  // The parent triggers a list refresh after the call resolves; the loading
  // state cleanly resets when this card unmounts/remounts with the new row.
};
</script>
