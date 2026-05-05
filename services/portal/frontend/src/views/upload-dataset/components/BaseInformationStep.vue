<template>
  <v-alert
    v-show="showAlert"
    :text="alertText"
    title="Required Fields Missing"
    type="error"
  />
  <div>
    <h3 class="text-cyan">
      {{ type === 'tool' ? 'Workflow Tool Information' : 'Workflow Information' }}
    </h3>
    <v-divider class="my-2 mb-5" :thickness="3" />

    <v-form ref="form" class="px-5">
      <!-- Tool-only: type selector -->
      <template v-if="type === 'tool'">
        <h4 class="my-2">Choose the workflow tool type *</h4>
        <v-radio-group
          v-model="formData.label"
          inline
          class="w-100 d-flex justify-start"
          @update:modelValue="handleLabelChange"
        >
          <v-radio color="success" label="Web GUI" value="GUI" />
          <v-radio color="success" label="CWL Script" value="Script" class="ml-2" />
        </v-radio-group>
      </template>

      <CommonInfoForm
        :cwl-repo-err="cwlRepoErr"
        :name-err="nameErr"
        v-model:repositoryUrl="formData.repositoryUrl"
        v-model:name="formData.name"
        v-model:author="formData.author"
        v-model:version="formData.version"
        v-model:description="formData.description"
        v-model:policy-checkbox="policyCheckbox"
        v-model:source-type="formData.sourceType"
        @onSoundUrlBlur="onRepoBlur"
        @onNameBlur="onNameBlur"
      >
        <!-- Source slot: visible only in local mode -->
        <template #dropzone>
          <LocalFolderDropzone
            ref="dropzone"
            :detected-folders="repoInfo.foldersInRoot"
            :detected-version="repoInfo.version"
            @folder-selected="onFolderSelected"
            @cancel-requested="onUploadCancel"
          />
        </template>

        <!-- Tool + GUI mode: backend & folder fields -->
        <div v-if="type === 'tool' && formData.label === 'GUI'" class="w-100">
          <div class="w-100">
            <h4 class="my-2">has backend? *</h4>
            <v-radio-group inline v-model="formData.hasBackend" class="w-100 d-flex justify-between">
              <v-radio label="Yes" :value="true" />
              <v-radio label="No" :value="false" />
            </v-radio-group>
          </div>
          <div class="w-100 d-flex flex-row">
            <div v-show="formData.hasBackend" class="w-100 mr-1">
              <h4 class="my-2">Frontend Folder Name *</h4>
              <v-select
                v-model="formData.frontendFolder"
                :items="foldersInRoot"
                :rules="frontendFolderRules"
                label="Frontend Folder"
              />
            </div>
            <div class="w-100 ml-1">
              <h4 class="my-2">Build Command *</h4>
              <v-text-field
                v-model="formData.frontendBuildCommand"
                :rules="frontendCommandRules"
                label="Frontend Build Command"
                clearable
                required
              />
            </div>
          </div>
          <div class="w-100 d-flex flex-row">
            <div v-show="formData.hasBackend" class="w-100 mr-1">
              <h4 class="mb-2">Backend Folder Name *</h4>
              <v-select
                v-model="formData.backendFolder"
                :items="foldersInRoot"
                :rules="backendFolderRules"
                label="Backend Folder"
              />
            </div>
            <div v-show="formData.hasBackend" class="w-100 ml-1">
              <h4 class="mb-2">Deploy Command (fixed) *</h4>
              <v-text-field
                v-model="formData.backendDeployCommand"
                bg-color="cyan-darken-4"
                variant="solo"
                readonly
              />
            </div>
          </div>
        </div>
      </CommonInfoForm>
    </v-form>

    <v-divider class="mb-5" :thickness="3" />
    <div class="d-flex flex-row justify-center">
      <v-btn
        color="red"
        text="Cancel"
        variant="tonal"
        :width="150"
        rounded="md"
        class="hover-animate ma-5"
        :disabled="submitting"
        @click="handleCancel"
      />
      <v-btn
        color="success"
        :text="type === 'tool' ? 'Submit Tool' : 'Submit Workflow'"
        variant="tonal"
        :width="150"
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
import { ref, reactive, watch, computed } from 'vue';
import CommonInfoForm from './CommonInfoForm.vue';
import LocalFolderDropzone from './LocalFolderDropzone.vue';
import type { ToolInformationStep, WorkflowInformationStep, CheckNameResponse } from '@/models/types';
import { useCheckName } from '@/bootstrap/api_helpers';
import { useGithubRepoInfo } from '@/composables/useGithubRepoInfo';
import { useLocalFolderInfo } from '@/composables/useLocalFolderInfo';
import {
  useUploadToolSource,
  useUploadWorkflowSource,
  type UploadProgress,
} from '@/bootstrap/upload_source';

