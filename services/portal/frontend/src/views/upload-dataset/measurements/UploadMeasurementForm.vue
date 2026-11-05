<template>
  <WizardFrame :steps="['Upload', 'FHIR annotation (optional)']" :current="step === 'upload' ? 1 : 2">
    <InformationStep
      v-if="step === 'upload'"
      ref="info"
      :resume-measurement-id="id"
      @created="handleCreated"
      @cancel="cancel"
    />
    <AnnotationStep
      v-else-if="measurement"
      :measurement="measurement"
      @saved="toHub"
      @skip="toHub"
      @cancel="toHub"
    />
    <p v-else-if="loadError" class="step-error" role="alert">
      <v-icon icon="mdi-alert-circle-outline" size="18" /> {{ loadError }}
    </p>
    <v-progress-linear v-else indeterminate color="#5fd6e8" />
  </WizardFrame>
</template>

<script setup lang="ts">
/**
 * The measurement registration wizard: Upload → FHIR annotation (optional).
 * `/catalogue/measurements/new` uploads; once the upload is staged the wizard moves to the dataset's own URL,
 * `/catalogue/measurements/<id>/register?step=annotation`. `?step=upload` resumes a paused upload.
 * The dataset is approved from its card afterwards.
 */
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import InformationStep from './steps/InformationStep.vue';
import AnnotationStep from './steps/AnnotationStep.vue';
import { useGetMeasurement } from '@/bootstrap/measurement_api';
import { describeApiError } from '../components/apiError';
import { hubRoute, registerRoute } from '../components/registrationSteps';
import { useLeaveGuard } from '../components/useLeaveGuard';
import WizardFrame from '../components/WizardFrame.vue';
import type { MeasurementResponse } from '@/models/types';

const props = defineProps<{ id?: string }>();
const route = useRoute();
const router = useRouter();

const step = computed(() => (!props.id || route.query.step === 'upload' ? 'upload' : 'annotation'));
const info = ref<{ dirty: boolean } | null>(null);
const measurement = ref<MeasurementResponse>();
const loadError = ref('');
const left = ref(false);

// An upload running, or a source chosen for one: leaving stops it.
useLeaveGuard(() => step.value === 'upload' && !left.value && !!info.value?.dirty);

watch([() => props.id, step], async ([id, current]) => {
  if (!id || current !== 'annotation' || measurement.value?.id === id) return;
  loadError.value = '';
  try {
    measurement.value = await useGetMeasurement(id);
  } catch (err) {
    loadError.value = describeApiError(err, 'Loading');
  }
}, { immediate: true });

const handleCreated = async (created: MeasurementResponse) => {
  measurement.value = created;
  left.value = true;
  await router.replace(registerRoute('measurements', created.id, 'annotation'));
  left.value = false;
};

const toHub = () => router.push(hubRoute('measurements'));
// The step has already cancelled its upload.
const cancel = async () => { left.value = true; await toHub(); };
</script>
