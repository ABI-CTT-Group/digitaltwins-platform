<template>
  <v-alert v-show="alertText" :text="alertText" type="error" closable @click:close="alertText = ''" />

  <div class="pa-2">
    <h3 class="text-cyan">Annotate measurements</h3>
    <v-divider class="my-2 mb-4" :thickness="3" />

    <v-progress-circular
      v-if="loading"
      indeterminate
      color="cyan"
      class="ma-4"
    />

    <template v-else-if="descriptions">
      <v-card variant="tonal" color="cyan-darken-3" class="pa-3 mb-3">
        <div class="d-flex flex-wrap ga-4">
          <div>
            <div class="text-caption text-cyan-lighten-3">Dataset</div>
            <div class="text-h6">{{ descriptions.dataset.name }}</div>
          </div>
          <v-divider vertical />
          <div>
            <div class="text-caption text-cyan-lighten-3">Patients</div>
            <div class="text-h6">{{ descriptions.patients.length }}</div>
          </div>
          <v-divider vertical />
          <div>
            <div class="text-caption text-cyan-lighten-3">Samples</div>
            <div class="text-h6">{{ totalSamples }}</div>
          </div>
          <v-divider vertical />
          <div>
            <div class="text-caption text-cyan-lighten-3">Auto-classified</div>
            <div class="text-h6">{{ autoCounts.observations + autoCounts.imagingStudy + autoCounts.documentReference }}</div>
            <div class="text-caption">
              Obs {{ autoCounts.observations }} ·
              Img {{ autoCounts.imagingStudy }} ·
              Doc {{ autoCounts.documentReference }}
            </div>
          </div>
        </div>
      </v-card>

      <v-alert
        v-if="skippedSamples.length"
        variant="tonal"
        type="warning"
        class="mb-3"
        :title="`Skipped ${skippedSamples.length} empty sample(s)`"
      >
        <div class="text-caption">{{ skippedSamples.join(', ') }}</div>
      </v-alert>

      <PatientSelector
        :patients="patientNames"
        :selected="selectedPatients"
        @update:selected="selectedPatients = $event"
      />

      <v-tabs v-model="activeTab" align-tabs="start" color="cyan-lighten-2" class="mb-2">
        <v-tab value="observation">Observations</v-tab>
        <v-tab value="imaging">Imaging Studies</v-tab>
        <v-tab value="document">Document References</v-tab>
      </v-tabs>

      <v-tabs-window v-model="activeTab">
        <v-tabs-window-item value="observation">
          <ObservationForm
            :descriptions="descriptions"
            :selected-patients="selectedPatients"
            :mock-uuid-fn="mockObsUuid"
          />
        </v-tabs-window-item>
        <v-tabs-window-item value="imaging">
          <ImagingStudyForm
            :descriptions="descriptions"
            :selected-patients="selectedPatients"
          />
        </v-tabs-window-item>
        <v-tabs-window-item value="document">
          <DocumentReferenceForm
            :descriptions="descriptions"
            :selected-patients="selectedPatients"
            :mock-uuid-fn="mockDocUuid"
          />
        </v-tabs-window-item>
      </v-tabs-window>

      <v-expansion-panels variant="accordion" class="mt-4">
        <v-expansion-panel>
          <v-expansion-panel-title>Preview descriptions (saved as draft; approve later to upload)</v-expansion-panel-title>
          <v-expansion-panel-text>
            <pre class="json-preview">{{ previewJson }}</pre>
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </template>

    <v-divider class="my-4" :thickness="3" />
    <div class="d-flex flex-row justify-center">
      <v-btn
        color="red"
        text="Cancel"
        variant="tonal"
        :min-width="150"
        rounded="md"
        class="hover-animate ma-5"
        :disabled="submitting"
        @click="emit('cancel')"
      />
      <v-btn
        color="success"
        text="Save annotation"
        variant="tonal"
        :min-width="200"
        rounded="md"
        class="hover-animate ma-5"
        :loading="submitting"
        :disabled="submitting || !descriptions"
        @click="handleSubmit"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, reactive } from 'vue';
import PatientSelector from '../components/PatientSelector.vue';
import ObservationForm from '../components/ObservationForm.vue';
import ImagingStudyForm from '../components/ImagingStudyForm.vue';
import DocumentReferenceForm from '../components/DocumentReferenceForm.vue';
import { stripAuto } from '../components/stripAuto';
import {
  useGetMeasurementTree,
  useGetMeasurementAnnotation,
  useUpsertMeasurementAnnotation,
} from '@/bootstrap/measurement_api';
import type {
  FhirCdaDescriptions,
  MeasurementResponse,
} from '@/models/types';