// ---- props / emits --------------------------------------------------------
const props = defineProps<{ type: 'workflow' | 'tool' }>();
const emit = defineEmits(['cancel', 'submit']);

// ---- state ----------------------------------------------------------------
const form = ref();
const dropzone = ref<InstanceType<typeof LocalFolderDropzone> | null>(null);
const policyCheckbox = ref(false);
const showAlert = ref(false);
const alertText = ref('');
const cwlCheck = ref(props.type === 'workflow' ? false : true); // workflow needs CWL; tool (GUI) doesn't by default

const nameErr = ref<CheckNameResponse>();
const cwlRepoErr = ref<CheckNameResponse>();

// Tool form data (superset of workflow fields). Holds an in-memory `files`
// list that is *not* sent to the backend directly — it is zipped + uploaded
// during handleSubmit, after which `uploadId` is filled in.
const formData = reactive<ToolInformationStep & { files?: File[] }>({
  label: 'GUI',
  repositoryUrl: '',
  name: '',
  author: '',
  version: '0.0.0',
  description: '',
  frontendFolder: '',
  frontendBuildCommand: 'npm run build:plugin',
  hasBackend: true,
  backendFolder: '',
  backendDeployCommand: 'docker compose up --build -d',
  toolMetadata: {},
  sourceType: 'github',
  uploadId: undefined,
  files: undefined,
});

// ---- repo info composables (one for each source) -------------------------
const githubRepo = useGithubRepoInfo();
const localFolder = useLocalFolderInfo();
const repoInfo = computed(() =>
  formData.sourceType === 'local' ? localFolder.info.value : githubRepo.info.value,
);
const foldersInRoot = ref<string[]>([]);

watch(
  () => repoInfo.value.foldersInRoot,
  (v) => { foldersInRoot.value = v; },
  { immediate: true },
);

// ---- upload state ---------------------------------------------------------
const submitting = ref(false);
const abortController = ref<AbortController | null>(null);

// ---- validation rules (tool-only) -----------------------------------------
const frontendCommandRegex = /^(npm|yarn)\s+\S+/;
const frontendFolderRules = [
  (v: string) => (formData.hasBackend ? !!v || "Make sure the folder name matches the frontend folder in your tool's source" : true),
];
const frontendCommandRules = [
  (v: string) => !!v || 'Command to build your plugin (e.g., npm run build, yarn build)',
  (v: string) => frontendCommandRegex.test(v) || 'At the moment, the server supports only npm or yarn commands',
];
const backendFolderRules = [
  (v: string) => (!formData.hasBackend || !!v) || "The backend folder name can't be empty!",
];

// ---- handlers -------------------------------------------------------------
const handleLabelChange = () => {
  if (props.type !== 'tool') return;
  if (formData.label === 'Script') {
    formData.hasBackend = false;
    refreshSourceInfo();
  } else {
    cwlCheck.value = false;
    cwlRepoErr.value = undefined;
  }
  showAlert.value = false;
};

const isCwlCheckMode = () =>
  props.type === 'workflow' || formData.label === 'Script';

async function refreshSourceInfo() {
  const isCwlCheck = isCwlCheckMode();

  if (formData.sourceType === 'github') {
    if (!formData.repositoryUrl) return;
    const normalizedUrl = await githubRepo.refresh(formData.repositoryUrl, isCwlCheck);
    formData.repositoryUrl = normalizedUrl;
    formData.name = githubRepo.info.value.name;
    formData.author = githubRepo.info.value.author;
    if (githubRepo.info.value.version) formData.version = githubRepo.info.value.version;
  } else {
    if (!formData.files || formData.files.length === 0) return;
    await localFolder.refresh(formData.files, isCwlCheck);
    if (localFolder.info.value.name) formData.name = localFolder.info.value.name;
    if (localFolder.info.value.author) formData.author = localFolder.info.value.author;
    if (localFolder.info.value.version) formData.version = localFolder.info.value.version;
  }

  if (isCwlCheck) {
    cwlCheck.value = repoInfo.value.cwlExists;
    cwlRepoErr.value = repoInfo.value.cwlRepoErr;
  }
}

