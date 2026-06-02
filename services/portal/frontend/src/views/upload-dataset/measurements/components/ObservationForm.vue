<template>
  <div>
    <div
      v-for="patient in selectedPatientObjects"
      :key="patient.name"
      class="mb-4"
    >
      <h4 class="text-subtitle-1 text-cyan-lighten-2 mb-2">
        {{ patient.name }} — Observations ({{ patient.observations.length }})
      </h4>

      <v-card
        v-for="(observation, idx) in patient.observations"
        :key="`${patient.name}-obs-${idx}`"
        class="mb-3 pa-3"
        variant="outlined"
        color="grey-lighten-2"
      >
        <div class="d-flex align-center justify-space-between mb-2">
          <v-chip
            v-if="autoMarker(observation)"
            size="x-small"
            color="cyan-lighten-3"
            prepend-icon="mdi-auto-fix"
          >
            Auto from {{ autoMarker(observation).samplePath }}
          </v-chip>
          <div v-else class="text-caption text-grey-darken-1">Manual entry</div>
          <v-btn
            icon="mdi-close"
            variant="text"
            density="comfortable"
            color="red"
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
          <v-radio label="Quantity" value="Quantity" color="cyan" />
          <v-radio label="String" value="String" color="cyan" class="ml-3" />
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
        color="cyan"
        size="small"
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
