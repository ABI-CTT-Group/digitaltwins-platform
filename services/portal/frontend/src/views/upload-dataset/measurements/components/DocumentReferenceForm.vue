<template>
  <div>
    <div
      v-for="patient in selectedPatientObjects"
      :key="patient.name"
      class="mb-4"
    >
      <h4 class="text-subtitle-1 text-cyan-lighten-2 mb-2">
        {{ patient.name }} — Document References ({{ patient.documentReference.length }})
      </h4>

      <v-card
        v-for="(doc, idx) in patient.documentReference"
        :key="`${patient.name}-doc-${idx}`"
        class="mb-3 pa-3"
        variant="outlined"
        color="grey-lighten-2"
      >
        <div class="d-flex align-center justify-space-between mb-2">
          <v-chip
            v-if="autoMarker(doc)"
            size="x-small"
            color="cyan-lighten-3"
            prepend-icon="mdi-auto-fix"
          >
            Auto from {{ autoMarker(doc).samplePath }}
          </v-chip>
          <div v-else class="text-caption text-grey-darken-1">Manual entry</div>
          <v-btn
            icon="mdi-close"
            variant="text"
            density="comfortable"
            color="red"
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

        <div class="text-caption text-grey-darken-1 mb-1">
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
                  color="red"
                  @click="doc.attachments.splice(aIdx, 1)"
                />
              </td>
            </tr>
            <tr v-if="!doc.attachments.length">
              <td colspan="4" class="text-center text-caption text-grey">
                No attachments. Click "Add attachment" below.
              </td>
            </tr>
          </tbody>
        </v-table>

        <v-btn
          variant="text"
          color="cyan"
          size="small"
          prepend-icon="mdi-plus"
          @click="addAttachment(doc)"
        >
          Add attachment
        </v-btn>
      </v-card>

      <v-btn
        variant="tonal"
        color="cyan"
        size="small"
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
