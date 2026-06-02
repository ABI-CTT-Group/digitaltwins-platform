<template>
  <v-alert v-show="showAlert" :text="alertText" title="Required Fields Missing" type="error" />
  <div>
    <h3 class="text-cyan">Measurements Information</h3>
    <v-divider class="my-2 mb-5" :thickness="3" />

    <v-form ref="form" class="px-5">
      <h4 class="mb-1">Dataset name *</h4>
      <v-text-field
        v-model="formData.name"
        :rules="nameRules"
        :error-messages="nameErrorMessages"
        label="Dataset name"
        required
        clearable
        @blur="onNameBlur"
      />

      <h4 class="mb-1 mt-3">Description</h4>
      <v-textarea
        v-model="formData.description"
        label="What does this dataset contain? (optional)"
        rows="2"
        auto-grow
        clearable
      />

      <h4 class="mb-1 mt-3">Dataset source *</h4>
      <p class="text-caption text-grey-lighten-2 mb-2">
        Drag a folder or .zip of a SPARC measurements dataset. We auto-detect
        patients and samples after upload.
      </p>
      <LocalFolderDropzone
        ref="dropzone"
        :detected-folders="detectedFolders"
        :max-total-bytes="MEASUREMENT_UPLOAD_MAX_BYTES"
        @source-selected="onSourceSelected"
        @cancel-requested="onUploadCancel"
      />

      <v-card
        v-if="sourceMeta"
        class="mt-3 pa-3"
        variant="tonal"
        color="cyan-darken-3"
      >
        <div class="text-subtitle-2 text-cyan-lighten-3">Detected SPARC structure</div>
        <div class="text-caption">
          {{ sourceMeta.patients.length }} patient(s),
          {{ totalSamples }} sample(s),
          {{ totalFiles }} file(s).
        </div>
        <v-expansion-panels v-if="sourceMeta.patients.length" variant="accordion" class="mt-2">
          <v-expansion-panel>
            <v-expansion-panel-title>Preview patients / samples</v-expansion-panel-title>
            <v-expansion-panel-text>
              <ul class="text-caption">
                <li v-for="p in sourceMeta.patients" :key="p">
                  {{ p }} —
                  {{ (sourceMeta.samplesPerPatient[p] || []).length }} sample(s)
                </li>
              </ul>
            </v-expansion-panel-text>
          </v-expansion-panel>
        </v-expansion-panels>
      </v-card>
    </v-form>

    <v-divider class="mb-5 mt-5" :thickness="3" />
    <div class="d-flex flex-row justify-center">
      <v-btn
        color="red"
        text="Cancel"
        variant="tonal"
        :min-width="150"
        rounded="md"
        class="hover-animate ma-5"
        :disabled="submitting"
        @click="handleCancel"
      />
      <v-btn
        color="success"
        text="Continue to Annotation"
        variant="tonal"
        :min-width="200"
        rounded="md"
        class="hover-animate ma-5"
        :loading="submitting"
        :disabled="submitting"
        @click="handleSubmit"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue';
import LocalFolderDropzone from '../../components/LocalFolderDropzone.vue';
import {
  useUploadMeasurementSource,
  type LocalSource,
  type UploadProgress,
  type MeasurementUploadSourceResponse,
} from '@/bootstrap/upload_source';
import { useCheckName } from '@/bootstrap/api_helpers';
import { useCreateMeasurement } from '@/bootstrap/measurement_api';
import type { CheckNameResponse, MeasurementInformationStep, MeasurementResponse } from '@/models/types';

// Interim ceiling for measurement uploads — must stay in sync with nginx
// (`client_max_body_size 20g` on the measurement upload-source location) and
// the backend (`_MEASUREMENT_UPLOAD_MAX_BYTES` in measurement_router.py).
// Replaced by chunked upload once Plan 05 ships.
const MEASUREMENT_UPLOAD_MAX_BYTES = 20 * 1024 * 1024 * 1024;

const emit = defineEmits<{
  (e: 'created', m: MeasurementResponse): void;
  (e: 'cancel'): void;
}>();

const form = ref();
const dropzone = ref<InstanceType<typeof LocalFolderDropzone> | null>(null);
const submitting = ref(false);
const abortController = ref<AbortController | null>(null);

const formData = reactive<{ name: string; description: string }>({
  name: '',
  description: '',
});

const source = ref<LocalSource | undefined>(undefined);
const sourceMeta = ref<MeasurementUploadSourceResponse | undefined>(undefined);

