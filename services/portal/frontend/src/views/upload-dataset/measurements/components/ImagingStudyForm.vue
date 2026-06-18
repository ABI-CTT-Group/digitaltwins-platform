<template>
  <div class="rform" style="--type: #c792ea">
    <div
      v-for="patient in selectedPatientObjects"
      :key="patient.name"
      class="rform__group"
    >
      <div class="rform__head">
        <span class="rform__dot"></span>
        <span class="rform__name">{{ patient.name }}</span>
        <span class="rform__count">{{ patient.imagingStudy.length }} imaging stud{{ patient.imagingStudy.length === 1 ? 'y' : 'ies' }}</span>
      </div>

      <v-card
        v-for="(study, idx) in patient.imagingStudy"
        :key="`${patient.name}-img-${idx}`"
        class="mb-3 pa-4 field-card"
        flat
      >
        <div class="d-flex align-center justify-space-between mb-2">
          <div class="d-flex align-center ga-2">
            <v-chip
              size="x-small"
              :color="modalityColor(study)"
              variant="tonal"
              prepend-icon="mdi-image-multiple"
            >
              {{ modalityLabel(study) }}
            </v-chip>
            <v-chip
              v-if="autoMarker(study)"
              size="x-small"
              color="#5fd6e8"
              variant="tonal"
              prepend-icon="mdi-auto-fix"
            >
              Auto from {{ autoMarker(study).samplePath }}
            </v-chip>
          </div>
          <v-btn
            icon="mdi-close"
            variant="text"
            density="comfortable"
            color="#ff6b6b"
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
          <div class="text-caption series-label mb-1">
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
              color="#5fd6e8"
              size="small"
              class="text-none"
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
  if (m === 'dcm') return '#c792ea';
  if (m === 'nrrd') return '#7c9cff';
  if (m === 'nii' || m === 'nii.gz') return '#6fd49a';
  return '#9fb4bf';
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
.series-label { color: var(--type); font-weight: 700; }
.rform__group { margin-bottom: 26px; }
.rform__head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
}
.rform__dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--type);
  box-shadow: 0 0 10px color-mix(in srgb, var(--type) 70%, transparent);
}
.rform__name {
  font-family: 'Fraunces', Georgia, serif;
  font-size: 1.12rem;
  font-weight: 500;
  color: #fff;
}
.rform__count {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--type);
  padding: 2px 9px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--type) 13%, transparent);
  border: 1px solid color-mix(in srgb, var(--type) 32%, transparent);
}
.field-card {
  background: rgba(255, 255, 255, 0.02) !important;
  border: 1px solid rgba(120, 200, 220, 0.12);
  border-left: 3px solid color-mix(in srgb, var(--type) 65%, transparent);
  border-radius: 12px !important;
}
.series-card {
  background: color-mix(in srgb, var(--type) 5%, transparent);
  border-radius: 10px;
  border: 1px solid color-mix(in srgb, var(--type) 22%, transparent);
}

/* Mocked / readonly fields: render as quiet inset values, not raised grey
   solo boxes, so they sit calmly inside the glass card. */
.rform :deep(.v-field--variant-solo) {
  background: rgba(255, 255, 255, 0.016) !important;
  box-shadow: none !important;
  border: 1px solid rgba(120, 200, 220, 0.1);
  border-radius: 9px !important;
}
.rform :deep(.v-field--variant-solo .v-field__input) {
  color: #c3d2d8;
  font-weight: 600;
}
.rform :deep(.v-field--variant-solo .v-label) { color: #7f97a1; }
</style>
