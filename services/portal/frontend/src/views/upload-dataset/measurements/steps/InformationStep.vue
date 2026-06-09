<template>
  <v-alert v-show="showAlert" :text="alertText" title="Required Fields Missing" type="error" />
  <v-alert
    v-if="pendingUploads.length && !source"
    type="warning"
    variant="tonal"
    class="mb-3"
  >
    <div class="text-subtitle-2 mb-1">Unfinished upload(s)</div>
    <div
      v-for="p in pendingUploads"
      :key="p.id"
      class="d-flex align-center justify-space-between text-caption py-1"
    >
      <span>{{ p.name }} — {{ p.percent }}% uploaded. Re-drop the same folder below to resume.</span>
      <v-btn size="x-small" variant="text" color="error" @click="cancelPending(p.id)">Cancel</v-btn>
    </div>
  </v-alert>
  <v-alert
    v-if="resumeId"
    type="info"
    variant="tonal"
    class="mb-3"
    text="Resuming a previous upload of this source — already-sent chunks will be skipped."
  />
  <div>
    <h3 class="step-heading">Measurements Information</h3>
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
      <p class="text-caption step-sub mb-2">
        Drag a folder or .zip of a SPARC measurements dataset. Large datasets
        upload in resumable chunks; patients and samples are detected on the
        next step.
      </p>
      <MeasurementChunkedDropzone
        ref="dropzone"
        :max-total-bytes="measurementUploadMaxBytes"
        @source-selected="onSourceSelected"
        @pause-requested="onPause"
        @resume-requested="onResume"
        @cancel-requested="onUploadCancel"
      />
    </v-form>

    <v-divider class="mb-5 mt-5" :thickness="3" />
    <div class="d-flex flex-row justify-center">
      <v-btn
        color="#9fb4bf"
        text="Cancel"
        variant="text"
        :min-width="150"
        rounded="lg"
        class="text-none ma-5"
        :disabled="submitting"
        @click="handleCancel"
      />
      <v-btn
        color="#5fd6e8"
        text="Upload & Continue"
        variant="tonal"
        :min-width="200"
        rounded="lg"
        class="text-none ma-5"
        :loading="submitting"
        :disabled="submitting || !canContinue"
        @click="handleSubmit"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue';
import MeasurementChunkedDropzone from '../../components/MeasurementChunkedDropzone.vue';
import type { LocalSource } from '@/bootstrap/upload_source';
import {
  ChunkedUploader,
  findResumableUpload,
  loadPendingUploads,
  clearPending,
  type UploaderPhase,
} from '@/bootstrap/measurement_upload';
import { useCheckName } from '@/bootstrap/api_helpers';
import {
  useMeasurementConfig,
  useUploadStatus,
  useUploadCancel,
} from '@/bootstrap/measurement_api';
import { readSampleTypesFromFiles, buildSampleTypeDescription } from '../components/sampleTypes';
import type { CheckNameResponse, MeasurementResponse } from '@/models/types';

// Operator-tunable upload ceiling (MAX_UPLOAD_MB, default 20 GiB), fetched on
// mount; the local fallback keeps the dropzone usable if config is unreachable.
const DEFAULT_MAX_UPLOAD_BYTES = 20 * 1024 * 1024 * 1024;
const measurementUploadMaxBytes = ref<number>(DEFAULT_MAX_UPLOAD_BYTES);

const emit = defineEmits<{
  (e: 'created', m: MeasurementResponse): void;
  (e: 'cancel'): void;
}>();

const form = ref();
const dropzone = ref<InstanceType<typeof MeasurementChunkedDropzone> | null>(null);
const submitting = ref(false);

const formData = reactive<{ name: string; description: string }>({ name: '', description: '' });

const source = ref<LocalSource | undefined>(undefined);
const resumeId = ref<string | null>(null);
const uploader = ref<ChunkedUploader | null>(null);

// Unfinished uploads recorded in this browser. Surfaced on mount so the user
// knows they can resume by re-dropping the same folder (file bytes don't
// survive a reload, so resume can't be automatic).
const pendingUploads = ref<{ id: string; name: string; percent: number }[]>([]);

// Track auto-filled values so we never clobber what the user typed.
const autoFilledName = ref('');
const autoFilledDescription = ref('');

const nameErr = ref<CheckNameResponse | undefined>(undefined);
const nameRules = [(v: string) => !!v?.trim() || 'Dataset name is required'];
const nameErrorMessages = computed<string[]>(() => {
  if (!nameErr.value) return [];
  return nameErr.value.available ? [] : [nameErr.value.message || 'Name already exists'];
});

const showAlert = ref(false);
const alertText = ref('');

const canContinue = computed(
  () => !!source.value && !!formData.name.trim() && nameErr.value?.available !== false,
);

onMounted(async () => {
  try {
    const cfg = await useMeasurementConfig();
    if (typeof cfg.maxUploadBytes === 'number' && cfg.maxUploadBytes > 0) {
      measurementUploadMaxBytes.value = cfg.maxUploadBytes;
    }
  } catch (err) {
    console.warn('useMeasurementConfig failed; using default upload ceiling', err);
  }
  void refreshPendingList();
});

