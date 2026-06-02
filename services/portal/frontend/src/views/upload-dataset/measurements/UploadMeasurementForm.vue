<template>
  <v-container class="d-flex align-center justify-center">
    <v-card
      class="pa-6 responsive-box d-flex flex-column align-center justify-center"
      elevation="12"
      style="background: rgba(15, 25, 35, 0.45); border-radius: 20px;"
    >
      <h2 class="w-100 text-center my-3">New Measurement Dataset</h2>
      <v-stepper v-model="step" alt-labels class="sheet-stepper">
        <v-stepper-header>
          <v-stepper-item title="Information" :value="1" color="cyan-lighten-1" :complete="step > 1" />
          <v-divider />
          <v-stepper-item title="Annotation" :value="2" color="cyan-lighten-1" :complete="step > 2" />
          <v-divider />
          <v-stepper-item title="Complete" :value="3" color="cyan-lighten-1" :editable="false" :complete="step > 3" />
        </v-stepper-header>

        <v-stepper-window>
          <v-stepper-window-item :value="1">
            <v-card class="pa-4" variant="outlined" color="grey-lighten-2">
              <InformationStep @created="handleCreated" @cancel="handleCancel" />
            </v-card>
          </v-stepper-window-item>

          <v-stepper-window-item :value="2">
            <v-card class="pa-4" variant="outlined" color="grey-lighten-2">
              <AnnotationStep
                v-if="measurement"
                :measurement="measurement"
                @submitted="handleAnnotationSubmitted"
                @cancel="handleCancel"
              />
            </v-card>
          </v-stepper-window-item>

          <v-stepper-window-item :value="3">
            <v-card class="pa-4" variant="tonal" color="cyan-darken-4">
              <CompleteStep
                v-if="measurement"
                :measurement="measurement"
                @back-to-annotation="handleBackToAnnotation"
                @done="handleCancel"
                @retried="handleRetried"
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
import InformationStep from './steps/InformationStep.vue';
import AnnotationStep from './steps/AnnotationStep.vue';
import CompleteStep from './steps/CompleteStep.vue';
import type { MeasurementResponse } from '@/models/types';

const emit = defineEmits(['finished']);

const step = ref(1);
const measurement = ref<MeasurementResponse>();

const handleCreated = (created: MeasurementResponse) => {
  measurement.value = created;
  step.value = 2;
};

const handleAnnotationSubmitted = (updated: MeasurementResponse) => {
  // Submit returns the row already flipped to `uploading`. Step 3 polls
  // from there until it lands on completed / submit_failed / fhir_failed.
  measurement.value = updated;
  step.value = 3;
};

const handleBackToAnnotation = () => {
  // Triggered on submit_failed — let the user edit the annotation. Step 2
  // rehydrates from /annotation so prior edits aren't lost.
  step.value = 2;
};

const handleRetried = (updated: MeasurementResponse) => {
  // /retry-fhir flipped status back to `uploading`; CompleteStep will resume
  // polling. We just refresh the measurement ref in place.
  measurement.value = updated;
};

const handleCancel = () => {
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
.sheet-stepper {
  width: 95%;
  min-height: 50vh;
  background: rgba(1, 62, 62, 0.15);
  border-radius: 10px !important;
  box-shadow:
    5px 5px 10px #071b25,
    -5px -5px 10px #0d3547 !important;
}
</style>