const props = defineProps<{ measurement: MeasurementResponse }>();
const emit = defineEmits<{
  (e: 'saved'): void;
  (e: 'cancel'): void;
}>();

const loading = ref(false);
const submitting = ref(false);
const alertText = ref('');

// Use a reactive descriptions container so the per-resource form bindings
// can two-way bind without prop drilling. Initialised on mount.
const descriptions = ref<FhirCdaDescriptions | undefined>(undefined);
const skippedSamples = ref<string[]>([]);
const selectedPatients = ref<string[]>([]);
const activeTab = ref<'observation' | 'imaging' | 'document'>('observation');

const patientNames = computed(() => descriptions.value?.patients.map((p) => p.name) ?? []);

const totalSamples = computed(() => {
  // Each Observation / ImagingStudy / DocumentReference corresponds to one
  // sample folder in the SPARC tree, modulo manual additions. We sum the
  // three lists across all patients as a proxy that's close enough for the
  // header card. (`skipped_samples` covers the discrepancy from empty dirs.)
  if (!descriptions.value) return 0;
  return descriptions.value.patients.reduce(
    (sum, p) =>
      sum +
      p.observations.length +
      p.imagingStudy.length +
      p.documentReference.length,
    0,
  );
});

const autoCounts = computed(() => {
  const counts = { observations: 0, imagingStudy: 0, documentReference: 0 };
  if (!descriptions.value) return counts;
  for (const p of descriptions.value.patients) {
    counts.observations += p.observations.filter(hasAuto).length;
    counts.imagingStudy += p.imagingStudy.filter(hasAuto).length;
    counts.documentReference += p.documentReference.filter(hasAuto).length;
  }
  return counts;
});

const previewJson = computed(() =>
  descriptions.value
    ? JSON.stringify(stripAuto(descriptions.value), null, 2)
    : '',
);

// http.ts deep-camelizes responses, which eats the leading underscore in
// `_auto` and turns it into `Auto`. Handle both spellings everywhere so the
// UI stays correct whether the interceptor changes its behaviour or not.
function hasAuto(item: unknown): boolean {
  if (!item || typeof item !== 'object') return false;
  return '_auto' in item || 'Auto' in item;
}

// Resource UUIDs come from the backend on /tree; for manually-added items in
// the UI we need *something* unique. crypto.randomUUID() is plenty for the
// UI prefill — the backend still treats them as opaque strings.
const mockObsUuid = () => `MOCK-obs-${cryptoUuid()}`;
const mockDocUuid = () => `MOCK-doc-${cryptoUuid()}`;
function cryptoUuid() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID().split('-')[0];
  }
  return Math.random().toString(36).slice(2, 10);
}

onMounted(async () => {
  loading.value = true;
  try {
    // If we got here after a submit_failed -> Back to Annotation, the user
    // already has a saved annotation; prefer it so edits aren't lost. The
    // /tree path is the fresh-classifier fallback (and the first-time path).
    const existing = await useGetMeasurementAnnotation(props.measurement.id).catch(() => undefined);
    if (existing && existing.descriptions) {
      descriptions.value = reactive(existing.descriptions) as FhirCdaDescriptions;
    } else {
      const tree = await useGetMeasurementTree(props.measurement.id);
      descriptions.value = reactive(tree.descriptions) as FhirCdaDescriptions;
      skippedSamples.value = tree.skippedSamples ?? [];
    }
    selectedPatients.value = descriptions.value!.patients.map((p) => p.name);
  } catch (err: any) {
    alertText.value =
      err?.response?.data?.detail || err?.message || 'Failed to load annotation tree.';
  } finally {
    loading.value = false;
  }
});

async function handleSubmit() {
  if (!descriptions.value || submitting.value) return;
  submitting.value = true;
  alertText.value = '';
  try {
    const cleaned = stripAuto(descriptions.value);
    await useUpsertMeasurementAnnotation(props.measurement.id, cleaned);
    // Save-only: the annotation is now a draft. Upload to MinIO + FHIR is a
    // separate, explicit Approval action from the registry card menu.
    emit('saved');
  } catch (err: any) {
    alertText.value =
      err?.response?.data?.detail || err?.message || 'Save failed; please try again.';
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.json-preview {
  background: rgba(15, 25, 35, 0.6);
  color: #b3e5fc;
  font-size: 11px;
  line-height: 1.4;
  border-radius: 6px;
  padding: 8px;
  max-height: 400px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
