<template>
  <v-alert v-show="alertText" :text="alertText" type="error" closable @click:close="alertText = ''" />

  <div class="annotate">
    <header class="annotate__head">
      <p class="annotate__eyebrow">Step 2 · FHIR</p>
      <h3 class="annotate__title">Annotate measurements</h3>
      <p class="annotate__sub">Review the auto-classified resources, fine-tune codes and metadata, then save as a draft.</p>
    </header>

    <v-progress-circular
      v-if="loading"
      indeterminate
      color="#5fd6e8"
      class="ma-4"
    />

    <template v-else-if="descriptions">
      <div class="stat-strip">
        <div class="stat stat--dataset">
          <span class="stat__label">Dataset</span>
          <span class="stat__value stat__value--text">{{ descriptions.dataset.name }}</span>
        </div>
        <div class="stat">
          <span class="stat__label">Patients</span>
          <span class="stat__value">{{ descriptions.patients.length }}</span>
        </div>
        <div class="stat">
          <span class="stat__label">Samples</span>
          <span class="stat__value">{{ totalSamples }}</span>
        </div>
        <div class="stat">
          <span class="stat__label">Auto-classified</span>
          <span class="stat__value">{{ autoCounts.observations + autoCounts.imagingStudy + autoCounts.documentReference }}</span>
          <span class="stat__break">
            <span style="color:#5fd6e8">{{ autoCounts.observations }} obs</span> ·
            <span style="color:#c792ea">{{ autoCounts.imagingStudy }} img</span> ·
            <span style="color:#ffb74d">{{ autoCounts.documentReference }} doc</span>
          </span>
        </div>
      </div>

      <v-alert
        v-if="skippedSamples.length"
        variant="tonal"
        type="warning"
        class="mb-4"
        :title="`Skipped ${skippedSamples.length} empty sample(s)`"
      >
        <div class="text-caption">{{ skippedSamples.join(', ') }}</div>
      </v-alert>

      <PatientSelector
        :patients="patientNames"
        :selected="selectedPatients"
        @update:selected="selectedPatients = $event"
      />

      <v-tabs v-model="activeTab" align-tabs="start" :color="tabAccent" class="annotate__tabs mb-4">
        <v-tab value="observation" class="text-none">
          <v-icon icon="mdi-pulse" size="18" class="mr-2" />Observations
        </v-tab>
        <v-tab value="imaging" class="text-none">
          <v-icon icon="mdi-image-multiple-outline" size="18" class="mr-2" />Imaging Studies
        </v-tab>
        <v-tab value="document" class="text-none">
          <v-icon icon="mdi-file-document-outline" size="18" class="mr-2" />Document References
        </v-tab>
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
        color="#9fb4bf"
        text="Cancel"
        variant="text"
        :min-width="150"
        rounded="lg"
        class="text-none ma-5"
        :disabled="submitting"
        @click="emit('cancel')"
      />
      <v-btn
        color="#5fd6e8"
        text="Save annotation"
        variant="tonal"
        :min-width="200"
        rounded="lg"
        class="text-none ma-5"
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

// The active tab's indicator + ripple takes that resource type's accent so the
// three FHIR categories stay colour-coded across the tabs and their forms.
const tabAccent = computed(() => {
  switch (activeTab.value) {
    case 'imaging': return '#c792ea';
    case 'document': return '#ffb74d';
    default: return '#5fd6e8';
  }
});

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
    // Persist the descriptions WITH their `_auto` markers intact so reopening a
    // saved draft can still render the auto-classified count and the modality /
    // "Auto from…" chips (all of which read `_auto`). The markers are inert
    // downstream: `apply_descriptions` builds fhir.json from named fields only
    // and never serialises `_auto`, and the Preview panel below strips them for
    // display. Re-deriving them on load isn't an option — `/tree` mints fresh
    // random UUIDs each call, so there's no stable key to merge markers back on.
    await useUpsertMeasurementAnnotation(props.measurement.id, descriptions.value);
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
.annotate { padding: 6px 6px 4px; }
.annotate__head { margin-bottom: 22px; }
.annotate__eyebrow {
  margin: 0 0 6px;
  font-size: 0.64rem;
  font-weight: 700;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: #5fd6e8;
}
.annotate__title {
  margin: 0;
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 500;
  font-size: 1.7rem;
  line-height: 1.15;
  color: #fff;
}
.annotate__sub {
  margin: 8px 0 0;
  font-size: 0.9rem;
  color: #9fb4bf;
  max-width: 64ch;
}

/* Airy stat strip — big Fraunces numbers over small uppercase labels. */
.stat-strip {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1.4fr;
  gap: 14px;
  margin-bottom: 22px;
  padding: 18px 20px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.022);
  border: 1px solid rgba(120, 200, 220, 0.14);
}
.stat { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.stat__label {
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #7f97a1;
}
.stat__value {
  font-family: 'Fraunces', Georgia, serif;
  font-size: 1.7rem;
  font-weight: 500;
  line-height: 1.1;
  color: #fff;
}
.stat__value--text {
  font-size: 1.1rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.stat__break { font-size: 0.72rem; font-weight: 700; color: #9fb4bf; margin-top: 2px; }
@media (max-width: 720px) {
  .stat-strip { grid-template-columns: 1fr 1fr; }
}

.annotate__tabs { border-bottom: 1px solid rgba(120, 200, 220, 0.12); }

.json-preview {
  background: rgba(8, 18, 26, 0.6);
  color: #cfeaf0;
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
