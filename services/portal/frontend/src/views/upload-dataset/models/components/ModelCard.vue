<template>
  <CardUI
    :title="model.name"
    kind="Model"
    accent="#b08fe8"
    :is-deleting="isDeleting"
    :menu-items="menuItems"
  >
    <template #description>{{ model.description || 'No description provided.' }}</template>

    <template #meta>
      <span class="aurora-chip" :style="{ '--chip': registration.color }" :title="registration.title">{{ registration.label }}</span>
      <span v-if="model.createdAt" class="aurora-chip ms-auto">{{ formatDate(model.createdAt) }}</span>
    </template>
  </CardUI>
</template>

<script setup lang="ts">
import { computed, ref, toRef } from 'vue';
import CardUI, { type UCardMenuItem } from '../../components/CardUI.vue';
import { formatDate } from '../../components/utils';
import { measurementRegistrationTag } from '../../components/cardTags';
import type { MeasurementResponse } from '@/models/types';

// Statuses are those of measurement_api's adapters: pending_upload (receiving),
// pending (staged), uploading (committing / pushing), submit_failed,
// completed, fhir_failed.
const props = defineProps<{ model: MeasurementResponse }>();
const emit = defineEmits<{
  (e: 'resumeUpload', id: string): void;
  (e: 'cancelUpload', id: string): void;
  (e: 'approve', m: MeasurementResponse): void;
  (e: 'edit', m: MeasurementResponse): void;
  (e: 'retryFhir', id: string): void;
  (e: 'delete', m: MeasurementResponse): void;
}>();

const model = toRef(props, 'model');
const isDeleting = ref(false);
const busy = computed(() => model.value.status === 'uploading');

const registration = computed(() => measurementRegistrationTag(model.value));

const menuItems = computed<UCardMenuItem[]>(() => {
  const m = model.value;
  if (m.status === 'pending_upload') {
    return [
      { label: 'Resume upload', icon: 'mdi-play-circle-outline', onClick: () => emit('resumeUpload', m.id) },
      { label: 'Cancel upload', icon: 'mdi-close-circle-outline', danger: true, onClick: onCancelUpload },
    ];
  }
  if (!m.uuid) {
    // Staged or failed session: approve (commit), edit its FHIR draft, or drop it.
    return [
      { label: 'Approve (register model)', icon: 'mdi-cloud-upload-outline', disabled: busy.value, onClick: () => emit('approve', m) },
      { label: 'Edit FHIR details', icon: 'mdi-pencil-outline', disabled: busy.value, onClick: () => emit('edit', m) },
      { label: 'Cancel upload', icon: 'mdi-close-circle-outline', danger: true, disabled: busy.value, onClick: onCancelUpload },
    ];
  }
  const items: UCardMenuItem[] = [
    { label: m.hasAnnotation ? 'Edit FHIR details' : 'Publish to FHIR', icon: 'mdi-pencil-outline', disabled: busy.value, onClick: () => emit('edit', m) },
  ];
  if (m.status === 'fhir_failed') {
    items.push({ label: 'Retry FHIR registration', icon: 'mdi-refresh', onClick: () => emit('retryFhir', m.id) });
  }
  items.push({ label: 'Delete model', icon: 'mdi-trash-can-outline', danger: true, disabled: busy.value, onClick: () => emit('delete', m) });
  return items;
});

const onCancelUpload = () => {
  isDeleting.value = true;
  emit('cancelUpload', model.value.id);
};
</script>
