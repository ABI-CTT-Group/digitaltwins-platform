<template>
  <div class="rform" style="--type: #5fd6e8">
    <div
      v-for="patient in selectedPatientObjects"
      :key="patient.name"
      class="rform__group"
    >
      <div class="rform__head">
        <span class="rform__dot"></span>
        <span class="rform__name">{{ patient.name }}</span>
        <span class="rform__count">{{ patient.observations.length }} observation{{ patient.observations.length === 1 ? '' : 's' }}</span>
      </div>

      <v-card
        v-for="(observation, idx) in patient.observations"
        :key="`${patient.name}-obs-${idx}`"
        class="mb-3 pa-4 field-card"
        flat
      >
        <div class="d-flex align-center justify-space-between mb-2">
          <v-chip
            v-if="autoMarker(observation)"
            size="x-small"
            color="#5fd6e8"
            variant="tonal"
            prepend-icon="mdi-auto-fix"
          >
            Auto from {{ autoMarker(observation).samplePath }}
          </v-chip>
          <div v-else class="text-caption text-muted">Manual entry</div>
          <v-btn
            icon="mdi-close"
            variant="text"
            density="comfortable"
            color="#ff6b6b"
            @click="removeObservation(patient, idx)"
          />
        </div>

        <div class="d-flex flex-row ga-2">
          <v-combobox
            v-model="observation.code"
            :items="loincItems"
            label="LOINC code"
            density="compact"
            :return-object="false"
            item-title="display"
            item-value="code"
            @update:model-value="onCodeSelected(observation, $event)"
            class="flex-grow-1"
          />
          <v-combobox
            v-model="observation.codeSystem"
            :items="systems"
            label="Code system"
            density="compact"
            class="flex-grow-1"
          />
        </div>

        <v-radio-group
          v-model="observation.valueType"
          inline
          density="compact"
          hide-details
          class="my-1"
        >
          <v-radio label="Quantity" value="Quantity" color="#5fd6e8" />
          <v-radio label="String" value="String" color="#5fd6e8" class="ml-3" />
        </v-radio-group>

        <div v-if="observation.valueType === 'Quantity'" class="d-flex flex-row ga-2">
          <v-text-field
            :model-value="observation.value"
            type="number"
            label="Value"
            density="compact"
            @update:model-value="(v) => updateQuantityValue(observation, v)"
            class="flex-grow-1"
          />
          <v-text-field
            v-model="observation.unit"
            label="Unit (e.g. kg, cm)"
            density="compact"
            class="flex-grow-1"
          />
        </div>
        <v-textarea
          v-else
          :model-value="String(observation.value ?? '')"
          label="Value (text)"
          density="compact"
          rows="2"
          auto-grow
          @update:model-value="(v) => (observation.value = v)"
        />

        <v-text-field
          v-model="observation.display"
          label="Display label (optional)"
          density="compact"
          hide-details
          class="mt-1"
        />
      </v-card>

      <v-btn
        variant="tonal"
        color="#5fd6e8"
        size="small"
        class="text-none"
        prepend-icon="mdi-plus"
        @click="addObservation(patient)"
      >
        Add manual observation
      </v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type {
  FhirCdaDescriptions,
  FhirCdaPatient,
  ObservationDescription,
} from '@/models/types';
import { LOINC_CODES, FHIR_OBSERVATION_SYSTEMS } from './fhirCodes';

const props = defineProps<{
  descriptions: FhirCdaDescriptions;
  selectedPatients: string[];
  mockUuidFn: () => string;
}>();

const selectedPatientObjects = computed<FhirCdaPatient[]>(() =>
  props.descriptions.patients.filter((p) => props.selectedPatients.includes(p.name)),
);

const loincItems = LOINC_CODES.map((c) => ({ code: c.code, display: `${c.code} — ${c.display}` }));
const systems = FHIR_OBSERVATION_SYSTEMS;

// The `_auto` marker is camelized to `Auto` by http.ts on inbound responses
// (see comment in stripAuto.ts) so we check both spellings to stay resilient.
const autoMarker = (obs: ObservationDescription): any =>
  (obs as any)._auto ?? (obs as any).Auto;

const updateQuantityValue = (observation: ObservationDescription, raw: string | number) => {
  if (raw === '' || raw === null || raw === undefined) {
    observation.value = undefined;
    return;
  }
  const num = typeof raw === 'number' ? raw : Number(raw);
  observation.value = Number.isFinite(num) ? num : raw;
};

const onCodeSelected = (observation: ObservationDescription, selected: any) => {
  if (typeof selected === 'string') {
    observation.code = selected;
    return;
  }
  if (selected && typeof selected === 'object' && 'code' in selected) {
    observation.code = selected.code;
    if (!observation.display && 'display' in selected) {
      observation.display = String(selected.display).split(' — ').pop() ?? '';
    }
  }
};

const removeObservation = (patient: FhirCdaPatient, idx: number) => {
  patient.observations.splice(idx, 1);
};

const addObservation = (patient: FhirCdaPatient) => {
  patient.observations.push({
    resourceType: 'Observation',
    uuid: props.mockUuidFn(),
    value: '',
    valueType: 'String',
    code: '',
    codeSystem: 'http://loinc.org',
    unit: '',
    display: '',
  });
};
</script>

<style scoped>
.text-muted { color: #7f97a1; }
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
</style>