// Build the resume banner: read the localStorage index, fetch each upload's
// server-side progress, and drop entries whose measurement no longer exists.
async function refreshPendingList(): Promise<void> {
  const out: { id: string; name: string; percent: number }[] = [];
  for (const p of loadPendingUploads()) {
    try {
      const status = await useUploadStatus(p.measurementId);
      const total = status.files.reduce((s, f) => s + f.size, 0);
      const got = status.files.reduce((s, f) => s + f.bytes, 0);
      out.push({
        id: p.measurementId,
        name: p.name,
        percent: total > 0 ? Math.round((got / total) * 100) : 0,
      });
    } catch (err: any) {
      if (err?.response?.status === 404) clearPending(p.measurementId);
    }
  }
  pendingUploads.value = out;
}

async function cancelPending(id: string): Promise<void> {
  try {
    await useUploadCancel(id);
  } catch (err) {
    console.warn('Cancel pending upload failed (clearing local index anyway)', err);
  }
  clearPending(id);
  pendingUploads.value = pendingUploads.value.filter((p) => p.id !== id);
}

const onSourceSelected = (selected: LocalSource) => {
  source.value = selected;
  // Exact-manifest match against a recorded pending upload → offer resume.
  resumeId.value = findResumableUpload(selected);

  const derived = (selected.rootName || '').replace(/\.zip$/i, '').trim();
  const nameIsUntouched = !formData.name.trim() || formData.name === autoFilledName.value;
  if (derived && nameIsUntouched) {
    formData.name = derived;
    autoFilledName.value = derived;
    onNameBlur();
  }

  if (selected.kind === 'folder') {
    void autofillDescriptionFromSamples(selected.files);
  }
};

async function autofillDescriptionFromSamples(files: File[]): Promise<void> {
  const descIsUntouched =
    !formData.description.trim() || formData.description === autoFilledDescription.value;
  if (!descIsUntouched) return;

  const types = await readSampleTypesFromFiles(files);
  const summary = buildSampleTypeDescription(types);
  if (!summary) return;

  const stillUntouched =
    !formData.description.trim() || formData.description === autoFilledDescription.value;
  if (!stillUntouched) return;

  formData.description = summary;
  autoFilledDescription.value = summary;
}

const onPause = () => uploader.value?.pause();
const onResume = () => uploader.value?.resume();

const onUploadCancel = () => {
  void uploader.value?.cancel();
  uploader.value = null;
  submitting.value = false;
  source.value = undefined;
  resumeId.value = null;
  formData.name = '';
  autoFilledName.value = '';
  formData.description = '';
  autoFilledDescription.value = '';
  nameErr.value = undefined;
  showAlert.value = false;
  dropzone.value?.setProgress({ phase: 'reset' });
};

const onNameBlur = async () => {
  if (!formData.name?.trim()) {
    nameErr.value = undefined;
    return;
  }
  try {
    nameErr.value = await useCheckName('measurement', formData.name.trim());
  } catch (e: any) {
    const msg = e?.response?.data?.detail || 'Name already exists';
    nameErr.value = { available: false, message: msg } as CheckNameResponse;
  }
};

async function handleSubmit() {
  if (submitting.value) return;

  const { valid } = await form.value.validate();
  await onNameBlur();
  const validName = valid && nameErr.value?.available !== false;
  if (!validName || !source.value) {
    showAlert.value = true;
    alertText.value = !source.value
      ? 'Drop a SPARC measurements folder or .zip before continuing.'
      : 'Pick a unique dataset name before continuing.';
    return;
  }

  showAlert.value = false;
  submitting.value = true;

  const up = new ChunkedUploader(
    source.value,
    { name: formData.name.trim(), description: formData.description?.trim() || undefined },
    {
      onProgress: (p) =>
        dropzone.value?.setProgress({
          phase: 'upload',
          sentBytes: p.sentBytes,
          totalBytes: p.totalBytes,
          percent: p.percent,
          sentParts: p.sentParts,
          totalParts: p.totalParts,
        }),
      onPhase: (phase: UploaderPhase) => {
        if (phase === 'paused') dropzone.value?.setProgress({ phase: 'paused' });
        else if (phase === 'finalizing') dropzone.value?.setProgress({ phase: 'finalizing' });
      },
    },
    resumeId.value ?? undefined,
  );
  uploader.value = up;

  try {
    const created = await up.start();
    dropzone.value?.setProgress({ phase: 'ready' });
    emit('created', created);
  } catch (err: any) {
    if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError' || err?.name === 'AbortError') {
      dropzone.value?.setProgress({ phase: 'reset' });
    } else {
      const msg = err?.response?.data?.detail || err?.message || 'Upload failed';
      dropzone.value?.setProgress({ phase: 'error', message: msg });
    }
  } finally {
    submitting.value = false;
    uploader.value = null;
  }
}

function handleCancel() {
  void uploader.value?.cancel();
  emit('cancel');
}
</script>

<style scoped>
.step-heading {
  color: #5fd6e8;
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 500;
}
.step-sub { color: #9fb4bf; }
.label-aqua { color: #5fd6e8; }
.info-card {
  background: rgba(95, 214, 232, 0.05) !important;
  border: 1px solid rgba(95, 214, 232, 0.2);
}
</style>
