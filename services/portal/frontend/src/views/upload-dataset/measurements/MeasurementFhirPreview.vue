<template>
  <v-container class="d-flex flex-column align-center" style="margin-top: 70px;">
    <div class="responsive-box mb-3">
      <BackLink to="UploadMeasurementsDataset" label="Measurements" />
    </div>
    <v-card
      class="pa-6 responsive-box"
      elevation="12"
      style="background: rgba(15, 25, 35, 0.45); border-radius: 20px;"
    >
      <div class="d-flex align-center flex-wrap ga-2 mb-3">
        <h2 class="text-cyan flex-grow-1 text-truncate">
          fhir.json — {{ name || measurementId }}
        </h2>
        <v-btn
          variant="tonal"
          color="cyan"
          prepend-icon="mdi-content-copy"
          :disabled="!fhirJson"
          @click="copyJson"
        >
          Copy
        </v-btn>
        <v-btn
          variant="tonal"
          color="cyan"
          prepend-icon="mdi-download"
          :disabled="!fhirJson"
          @click="downloadJson"
        >
          Download
        </v-btn>
      </div>

      <v-alert
        type="info"
        variant="tonal"
        density="compact"
        class="mb-3"
        text="Endpoint URLs are placeholders until the dataset is approved & uploaded — they are finalized to the real stream-proxy URLs during approval."
      />

      <v-progress-circular v-if="loading" indeterminate color="cyan" class="ma-4" />

      <v-alert
        v-else-if="errorText"
        type="error"
        variant="tonal"
        :text="errorText"
      />

      <pre v-else class="json-preview">{{ prettyJson }}</pre>
    </v-card>
  </v-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import BackLink from '@/components/common/BackLink.vue';
// @ts-ignore - vue-toastification ships without type declarations
import { useToast } from 'vue-toastification';
import {
  useGetMeasurement,
  useMeasurementFhirPreview,
} from '@/bootstrap/measurement_api';

const route = useRoute();
const router = useRouter();
const toast = useToast();

const measurementId = String(route.params.id);
const name = ref('');
const fhirJson = ref<Record<string, any> | null>(null);
const loading = ref(true);
const errorText = ref('');

const prettyJson = computed(() =>
  fhirJson.value ? JSON.stringify(fhirJson.value, null, 2) : '',
);

onMounted(async () => {
  loading.value = true;
  try {
    // Fetch the row name for the heading/filename in parallel with the bundle.
    const [meas, fhir] = await Promise.all([
      useGetMeasurement(measurementId).catch(() => undefined),
      useMeasurementFhirPreview(measurementId),
    ]);
    name.value = meas?.name ?? '';
    fhirJson.value = fhir;
  } catch (err: any) {
    errorText.value =
      err?.response?.data?.detail || err?.message || 'Failed to load fhir.json preview.';
  } finally {
    loading.value = false;
  }
});

const copyJson = async () => {
  try {
    await navigator.clipboard.writeText(prettyJson.value);
    toast.success('Copied fhir.json to clipboard.');
  } catch {
    toast.error('Copy failed — your browser blocked clipboard access.');
  }
};

const downloadJson = () => {
  const blob = new Blob([prettyJson.value], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${name.value || 'measurement'}-fhir.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
};
</script>

<style scoped>
.responsive-box {
  width: 90%;
}
@media (min-width: 2100px) {
  .responsive-box {
    width: 75%;
  }
}
.json-preview {
  background: rgba(15, 25, 35, 0.6);
  color: #b3e5fc;
  font-size: 12px;
  line-height: 1.4;
  border-radius: 6px;
  padding: 12px;
  max-height: 70vh;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
</style>
