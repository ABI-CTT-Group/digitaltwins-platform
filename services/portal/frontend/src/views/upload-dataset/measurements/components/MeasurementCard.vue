<template>
  <CardUI
    cardStyle="background: rgba(0, 200, 180, 0.05);"
    :isDeleting="isDeleting"
    v-model:menu="menu"
  >
    <template #menu>
      <v-list density="compact" class="py-0 cursor-pointer">
        <v-list-item
          v-if="showApproval"
          density="compact"
          :disabled="busy"
          @click.stop="onApprove"
        >
          <v-list-item-title class="hover-animate px-2">Approval (upload to MinIO)</v-list-item-title>
        </v-list-item>
        <v-list-item
          v-if="showEdit"
          density="compact"
          :disabled="busy"
          @click.stop="onEdit"
        >
          <v-list-item-title class="hover-animate px-2">Edit annotation</v-list-item-title>
        </v-list-item>
        <v-list-item
          v-if="showAnnotationActions"
          density="compact"
          :disabled="busy"
          @click.stop="onPreview"
        >
          <v-list-item-title class="hover-animate px-2">Preview fhir.json</v-list-item-title>
        </v-list-item>
        <v-list-item
          v-if="showAnnotationActions"
          density="compact"
          :disabled="busy"
          @click.stop="onExport"
        >
          <v-list-item-title class="hover-animate px-2">Export annotation</v-list-item-title>
        </v-list-item>
        <v-list-item
          v-if="measurement.status === 'fhir_failed'"
          density="compact"
          @click.stop="onRetryFhir"
        >
          <v-list-item-title class="hover-animate px-2">Retry FHIR registration</v-list-item-title>
        </v-list-item>
        <v-list-item density="compact" :disabled="busy" @click.stop="onDelete" color="red">
          <v-list-item-title class="text-red hover-animate px-2">Delete measurement</v-list-item-title>
        </v-list-item>
      </v-list>
    </template>
    <template #name>
      <v-tooltip :text="measurement.name" location="top" max-width="300">
        <template #activator="{ props }">
          <p v-bind="props" class="text-truncate" style="max-width: 400px;">
            {{ measurement.name }}
          </p>
        </template>
      </v-tooltip>
    </template>
    <template #description>
      {{ measurement.description || 'No description provided.' }}
    </template>
    <template #tags>
      <v-chip
        size="small"
        :color="statusColor"
        :text-color="statusTextColor"
        class="mx-1 my-1"
      >
        {{ statusLabel }}
      </v-chip>
      <v-chip
        v-if="measurement.failureStage && (measurement.status === 'submit_failed' || measurement.status === 'fhir_failed')"
        size="x-small"
        color="amber-lighten-3"
        text-color="amber-darken-3"
        class="mx-1 my-1"
      >
        stage: {{ measurement.failureStage }}
      </v-chip>
      <v-btn
        v-if="measurement.status === 'fhir_failed'"
        size="small"
        variant="tonal"
        color="amber"
        prepend-icon="mdi-refresh"
        :loading="retrying"
        class="mx-1 my-1"
        @click.stop="onRetryFhir"
      >
        Retry FHIR
      </v-btn>
    </template>
    <template #time>
      <v-chip
        v-if="measurement.createdAt"
        size="small"
        color="green-lighten-4"
        text-color="green-darken-2"
        class="ms-auto"
      >
        {{ formatDate(measurement.createdAt) }}
      </v-chip>
    </template>
  </CardUI>
</template>

<script setup lang="ts">
import { computed, ref, toRef } from 'vue';
import CardUI from '../../components/CardUI.vue';
import { formatDate } from '../../components/utils';
import type { MeasurementResponse } from '@/models/types';

const props = defineProps<{ measurement: MeasurementResponse }>();
const emit = defineEmits<{
  (e: 'delete', id: string): void;
  (e: 'retryFhir', id: string): void;
  (e: 'approve', m: MeasurementResponse): void;
  (e: 'edit', m: MeasurementResponse): void;
  (e: 'preview', m: MeasurementResponse): void;
  (e: 'export', m: MeasurementResponse): void;
}>();

const menu = ref(false);
const isDeleting = ref(false);
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

const statusLabel = computed(() => {
  switch (measurement.value.status) {
    case 'pending': return 'pending';
    case 'uploading': return 'uploading…';
    case 'submit_failed': return 'submit failed';
    case 'fhir_failed': return 'FHIR failed';
    case 'completed': return 'completed';
    default: return measurement.value.status;
  }
});

const statusColor = computed(() => {
  switch (measurement.value.status) {
    case 'pending': return 'grey-lighten-2';
    case 'uploading': return 'cyan-lighten-2';
    case 'submit_failed': return 'amber-lighten-2';
    case 'fhir_failed': return 'amber-lighten-2';
    case 'completed': return 'green-lighten-2';
    default: return '';
  }
});

const statusTextColor = computed(() => {
  switch (measurement.value.status) {
    case 'pending': return 'grey-darken-3';
    case 'uploading': return 'cyan-darken-3';
    case 'submit_failed': return 'amber-darken-3';
    case 'fhir_failed': return 'amber-darken-3';
    case 'completed': return 'green-darken-3';
    default: return '';
  }
});

const onApprove = () => {
  menu.value = false;
  emit('approve', measurement.value);
};

const onEdit = () => {
  menu.value = false;
  emit('edit', measurement.value);
};

const onPreview = () => {
  menu.value = false;
  emit('preview', measurement.value);
};

const onExport = () => {
  menu.value = false;
  emit('export', measurement.value);
};

const onDelete = () => {
  menu.value = false;
  isDeleting.value = true;
  emit('delete', measurement.value.id);
};

const onRetryFhir = () => {
  menu.value = false;
  retrying.value = true;
  emit('retryFhir', measurement.value.id);
  // The parent triggers a list refresh after the call resolves; the loading
  // state cleanly resets when this card unmounts/remounts with the new row.
};
</script>
