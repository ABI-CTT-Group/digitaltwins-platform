<template>
  <HubShell :title="heroDetail.title" :subtitle="heroDetail.subtitle" accent="var(--accent-models)">

      <ModelsOverallView
        v-if="showOverall"
        @register="handleRegister"
        @resume="handleResume"
        @edit="handleEdit"
      />
      <UploadModelForm
        v-else
        :model="editModel"
        :resume-model-id="resumeModelId"
        @finished="handleFinished"
      />
  </HubShell>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import HubShell from '../components/HubShell.vue';
import ModelsOverallView from './ModelsOverallView.vue';
import UploadModelForm from './UploadModelForm.vue';
import type { MeasurementResponse } from '@/models/types';

const showOverall = ref(true);
// Set: the form opens at the FHIR step for this model. Unset: the create flow.
const editModel = ref<MeasurementResponse | undefined>(undefined);
// Set: the Information step resumes this unfinished upload.
const resumeModelId = ref<string | undefined>(undefined);

const heroDetail = computed(() =>
  showOverall.value
    ? {
        title: 'Models',
        subtitle: 'Register trained models (SDS datasets) so assays and inference workflows can use them.',
      }
    : {
        title: 'Register a model',
        subtitle: 'Upload an SDS model dataset and add FHIR details if you want. You approve it from its card afterwards.',
      },
);

const open = (model?: MeasurementResponse, resumeId?: string) => {
  editModel.value = model;
  resumeModelId.value = resumeId;
  showOverall.value = false;
};
const handleRegister = () => open();
const handleResume = (id: string) => open(undefined, id);
const handleEdit = (m: MeasurementResponse) => open(m);
const handleFinished = () => {
  editModel.value = undefined;
  resumeModelId.value = undefined;
  showOverall.value = true;
};
</script>
