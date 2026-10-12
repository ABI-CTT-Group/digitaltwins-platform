<template>
  <div>
    <h3 class="step-heading">FHIR (optional)</h3>
    <v-divider class="my-2 mb-5" :thickness="3" />

    <div class="px-5">
      <p class="text-caption step-sub mb-2">
        Publish this model to the FHIR server as a Device, identified by its dataset UUID.
        You can also do this later from the model's card.
      </p>
      <v-switch
        v-model="publish"
        data-testid="publish-fhir"
        label="Publish to FHIR"
        color="#b08fe8"
        hide-details
        inset
      />

      <template v-if="publish">
        <v-progress-linear v-if="loading" indeterminate color="#b08fe8" class="my-2" />
        <h4 class="mb-1 mt-3">Version</h4>
        <v-text-field
          v-model="fields.version"
          data-testid="model-version"
          label="e.g. 2.1 (optional)"
          clearable
        />
        <h4 class="mb-1 mt-3">Description</h4>
        <v-textarea
          v-model="fields.description"
          data-testid="model-description"
          label="What does the model do? (optional)"
          rows="2"
          auto-grow
          clearable
        />
      </template>

      <v-alert v-if="error" type="error" variant="tonal" class="mt-3" :text="error" />
    </div>

    <v-divider class="mb-5 mt-5" :thickness="3" />
    <div class="d-flex flex-row justify-center">
      <v-btn
        color="#9fb4bf"
        text="Cancel"
        variant="text"
        :min-width="150"
        rounded="lg"
        class="text-none ma-5"
        :disabled="saving"
        @click="emit('cancel')"
      />
      <v-btn
        data-testid="finish"
        color="#b08fe8"
        text="Finish"
        variant="tonal"
        :min-width="200"
        rounded="lg"
        class="text-none ma-5"
        :loading="saving"
        :disabled="saving || loading"
        @click="handleFinish"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { reactive, ref, watch } from 'vue';
import { useModelFhirDraft, useUpsertModelAnnotation } from '@/bootstrap/model_api';
import type { MeasurementResponse } from '@/models/types';

// Staged upload: the draft is pushed on Approval. Registered model: saved here,
// then pushed with "Publish to FHIR" on its card.
const props = defineProps<{ model: MeasurementResponse }>();
// `finished` reports whether an annotation was saved.
const emit = defineEmits<{ (e: 'finished', saved: boolean): void; (e: 'cancel'): void }>();

const publish = ref(!!props.model.hasAnnotation);
const fields = reactive({ description: '', version: '' });
const loading = ref(false);
const saving = ref(false);
const error = ref('');

const errorText = (err: any): string => {
  const detail = err?.response?.data?.detail;
  return typeof detail === 'string' ? detail : err?.message || 'Saving failed.';
};

// Prefill from the stored annotation, or the server defaults (the upload's description).
watch(
  publish,
  async (on) => {
    if (!on) return;
    loading.value = true;
    error.value = '';
    try {
      Object.assign(fields, await useModelFhirDraft(props.model.id));
    } catch (err) {
      error.value = errorText(err);
    } finally {
      loading.value = false;
    }
  },
  { immediate: true },
);

async function handleFinish() {
  if (!publish.value) {
    emit('finished', false);
    return;
  }
  saving.value = true;
  error.value = '';
  try {
    await useUpsertModelAnnotation(props.model.id, {
      description: fields.description?.trim() ?? '',
      version: fields.version?.trim() ?? '',
    });
    emit('finished', true);
  } catch (err) {
    error.value = errorText(err);
  } finally {
    saving.value = false;
  }
}
</script>

<style scoped>
.step-heading {
  color: #b08fe8;
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 500;
}
.step-sub { color: #9fb4bf; }
</style>
