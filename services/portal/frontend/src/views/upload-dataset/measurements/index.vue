<template>
  <div class="container overflow-hidden d-flex justify-center">
    <div class="overflow-y-auto sub-container">
      <Hero :title="heroDetail.title" :subtitle="heroDetail.subtitle" />

      <MeasurementsOverallView v-if="showOverall" @register="showOverall = false" />
      <UploadMeasurementForm v-else @finished="handleUploadFinished" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import Hero from '@/components/domain/Hero.vue';
import MeasurementsOverallView from './MeasurementsOverallView.vue';
import UploadMeasurementForm from './UploadMeasurementForm.vue';

const showOverall = ref(true);

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

const handleUploadFinished = () => {
  showOverall.value = true;
};
</script>

<style scoped>
.sub-container {
  width: 100%;
  margin-top: 70px;
}
</style>