const nameErr = ref<CheckNameResponse | undefined>(undefined);
const nameRules = [(v: string) => !!v?.trim() || 'Dataset name is required'];
const nameErrorMessages = computed<string[]>(() => {
  if (!nameErr.value) return [];
  return nameErr.value.available ? [] : [nameErr.value.message || 'Name already exists'];
});

const showAlert = ref(false);
const alertText = ref('');

// `detectedFolders` is what LocalFolderDropzone shows in its "Found in root"
// hint. For measurements that's the top-level patient list once we've
// hit /upload-source; before that it's empty (the dropzone is happy with []).
const detectedFolders = computed(() => sourceMeta.value?.patients ?? []);

const totalSamples = computed(() => {
  if (!sourceMeta.value) return 0;
  return Object.values(sourceMeta.value.samplesPerPatient).reduce(
    (sum, samples) => sum + samples.length,
    0,
  );
});

const totalFiles = computed(() => {
  if (!sourceMeta.value) return 0;
  return Object.values(sourceMeta.value.fileCountPerSample).reduce(
    (sum, n) => sum + n,
    0,
  );
});

const onSourceSelected = (selected: LocalSource) => {
  source.value = selected;
  // A new source invalidates any prior upload metadata; the dropzone
  // surfaces upload progress + final preview through `setProgress`.
  sourceMeta.value = undefined;
};

const onUploadCancel = () => {
  abortController.value?.abort();
  abortController.value = null;
  submitting.value = false;
};

const onNameBlur = async () => {
  if (!formData.name?.trim()) {
    nameErr.value = undefined;
    return;
  }
  try {
    nameErr.value = await useCheckName('measurement', formData.name.trim());
  } catch (e: any) {
    // useCheckName uses the same axios stack as the other endpoints — backend
    // returns 400 on conflict, which the helper surfaces by throwing. We
    // translate to an inline message rather than an alert so the user can
    // just fix the field.
    const msg = e?.response?.data?.detail || 'Name already exists';
    nameErr.value = { available: false, message: msg } as CheckNameResponse;
  }
};

async function uploadSource(): Promise<MeasurementUploadSourceResponse | null> {
  if (!source.value) return null;
  abortController.value = new AbortController();
  const onProgress = (p: UploadProgress) => dropzone.value?.setProgress(p);
  try {
    const res = await useUploadMeasurementSource(source.value, {
      onProgress,
      signal: abortController.value.signal,
    });
    dropzone.value?.setProgress({ phase: 'ready' });
    return res;
  } catch (err: any) {
    if (
      err?.code === 'ERR_CANCELED' ||
      err?.name === 'CanceledError' ||
      err?.name === 'AbortError'
    ) {
      dropzone.value?.setProgress({ phase: 'reset' });
    } else {
      const msg = err?.response?.data?.detail || err?.message || 'Upload failed';
      dropzone.value?.setProgress({ phase: 'error', message: msg });
    }
    return null;
  } finally {
    abortController.value = null;
  }
}

async function handleSubmit() {
  if (submitting.value) return;

  const { valid } = await form.value.validate();
  await onNameBlur();
  const validName = valid && nameErr.value?.available !== false;
  const hasSource = !!source.value;

  if (!validName || !hasSource) {
    showAlert.value = true;
    alertText.value = !hasSource
      ? 'Drop a SPARC measurements folder or .zip before continuing.'
      : 'Pick a unique dataset name before continuing.';
    return;
  }

  showAlert.value = false;
  submitting.value = true;
  try {
    // Re-upload only if we haven't already done it (e.g. user changed name
    // after a successful dropzone scan). sourceMeta presence is the marker.
    if (!sourceMeta.value) {
      const res = await uploadSource();
      if (!res) return; // dropzone already showed the error
      sourceMeta.value = res;
    }

    const payload: MeasurementInformationStep = {
      name: formData.name.trim(),
      description: formData.description?.trim() || undefined,
      uploadId: sourceMeta.value!.uploadId,
    };
    const created = await useCreateMeasurement(payload);
    emit('created', created);
  } catch (err: any) {
    showAlert.value = true;
    alertText.value =
      err?.response?.data?.detail ||
      err?.message ||
      'Failed to create the measurement record.';
  } finally {
    submitting.value = false;
  }
}

function handleCancel() {
  abortController.value?.abort();
  emit('cancel');
}
</script>
