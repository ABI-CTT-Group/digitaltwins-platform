<template>
  <HubShell :title="heroDetail.title" :subtitle="heroDetail.subtitle" accent="var(--accent-measurements)">

      <MeasurementsOverallView
        v-if="showOverall"
        @register="handleRegister"
        @resume="handleResume"
        @edit="handleEdit"
      />
      <UploadMeasurementForm
        v-else
        :measurement="editMeasurement"
        :initial-step="editMeasurement ? 2 : 1"
        :resume-measurement-id="resumeMeasurementId"
        @finished="handleUploadFinished"
      />
  </HubShell>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import HubShell from '../components/HubShell.vue';
import MeasurementsOverallView from './MeasurementsOverallView.vue';
import UploadMeasurementForm from './UploadMeasurementForm.vue';
import type { MeasurementResponse } from '@/models/types';

const showOverall = ref(true);
// When set, the form opens in edit mode (Annotation step) for this draft.
// Undefined means the create flow (start at Information).
const editMeasurement = ref<MeasurementResponse | undefined>(undefined);
// When set, the Information step opens in resume mode bound to this unfinished
// upload (name locked, dropped folder validated against the server manifest).
const resumeMeasurementId = ref<string | undefined>(undefined);

const heroDetail = computed(() =>
  showOverall.value
    ? {
        title: 'Measurements',
        subtitle: 'Register SDS measurement datasets so assays can use them as inputs.',
      }
    : {
        title: 'Register a measurement dataset',
        subtitle: 'Upload an SDS dataset and annotate it for FHIR. You approve it from its card afterwards.',
      },
);

const handleRegister = () => {
  editMeasurement.value = undefined;
  resumeMeasurementId.value = undefined;
  showOverall.value = false;
};

const handleResume = (id: string) => {
  editMeasurement.value = undefined;
  resumeMeasurementId.value = id;
  showOverall.value = false;
};

const handleEdit = (m: MeasurementResponse) => {
  editMeasurement.value = m;
  showOverall.value = false;
};

const handleUploadFinished = () => {
  editMeasurement.value = undefined;
  resumeMeasurementId.value = undefined;
  showOverall.value = true;
};
</script>

<style scoped>

</style>
