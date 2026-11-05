<template>
  <WizardFrame :steps="['Upload', 'FHIR annotation (optional)']" :current="step === 'upload' ? 1 : 2" accent="#b08fe8">
    <InformationStep
      v-if="step === 'upload'"
      ref="info"
      category="models"
      :resume-measurement-id="id"
      @created="handleCreated"
      @cancel="cancel"
    />
    <ModelFhirStep
      v-else-if="model"
      :model="model"
      @finished="handleFhirFinished"
      @cancel="toHub"
    />
    <p v-else-if="loadError" class="step-error" role="alert">
      <v-icon icon="mdi-alert-circle-outline" size="18" /> {{ loadError }}
    </p>
    <v-progress-linear v-else indeterminate color="#b08fe8" />
  </WizardFrame>
</template>

<script setup lang="ts">
/**
 * The model registration wizard: Upload → FHIR annotation (optional), as for measurements
 * (`/catalogue/models/new`, then `/catalogue/models/<id>/register?step=annotation|upload`).
 */
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
// @ts-ignore - vue-toastification ships without type declarations
import { useToast } from 'vue-toastification';
import InformationStep from '../measurements/steps/InformationStep.vue';
import ModelFhirStep from './steps/ModelFhirStep.vue';
import { useGetMeasurement, useMeasurementRetryFhir } from '@/bootstrap/measurement_api';
import { describeApiError } from '../components/apiError';
import { hubRoute, registerRoute } from '../components/registrationSteps';
import { useLeaveGuard } from '../components/useLeaveGuard';
import WizardFrame from '../components/WizardFrame.vue';
import type { MeasurementResponse } from '@/models/types';

const props = defineProps<{ id?: string }>();
const route = useRoute();
const router = useRouter();
const toast = useToast();

const step = computed(() => (!props.id || route.query.step === 'upload' ? 'upload' : 'annotation'));
const info = ref<{ dirty: boolean } | null>(null);
const model = ref<MeasurementResponse>();
const loadError = ref('');
const left = ref(false);

useLeaveGuard(() => step.value === 'upload' && !left.value && !!info.value?.dirty);

watch([() => props.id, step], async ([id, current]) => {
  if (!id || current !== 'annotation' || model.value?.id === id) return;
  loadError.value = '';
  try {
    model.value = await useGetMeasurement(id);
  } catch (err) {
    loadError.value = describeApiError(err, 'Loading');
  }
}, { immediate: true });

const handleCreated = async (created: MeasurementResponse) => {
  model.value = created;
  left.value = true;
  await router.replace(registerRoute('models', created.id, 'annotation'));
  left.value = false;
};

const toHub = () => router.push(hubRoute('models'));
const cancel = async () => { left.value = true; await toHub(); };

// A staged upload is pushed on Approval; a registered model is pushed now.
const handleFhirFinished = async (saved: boolean) => {
  if (saved && model.value?.uuid) {
    try {
      await useMeasurementRetryFhir(model.value.id);
      toast.success('Publishing the model to FHIR.');
    } catch (e) {
      toast.error(describeApiError(e, 'FHIR publish'));
    }
  }
  await toHub();
};
</script>
