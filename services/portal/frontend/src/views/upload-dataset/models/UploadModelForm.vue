<template>
  <v-container class="d-flex align-center justify-center">
    <v-card
      class="pa-6 responsive-box d-flex flex-column align-center justify-center aurora-panel"
      flat
    >
      <h2 class="w-100 text-center my-3 wizard-title">{{ props.model ? 'FHIR Details' : 'New Model Dataset' }}</h2>
      <v-stepper v-model="step" alt-labels class="sheet-stepper">
        <v-stepper-header>
          <v-stepper-item title="Information" :value="1" color="#b08fe8" :complete="step > 1" />
          <v-divider />
          <v-stepper-item title="FHIR (optional)" :value="2" color="#b08fe8" :complete="step > 2" />
        </v-stepper-header>

        <v-stepper-window>
          <v-stepper-window-item :value="1">
            <v-card class="pa-4 step-pane" flat>
              <InformationStep
                category="models"
                :resume-measurement-id="resumeModelId"
                @created="handleCreated"
                @cancel="emit('finished')"
              />
            </v-card>
          </v-stepper-window-item>

          <v-stepper-window-item :value="2">
            <v-card class="pa-4 step-pane" flat>
              <ModelFhirStep
                v-if="model"
                :model="model"
                @finished="handleFhirFinished"
                @cancel="emit('finished')"
              />
            </v-card>
          </v-stepper-window-item>
        </v-stepper-window>
      </v-stepper>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { ref } from 'vue';
// @ts-ignore - vue-toastification ships without type declarations
import { useToast } from 'vue-toastification';
import InformationStep from '../measurements/steps/InformationStep.vue';
import ModelFhirStep from './steps/ModelFhirStep.vue';
import { useMeasurementRetryFhir } from '@/bootstrap/measurement_api';
import type { MeasurementResponse } from '@/models/types';

// With `model` the form opens at the FHIR step (edit); otherwise it starts at
// Information and continues with the staged upload it creates.
const props = defineProps<{ model?: MeasurementResponse; resumeModelId?: string }>();
const emit = defineEmits(['finished']);
const toast = useToast();

const step = ref(props.model ? 2 : 1);
const model = ref<MeasurementResponse | undefined>(props.model);

const handleCreated = (created: MeasurementResponse) => {
  model.value = created;
  step.value = 2;
};

// A staged upload is pushed on Approval; a registered model is pushed now.
const handleFhirFinished = async (saved: boolean) => {
  if (saved && model.value?.uuid) {
    try {
      await useMeasurementRetryFhir(model.value.id);
      toast.success('Publishing the model to FHIR.');
    } catch (e: any) {
      toast.error(`FHIR publish failed: ${e?.response?.data?.detail || e?.message || 'unknown error'}`);
    }
  }
  emit('finished');
};
</script>

<style scoped>
.responsive-box {
  width: 90% !important;
}
@media (min-width: 2100px) {
  .responsive-box {
    width: 75% !important;
  }
}
.aurora-panel {
  background: rgba(8, 18, 26, 0.55) !important;
  border: 1px solid rgba(120, 200, 220, 0.16);
  border-radius: 20px !important;
}
.wizard-title {
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 500;
  color: #fff;
}
.sheet-stepper {
  width: 95%;
  min-height: 50vh;
  background: transparent !important;
  box-shadow: none !important;
}
.step-pane {
  background: rgba(255, 255, 255, 0.02) !important;
  border: 1px solid rgba(120, 200, 220, 0.14);
  border-radius: 14px !important;
}
</style>
