<template>
  <div class="rform" style="--type: #ffb74d">
    <div
      v-for="patient in selectedPatientObjects"
      :key="patient.name"
      class="rform__group"
    >
      <div class="rform__head">
        <span class="rform__dot"></span>
        <span class="rform__name">{{ patient.name }}</span>
        <span class="rform__count">{{ patient.documentReference.length }} document{{ patient.documentReference.length === 1 ? '' : 's' }}</span>
      </div>

      <v-card
        v-for="(doc, idx) in patient.documentReference"
        :key="`${patient.name}-doc-${idx}`"
        class="mb-3 pa-4 field-card"
        flat
      >
        <div class="d-flex align-center justify-space-between mb-2">
          <v-chip
            v-if="autoMarker(doc)"
            size="x-small"
            color="#5fd6e8"
            variant="tonal"
            prepend-icon="mdi-auto-fix"
          >
            Auto from {{ autoMarker(doc).samplePath }}
          </v-chip>
          <div v-else class="text-caption text-muted">Manual entry</div>
          <v-btn
            icon="mdi-close"
            variant="text"
            density="comfortable"
            color="#ff6b6b"
            @click="removeDoc(patient, idx)"
          />
        </div>

        <v-text-field
          v-model="doc.description"
          label="Title / description"
          density="compact"
          hide-details
          class="mb-2"
        />

        <div class="text-caption text-muted mb-1">
          Attachments ({{ doc.attachments.length }})
        </div>
        <v-table density="compact" class="mb-2">
          <thead>
            <tr>
              <th>File</th>
              <th>Content type</th>
              <th class="text-end">Size</th>
              <th />
            </tr>
          </thead>
          <tbody>
            <tr v-for="(a, aIdx) in doc.attachments" :key="`a-${aIdx}`">
              <td>
                <v-text-field
                  v-model="a.title"
                  density="compact"
                  variant="plain"
                  hide-details
                />
              </td>
              <td>
                <v-combobox
                  v-model="a.contentType"
                  :items="contentTypes"
                  density="compact"
                  variant="plain"
                  hide-details
                />
              </td>
              <td class="text-end text-caption">{{ formatBytes(a.size) }}</td>
              <td>
                <v-btn
                  icon="mdi-close"
                  variant="text"
                  density="comfortable"
                  size="small"
                  color="#ff6b6b"
                  @click="doc.attachments.splice(aIdx, 1)"
                />
              </td>
            </tr>
            <tr v-if="!doc.attachments.length">
              <td colspan="4" class="text-center text-caption text-muted">
                No attachments. Click "Add attachment" below.
              </td>
            </tr>
          </tbody>
        </v-table>

        <v-btn
          variant="text"
          color="#5fd6e8"
          size="small"
          class="text-none"
          prepend-icon="mdi-plus"
          @click="addAttachment(doc)"
        >
          Add attachment
        </v-btn>
      </v-card>

      <v-btn
        variant="tonal"
        color="#5fd6e8"
        size="small"
        class="text-none"
        prepend-icon="mdi-plus"
        @click="addDoc(patient)"
      >
        Add manual document reference
      </v-btn>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type {
  DocumentAttachment,
  DocumentReferenceDescription,
  FhirCdaDescriptions,
  FhirCdaPatient,
} from '@/models/types';
import { COMMON_CONTENT_TYPES } from './fhirCodes';

const props = defineProps<{
  descriptions: FhirCdaDescriptions;
  selectedPatients: string[];
  mockUuidFn: () => string;
}>();

const selectedPatientObjects = computed<FhirCdaPatient[]>(() =>
  props.descriptions.patients.filter((p) => props.selectedPatients.includes(p.name)),
);

const contentTypes = COMMON_CONTENT_TYPES;

const autoMarker = (doc: DocumentReferenceDescription): any =>
  (doc as any)._auto ?? (doc as any).Auto;

const removeDoc = (patient: FhirCdaPatient, idx: number) => {
  patient.documentReference.splice(idx, 1);
};

const addDoc = (patient: FhirCdaPatient) => {
  patient.documentReference.push({
    resourceType: 'DocumentReference',
    uuid: props.mockUuidFn(),
    description: '',
    display: '',
    attachments: [],
  });
};

const addAttachment = (doc: DocumentReferenceDescription) => {
  doc.attachments.push({
    url: '',
    contentType: 'application/octet-stream',
    title: '',
    size: 0,
  } satisfies DocumentAttachment);
};

const formatBytes = (n?: number) => {
  if (n === undefined || n === null) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  if (n < 1024 * 1024 * 1024) return `${(n / 1024 / 1024).toFixed(1)} MB`;
  return `${(n / 1024 / 1024 / 1024).toFixed(2)} GB`;
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
