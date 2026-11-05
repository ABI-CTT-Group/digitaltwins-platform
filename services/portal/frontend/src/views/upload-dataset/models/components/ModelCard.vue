<template>
  <CardUI
    :title="model.name"
    kind="Model"
    accent="var(--accent-models)"
    :menu-items="menuItems"
  >
    <template #description>{{ model.description || 'No description provided.' }}</template>

    <template #status><StatusLine :status="status" /></template>

    <template v-if="status.action" #action>
      <button type="button" class="aurora-btn aurora-btn--sm" @click.stop="runAction(status.action)">
        {{ ACTION_LABELS[status.action] }}
      </button>
    </template>
  </CardUI>
</template>

<script setup lang="ts">
import { computed, toRef } from 'vue';
import CardUI, { type UCardMenuItem } from '../../components/CardUI.vue';
import StatusLine from '../../components/StatusLine.vue';
import { ACTION_LABELS, datasetStatus, type CardAction } from '../../components/cardStatus';
import type { MeasurementResponse } from '@/models/types';

// Statuses are those of measurement_api's adapters: pending_upload (receiving),
// pending (staged), uploading (committing / pushing), submit_failed,
// completed, fhir_failed.
const props = defineProps<{ model: MeasurementResponse }>();
const emit = defineEmits<{
  (e: 'resumeUpload', id: string): void;
  (e: 'cancelUpload', m: MeasurementResponse): void;
  (e: 'approve', m: MeasurementResponse): void;
  (e: 'edit', m: MeasurementResponse): void;
  (e: 'retryFhir', id: string): void;
  (e: 'delete', m: MeasurementResponse): void;
}>();

const model = toRef(props, 'model');
const busy = computed(() => model.value.status === 'uploading');

const status = computed(() => datasetStatus(model.value));

const runAction = (action: CardAction) => {
  const m = model.value;
  if (action === 'approve' || action === 'approve-again') emit('approve', m);
  else if (action === 'resume-upload') emit('resumeUpload', m.id);
  else if (action === 'retry-fhir') emit('retryFhir', m.id);
};

// The status line's action is the card's button (approve, resume, retry FHIR); the menu holds the rest.
const menuItems = computed<UCardMenuItem[]>(() => {
  const m = model.value;
  if (m.status === 'pending_upload') {
    return [{ label: 'Cancel upload', icon: 'mdi-close-circle-outline', danger: true, onClick: onCancelUpload }];
  }
  const annotation: UCardMenuItem = { label: m.hasAnnotation ? 'Edit FHIR annotation' : 'Add FHIR annotation',
    icon: 'mdi-pencil-outline', disabled: busy.value, onClick: () => emit('edit', m) };
  if (!m.uuid) {
    // Staged or failed session: annotate it (optional) or drop it.
    return [annotation,
      { label: 'Cancel upload', icon: 'mdi-close-circle-outline', danger: true, disabled: busy.value, onClick: onCancelUpload }];
  }
  const items: UCardMenuItem[] = [annotation];
  items.push({ label: 'Delete model', icon: 'mdi-trash-can-outline', danger: true, disabled: busy.value, onClick: () => emit('delete', m) });
  return items;
});

// The hub confirms before cancelling.
const onCancelUpload = () => emit('cancelUpload', model.value);
</script>