const onRepoBlur = async () => {
  await refreshSourceInfo();
  await onNameBlur();
};

const onFolderSelected = async (files: File[]) => {
  formData.files = files;
  // A new folder selection invalidates any prior upload.
  formData.uploadId = undefined;
  await refreshSourceInfo();
  await onNameBlur();
};

const onUploadCancel = () => {
  abortController.value?.abort();
  abortController.value = null;
  submitting.value = false;
};

const onNameBlur = async () => {
  const scope = props.type === 'tool' ? 'tool' : 'workflow';
  if (!formData.name) return;
  nameErr.value = await useCheckName(scope, formData.name);
};

const checkFolderInRoot = (name: string) => foldersInRoot.value.includes(name);

watch(() => formData.hasBackend, () => { policyCheckbox.value = false; });

// When the user toggles source, clear cross-mode artifacts so stale state
// from the other branch doesn't poison validation.
watch(() => formData.sourceType, (next, prev) => {
  if (next === prev) return;
  if (next === 'github') {
    formData.files = undefined;
    formData.uploadId = undefined;
    dropzone.value?.setProgress({ phase: 'reset' });
  } else {
    formData.repositoryUrl = '';
  }
  cwlRepoErr.value = undefined;
  cwlCheck.value = props.type === 'workflow' ? false : (formData.label !== 'Script');
});

// ---- validation -----------------------------------------------------------
async function validate(): Promise<boolean> {
  const { valid } = await form.value.validate();
  await onNameBlur();

  // Source-specific gate: local mode must have files selected.
  if (formData.sourceType === 'local' && (!formData.files || formData.files.length === 0)) {
    return false;
  }

  if (props.type === 'workflow') {
    return valid && !!cwlCheck.value;
  }

  // tool
  if (formData.label === 'GUI') {
    if (formData.hasBackend) {
      const fOk = checkFolderInRoot(formData.frontendFolder ?? '');
      const bOk = checkFolderInRoot(formData.backendFolder ?? '');
      return valid && !!nameErr.value?.available && fOk && bOk;
    }
    return valid && !!nameErr.value?.available;
  } else {
    // Script
    return valid && !!nameErr.value?.available && cwlCheck.value;
  }
}

async function handleCancel() {
  emit('cancel');
}

async function uploadLocalSource(): Promise<string | null> {
  if (!formData.files || formData.files.length === 0) return null;
  abortController.value = new AbortController();
  const onProgress = (p: UploadProgress) => dropzone.value?.setProgress(p);
  try {
    const uploader = props.type === 'tool' ? useUploadToolSource : useUploadWorkflowSource;
    const res = await uploader(formData.files, {
      onProgress,
      signal: abortController.value.signal,
    });
    dropzone.value?.setProgress({ phase: 'ready' });
    return res.uploadId;
  } catch (err: any) {
    if (axiosWasCanceled(err)) {
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

function axiosWasCanceled(err: any): boolean {
  // axios surfaces aborts as either err.code === 'ERR_CANCELED' or as a CanceledError.
  return err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError' || err?.name === 'AbortError';
}

async function handleSubmit() {
  if (submitting.value) return;
  const ok = await validate();
  if (!ok) {
    showAlert.value = true;
    alertText.value =
      props.type === 'tool'
        ? 'Some required fields are missing. Please provide your source (GitHub URL or local folder), workflow tool name, build command, and, if the tool includes a backend, fill in the frontend and backend folder details.'
        : 'Some required fields are missing. Please provide your source (GitHub URL or local folder), workflow name, and annotating information.';
    return;
  }

  showAlert.value = false;
  submitting.value = true;
  try {
    if (formData.sourceType === 'local') {
      const uploadId = await uploadLocalSource();
      if (!uploadId) {
        // Upload failed or was cancelled — bail without emitting submit.
        return;
      }
      formData.uploadId = uploadId;
    }

    if (props.type === 'workflow') {
      const workflowData: WorkflowInformationStep = {
        repositoryUrl: formData.repositoryUrl,
        name: formData.name,
        author: formData.author,
        version: formData.version,
        description: formData.description,
        sourceType: formData.sourceType,
        uploadId: formData.uploadId,
      };
      emit('submit', workflowData);
    } else {
      // Strip the in-memory `files` blob from the emitted payload — useCreateTool
      // sends JSON, so a File[] in the body would otherwise serialize as an empty
      // array and confuse the backend.
      const { files: _files, ...payload } = formData;
      emit('submit', payload);
    }
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped></style>
