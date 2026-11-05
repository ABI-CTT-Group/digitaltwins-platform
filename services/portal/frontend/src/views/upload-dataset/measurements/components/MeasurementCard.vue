<template>
  <CardUI
    :title="measurement.name"
    kind="Measurement"
    accent="var(--accent-measurements)"
    :menu-items="menuItems"
  >
    <template #description>{{ measurement.description || 'No description provided.' }}</template>

    <template #status><StatusLine :status="status" /></template>

    <template v-if="status.action" #action>
      <button type="button" class="aurora-btn aurora-btn--sm" :disabled="retrying" @click.stop="runAction(status.action)">
        <v-progress-circular v-if="retrying" indeterminate size="13" width="2" />
        {{ ACTION_LABELS[status.action] }}
      </button>
    </template>
  </CardUI>
</template>

<script setup lang="ts">
import { computed, ref, toRef } from 'vue';
import CardUI, { type UCardMenuItem } from '../../components/CardUI.vue';
import StatusLine from '../../components/StatusLine.vue';
import { ACTION_LABELS, datasetStatus, type CardAction } from '../../components/cardStatus';
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

// The status line's action is the card's button (approve, resume, retry FHIR); the menu holds the rest.
// The files reach the platform once status leaves pending/submit_failed; `uploading` disables every
// action to prevent races. The FHIR annotation is optional, so a staged dataset approves without one.
const busy = computed(() => measurement.value.status === 'uploading');
const notUploaded = computed(
  () => measurement.value.status === 'pending' || measurement.value.status === 'submit_failed',
);
const hasAnnotation = computed(() => !!measurement.value.hasAnnotation);

const status = computed(() => datasetStatus(measurement.value));

const runAction = (action: CardAction) => {
  if (action === 'approve' || action === 'approve-again') onApprove();
  else if (action === 'resume-upload') onResumeUpload();
  else if (action === 'retry-fhir') onRetryFhir();
};

const menuItems = computed<UCardMenuItem[]>(() => {
  // A pending_upload row is a placeholder for an in-flight chunked upload: resume it (the button)
  // or abort it — which must go through /upload/cancel (drops the tmp parts + row), not the generic delete.
  if (measurement.value.status === 'pending_upload') {
    return [{ label: 'Cancel upload', icon: 'mdi-close-circle-outline', danger: true, onClick: onCancelUpload }];
  }

  const items: UCardMenuItem[] = [];
  if (notUploaded.value) {
    items.push({ label: hasAnnotation.value ? 'Edit FHIR annotation' : 'Add FHIR annotation', icon: 'mdi-pencil-outline',
      disabled: busy.value, onClick: onEdit });
  }
  if (hasAnnotation.value) {
    items.push({ label: 'Preview fhir.json', icon: 'mdi-code-json', disabled: busy.value, onClick: onPreview });
    items.push({ label: 'Export annotation', icon: 'mdi-download-outline', disabled: busy.value, onClick: onExport });
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
