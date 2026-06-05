<template>
  <v-container class="d-flex align-center justify-center">
    <v-card
      class="pa-6 responsive-box d-flex flex-column align-center justify-center aurora-panel"
      flat
    >
      <h2 class="w-100 text-center my-3 wizard-title">{{ isEdit ? 'Edit Annotation' : 'New Measurement Dataset' }}</h2>
      <v-stepper v-model="step" alt-labels class="sheet-stepper">
        <v-stepper-header>
          <v-stepper-item title="Information" :value="1" color="#5fd6e8" :complete="step > 1" />
          <v-divider />
          <v-stepper-item title="Annotation" :value="2" color="#5fd6e8" :complete="step > 2" />
        </v-stepper-header>

        <v-stepper-window>
          <v-stepper-window-item :value="1">
            <v-card class="pa-4 step-pane" flat>
              <InformationStep @created="handleCreated" @cancel="handleCancel" />
            </v-card>
          </v-stepper-window-item>

          <v-stepper-window-item :value="2">
            <v-card class="pa-4 step-pane" flat>
              <AnnotationStep
                v-if="measurement"
                :measurement="measurement"
                @saved="handleAnnotationSaved"
                @cancel="handleCancel"
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
import type { MeasurementResponse } from '@/models/types';

// In edit mode the parent passes an existing measurement; we skip the
// Information step and open Annotation directly so the user re-edits the
// saved draft. In create mode both props are undefined and we start at step 1.
const props = defineProps<{
  measurement?: MeasurementResponse;
  initialStep?: number;
}>();

const emit = defineEmits(['finished']);

const isEdit = !!props.measurement;
const step = ref(props.initialStep ?? 1);
const measurement = ref<MeasurementResponse | undefined>(props.measurement);

const handleCreated = (created: MeasurementResponse) => {
  measurement.value = created;
  step.value = 2;
};

const handleAnnotationSaved = () => {
  // Draft saved (no upload). Return to the registry list — the dataset now
  // shows an Approval action in its card menu.
  emit('finished');
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
