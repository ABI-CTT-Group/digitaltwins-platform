<template>
  <div>
    <div
      v-for="patient in selectedPatientObjects"
      :key="patient.name"
      class="mb-4"
    >
      <h4 class="text-subtitle-1 text-cyan-lighten-2 mb-2">
        {{ patient.name }} — Imaging Studies ({{ patient.imagingStudy.length }})
      </h4>

      <v-card
        v-for="(study, idx) in patient.imagingStudy"
        :key="`${patient.name}-img-${idx}`"
        class="mb-3 pa-3"
        variant="outlined"
        color="grey-lighten-2"
      >
        <div class="d-flex align-center justify-space-between mb-2">
          <div class="d-flex align-center ga-2">
            <v-chip
              size="x-small"
              :color="modalityColor(study)"
              prepend-icon="mdi-image-multiple"
            >
              {{ modalityLabel(study) }}
            </v-chip>
            <v-chip
              v-if="autoMarker(study)"
              size="x-small"
              color="cyan-lighten-3"
              prepend-icon="mdi-auto-fix"
            >
              Auto from {{ autoMarker(study).samplePath }}
            </v-chip>
          </div>
          <v-btn
            icon="mdi-close"
            variant="text"
            density="comfortable"
            color="red"
            @click="removeStudy(patient, idx)"
          />
        </div>

        <v-text-field
          v-model="study.description"
          label="Description"
          density="compact"
          hide-details
          class="mb-2"
        />

        <v-text-field
          :model-value="study.uuid"
          label="UUID (mocked)"
          density="compact"
          variant="solo"
          readonly
          hide-details
          class="mb-1"
        />
        <v-text-field
          :model-value="study.endpointUrl"
          label="Endpoint URL (mocked; filled in submit finalize)"
          density="compact"
          variant="solo"
          readonly
          hide-details
          class="mb-2"
        />

        <div
          v-for="(series, sIdx) in study.series"
          :key="`${patient.name}-img-${idx}-series-${sIdx}`"
          class="pa-2 mb-1 series-card"
        >
          <div class="text-caption text-cyan-darken-3 mb-1">
            Series {{ sIdx + 1 }}
          </div>
          <div class="d-flex flex-row ga-2">
            <v-text-field
              :model-value="series.name"
              label="Sample folder"
              density="compact"
              variant="solo"
              readonly
              hide-details
              class="flex-grow-1"
            />
            <v-text-field
              :model-value="series.numberOfInstances"
              label="# Instances"
              density="compact"
              variant="solo"
              readonly
              hide-details
              style="max-width: 140px;"
            />
          </div>
          <v-combobox
            :model-value="bodySiteDisplay(series.bodySite)"
            :items="bodySiteOptions"
            item-title="display"
            return-object
            label="Body site (SNOMED CT)"
            density="compact"
            hide-details
            class="mt-2"
            @update:model-value="(val) => setBodySite(series, val)"
          />
        </div>
      </v-card>

      <!-- Tooltip activator sits on the wrapper span, not the button: a disabled
           v-btn swallows hover events, so the span is what surfaces the hint. -->
      <v-tooltip
        text="Manual ImagingStudy entry requires a sample folder on disk; rebuild dataset to add"
        location="top"
        open-delay="250"
      >
        <template #activator="{ props: tip }">
          <span v-bind="tip" class="d-inline-flex">
            <v-btn
              variant="tonal"
              color="cyan"
              size="small"
              prepend-icon="mdi-plus"
              :disabled="true"
            >
              Add manual imaging study
            </v-btn>
          </span>
        </template>
      </v-tooltip>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type {
  FhirCdaDescriptions,
  FhirCdaPatient,
  ImagingStudyDescription,
  ImagingStudySeries,
} from '@/models/types';
import { SNOMED_BODY_SITES } from './fhirCodes';

const props = defineProps<{
  descriptions: FhirCdaDescriptions;
  selectedPatients: string[];
}>();

const selectedPatientObjects = computed<FhirCdaPatient[]>(() =>
  props.descriptions.patients.filter((p) => props.selectedPatients.includes(p.name)),
);

const bodySiteOptions = SNOMED_BODY_SITES;

const autoMarker = (study: ImagingStudyDescription): any =>
  (study as any)._auto ?? (study as any).Auto;

const modalityLabel = (study: ImagingStudyDescription): string => {
  const m = autoMarker(study)?.modality;
  return m ? m.toUpperCase() : 'IMG';
};

const modalityColor = (study: ImagingStudyDescription): string => {
  const m = (autoMarker(study)?.modality || '').toLowerCase();
  if (m === 'dcm') return 'deep-purple-lighten-3';
  if (m === 'nrrd') return 'indigo-lighten-3';
  if (m === 'nii' || m === 'nii.gz') return 'teal-lighten-3';
  return 'grey-lighten-2';
};

const bodySiteDisplay = (bs?: string | { display?: string; code?: string } | null) => {
  if (!bs) return undefined;
  if (typeof bs === 'string') return bs;
  return bs.display || bs.code;
};

const setBodySite = (series: ImagingStudySeries, selected: any) => {
  if (!selected) {
    (series as any).bodySite = undefined;
    return;
  }
  if (typeof selected === 'string') {
    // user typed free-form; keep as display-only string
    (series as any).bodySite = selected;
    return;
  }
  // SNOMED entry from the list
  (series as any).bodySite = {
    system: selected.system,
    code: selected.code,
    display: selected.display,
  };
};

const removeStudy = (patient: FhirCdaPatient, idx: number) => {
  patient.imagingStudy.splice(idx, 1);
};
</script>

<style scoped>
.series-card {
  background: rgba(0, 188, 212, 0.06);
  border-radius: 6px;
  border: 1px dashed rgba(0, 188, 212, 0.3);
}
</style>
