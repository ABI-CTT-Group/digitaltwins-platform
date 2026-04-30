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
        @onSoundUrlBlur="onRepoBlur"
        @onNameBlur="onNameBlur"
      >
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
        @click="handleCancel"
      />
      <v-btn
        color="success"
        :text="type === 'tool' ? 'Submit Tool' : 'Submit Workflow'"
        variant="tonal"
        :width="150"
        rounded="md"
        class="hover-animate ma-5"
        @click="handleSubmit"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue';
import CommonInfoForm from './CommonInfoForm.vue';
import type { ToolInformationStep, WorkflowInformationStep, CheckNameResponse } from '@/models/types';
import { useCheckName } from '@/bootstrap/api_helpers';
import { useGithubRepoInfo } from '@/composables/useGithubRepoInfo';

// ---- props / emits --------------------------------------------------------
const props = defineProps<{ type: 'workflow' | 'tool' }>();
const emit = defineEmits(['cancel', 'submit']);

// ---- state ----------------------------------------------------------------
const form = ref();
const policyCheckbox = ref(false);
const showAlert = ref(false);
const alertText = ref('');
const cwlCheck = ref(props.type === 'workflow' ? false : true); // workflow needs CWL; tool (GUI) doesn't by default

const nameErr = ref<CheckNameResponse>();
const cwlRepoErr = ref<CheckNameResponse>();

// Tool form data (superset of workflow fields)
const formData = reactive<ToolInformationStep>({
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
});

// ---- GitHub repo info composable ------------------------------------------
const { info: repoInfo, refresh: refreshRepoInfo } = useGithubRepoInfo();
const foldersInRoot = ref<string[]>([]);

// Sync foldersInRoot from composable
watch(() => repoInfo.value.foldersInRoot, (v) => { foldersInRoot.value = v; });

// ---- validation rules (tool-only) -----------------------------------------
const frontendCommandRegex = /^(npm|yarn)\s+\S+/;
const frontendFolderRules = [
  (v: string) => (formData.hasBackend ? !!v || "Make sure the folder name matches the frontend folder in your tool's GitHub repo" : true),
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
    onRepoBlur();
  } else {
    cwlCheck.value = false;
    cwlRepoErr.value = undefined;
  }
  showAlert.value = false;
};

const onRepoBlur = async () => {
  if (!formData.repositoryUrl) return;
  const isCwlCheck = props.type === 'workflow' || formData.label === 'Script';
  const normalizedUrl = await refreshRepoInfo(formData.repositoryUrl, isCwlCheck);
  formData.repositoryUrl = normalizedUrl;
  formData.name = repoInfo.value.name;
  formData.author = repoInfo.value.author;
  if (repoInfo.value.version) formData.version = repoInfo.value.version;

  if (isCwlCheck) {
    cwlCheck.value = repoInfo.value.cwlExists;
    cwlRepoErr.value = repoInfo.value.cwlRepoErr;
  }

  await onNameBlur();
};

const onNameBlur = async () => {
  const scope = props.type === 'tool' ? 'tool' : 'workflow';
  nameErr.value = await useCheckName(scope, formData.name);
};

const checkFolderInRoot = (name: string) => foldersInRoot.value.includes(name);

watch(() => formData.hasBackend, () => { policyCheckbox.value = false; });

// ---- validation -----------------------------------------------------------
async function validate(): Promise<boolean> {
  const { valid } = await form.value.validate();
  await onNameBlur();

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

async function handleSubmit() {
  const ok = await validate();
  if (ok) {
    showAlert.value = false;
    if (props.type === 'workflow') {
      // emit only the workflow subset of fields
      const workflowData: WorkflowInformationStep = {
        repositoryUrl: formData.repositoryUrl,
        name: formData.name,
        author: formData.author,
        version: formData.version,
        description: formData.description,
      };
      emit('submit', workflowData);
    } else {
      emit('submit', formData);
    }
  } else {
    showAlert.value = true;
    alertText.value =
      props.type === 'tool'
        ? 'Some required fields are missing. Please provide your GitHub repository, workflow tool name, build command, and, if the tool includes a backend, fill in the frontend and backend folder details.'
        : 'Some required fields are missing. Please provide your GitHub repository, workflow name, and annotating information.';
  }
}
</script>

<style scoped></style>
