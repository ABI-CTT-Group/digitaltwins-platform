<template>
  <div class="container d-flex justify-center">
    <div class="sub-container">
      <BackLink to="CatalogueDashboardView" label="Catalogue" class="mb-4" />
      <Hero :title="heroDetail.title" :subtitle="heroDetail.subtitle" />

      <MeasurementsOverallView
        v-if="showOverall"
        @register="handleRegister"
        @edit="handleEdit"
      />
      <UploadMeasurementForm
        v-else
        :measurement="editMeasurement"
        :initial-step="editMeasurement ? 2 : 1"
        @finished="handleUploadFinished"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import Hero from '@/components/domain/Hero.vue';
import BackLink from '@/components/common/BackLink.vue';
import MeasurementsOverallView from './MeasurementsOverallView.vue';
import UploadMeasurementForm from './UploadMeasurementForm.vue';
import type { MeasurementResponse } from '@/models/types';

const showOverall = ref(true);
// When set, the form opens in edit mode (Annotation step) for this draft.
// Undefined means the create flow (start at Information).
const editMeasurement = ref<MeasurementResponse | undefined>(undefined);

const heroDetail = computed(() =>
  showOverall.value
    ? {
        title: 'Measurements Hub',
        subtitle:
          'Register SPARC measurements datasets and annotate patients, observations, imaging studies, and document references.',
      }
    : {
        title: 'Upload & Annotate Measurements',
        subtitle:
          'Drag a folder or .zip, fine-tune the auto-detected annotation, and we will push it to MinIO + FHIR.',
      },
);

const handleRegister = () => {
  editMeasurement.value = undefined;
  showOverall.value = false;
};

const handleEdit = (m: MeasurementResponse) => {
  editMeasurement.value = m;
  showOverall.value = false;
};

const handleUploadFinished = () => {
  editMeasurement.value = undefined;
  showOverall.value = true;
};
</script>

<style scoped>
.sub-container {
  width: 100%;
  margin-top: 70px;
}
</style>
