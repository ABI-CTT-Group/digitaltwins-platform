<template>
  <div class="container d-flex justify-center" style="padding-top: 16px;">
    <div class="w-100">
      <BackLink to="CatalogueDashboardView" label="Catalogue" sticky class="mb-4" />
      <Hero :title="heroDetail.title" :subtitle="heroDetail.subtitle" />

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
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import Hero from '@/components/domain/Hero.vue';
import BackLink from '@/components/common/BackLink.vue';
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
        title: 'Models Hub',
        subtitle: 'Register trained models (SDS datasets) so assays and inference workflows can use them.',
      }
    : {
        title: 'Register a Model',
        subtitle: 'Drag a folder or .zip of an SDS model dataset. It is staged for approval before it is stored.',
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
