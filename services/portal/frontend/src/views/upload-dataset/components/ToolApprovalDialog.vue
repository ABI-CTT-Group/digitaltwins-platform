<template>
  <v-dialog v-model="open" max-width="560" :persistent="running" transition="dialog-bottom-transition">
    <v-card rounded="lg" flat class="overflow-hidden">
      <v-card-title class="d-flex align-center px-6 pt-6 pb-4 text-h5">
        <v-icon color="#5fd6e8" class="mr-3" size="32">mdi-send-check-outline</v-icon>
        Approve to the platform
      </v-card-title>

      <v-card-text class="px-6 pb-4">
        <template v-if="!status">
          <v-alert type="info" variant="tonal" color="#5fd6e8" density="comfortable" class="mb-6 text-body-2"
                   icon="mdi-information-outline">
            The latest build of <strong>{{ item?.name }}</strong> is registered in SEEK as you, and stored in the
            platform{{ kind === 'workflow' ? ', with a tool dataset for each of its tools' : '' }}. Approving a
            rebuild replaces its previous version.
          </v-alert>
          <v-select
            v-model="seekProjectId"
            :items="projects"
            item-title="title"
            item-value="id"
            label="SEEK project"
            variant="outlined"
            color="#5fd6e8"
            density="comfortable"
            :loading="loadingProjects"
            :error-messages="projectsError"
            prepend-inner-icon="mdi-folder-account-outline"
          />
          <v-checkbox v-model="fhir" color="#5fd6e8" hide-details density="compact"
                              :label="kind === 'workflow' ? 'Publish to FHIR (a PlanDefinition, and an ActivityDefinition per tool)' : 'Publish to FHIR (ActivityDefinition with the port annotations)'" />
        </template>

        <template v-else>
          <div class="d-flex align-center mb-3">
            <v-chip :color="chipColor" variant="tonal" class="mr-3">{{ statusLabel }}</v-chip>
            <span v-if="running" class="text-caption mr-3">You can close this; the {{ kind === 'workflow' ? 'Workflow' : 'Tool' }} Hub keeps it going.</span>
            <span v-if="status.partsTotal" class="text-caption">{{ status.partsSent }} / {{ status.partsTotal }} parts</span>
          </div>
          <v-progress-linear v-if="running" :model-value="percent" :indeterminate="!status.partsTotal"
                             color="#5fd6e8" rounded height="6" class="mb-4" />
          <v-alert v-if="status.handoffError" :type="status.handoffStatus === 'failed' ? 'error' : 'warning'"
                   variant="tonal" density="compact" class="mb-3 text-body-2">
            {{ status.handoffError }}
          </v-alert>
          <div v-if="status.handoffStatus === 'completed'" class="text-body-2">
            <div>Dataset: <code>{{ status.datasetUuid }}</code></div>
            <div>SEEK workflow: <code>{{ status.seekId }}</code></div>
            <div v-if="fhirStatus">FHIR: <code>{{ fhirStatus }}</code></div>
          </div>
        </template>
      </v-card-text>

      <v-divider :thickness="2" />
      <v-card-actions class="px-6 py-4 justify-center">
        <v-btn variant="text" color="#9fb4bf" class="text-none mx-3" :min-width="150" rounded="lg"
               :text="status ? 'Close' : 'Cancel'" @click="close" />
        <v-btn v-if="!status" variant="tonal" color="#5fd6e8" class="text-none mx-3" :min-width="200" rounded="lg"
               text="Approve" :loading="submitting" :disabled="!seekProjectId" @click="approve" />
        <v-btn v-else-if="fhirStatus === 'failed'" variant="tonal" color="#ffb74d" class="text-none mx-3"
               :min-width="200" rounded="lg" text="Retry FHIR push" :loading="retrying" @click="retryFhir" />
      </v-card-actions>
    </v-card>
  </v-dialog>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue';
// @ts-ignore - vue-toastification is installed but missing type declarations
import { useToast } from 'vue-toastification';
import type { SeekProject, ToolApprovalStatus, ToolResponse, WorkflowResponse } from '@/models/types';
import {
  usePlatformDataset, useRetryToolFhir, useSeekProjects, useToolApproval, useToolApprovalStatus,
} from '@/bootstrap/tool_api';
import { useWorkflowApprovalStatus, useWorkflowPlatformApproval } from '@/bootstrap/workflow_api';

const POLL_MS = 3000;

const props = defineProps<{ item: ToolResponse | WorkflowResponse | null; kind?: 'tool' | 'workflow' }>();
const open = defineModel<boolean>({ default: false });
const emit = defineEmits(['done']);
const toast = useToast();
const calls = computed(() => props.kind === 'workflow'
  ? { approve: useWorkflowPlatformApproval, status: useWorkflowApprovalStatus }
  : { approve: useToolApproval, status: useToolApprovalStatus });

const projects = ref<SeekProject[]>([]);
const loadingProjects = ref(false);
const projectsError = ref('');
const seekProjectId = ref<number | undefined>();
const fhir = ref(true);
const submitting = ref(false);
const retrying = ref(false);
const status = ref<ToolApprovalStatus | null>(null);
const fhirStatus = ref<string | undefined>();
let timer: ReturnType<typeof setTimeout> | undefined;

const running = computed(() => !!status.value && !['completed', 'failed'].includes(status.value.handoffStatus ?? ''));
const percent = computed(() =>
  status.value?.partsTotal ? (100 * (status.value.partsSent ?? 0)) / status.value.partsTotal : 0);
const statusLabel = computed(() => ({
  uploading: 'Uploading', awaiting_reauth: 'Waiting for sign-in', committing: 'Registering in SEEK and storing',
  completed: 'Approved', failed: 'Failed',
} as Record<string, string>)[status.value?.handoffStatus ?? ''] ?? 'Starting');
const chipColor = computed(() => (
  status.value?.handoffStatus === 'completed' ? '#6fd49a' : status.value?.handoffStatus === 'failed' ? '#ff6b6b' : '#5fd6e8'));

watch(open, async (isOpen) => {
  stop();
  if (!isOpen) return;
  status.value = null;
  fhirStatus.value = undefined;
  seekProjectId.value = props.item?.seekProjectId;
  if (props.item && ['uploading', 'awaiting_reauth', 'committing'].includes(props.item.handoffStatus ?? '')) {
    poll(); // an approval already under way: show (and resume) it
    return;
  }
  loadingProjects.value = true;
  projectsError.value = '';
  try {
    projects.value = await useSeekProjects();
  } catch (err: any) {
    projectsError.value = `Could not load SEEK projects: ${err?.message ?? 'unknown error'}`;
  } finally {
    loadingProjects.value = false;
  }
});

async function approve() {
  if (!props.item || !seekProjectId.value) return;
  submitting.value = true;
  try {
    status.value = await calls.value.approve(props.item.id, { seekProjectId: seekProjectId.value, fhir: fhir.value });
    schedule();
  } catch (err: any) {
    toast.error(`Approval failed: ${err?.response?.data?.detail ?? err?.message ?? 'unknown error'}`);
  } finally {
    submitting.value = false;
  }
}

async function poll() {
  if (!props.item) return;
  try {
    status.value = await calls.value.status(props.item.id);
  } catch (err) {
    console.warn('Approval status poll failed:', err);
  }
  if (running.value) return schedule();
  if (status.value?.handoffStatus === 'completed' && status.value.datasetUuid) await loadFhirStatus();
  emit('done', status.value);
}

async function loadFhirStatus() {
  try {
    const dataset = await usePlatformDataset(status.value!.datasetUuid!);
    fhirStatus.value = dataset.fhirStatus;
    if (['pending', 'pushing'].includes(dataset.fhirStatus ?? '')) timer = setTimeout(loadFhirStatus, POLL_MS);
  } catch (err) {
    console.warn('Could not read the platform dataset:', err);
  }
}

async function retryFhir() {
  retrying.value = true;
  try {
    await useRetryToolFhir(status.value!.datasetUuid!);
    fhirStatus.value = 'pending';
    timer = setTimeout(loadFhirStatus, POLL_MS);
  } catch (err: any) {
    toast.error(`FHIR retry failed: ${err?.response?.data?.detail ?? err?.message ?? 'unknown error'}`);
  } finally {
    retrying.value = false;
  }
}

function schedule() {
  timer = setTimeout(poll, POLL_MS);
}

function stop() {
  if (timer) clearTimeout(timer);
  timer = undefined;
}

function close() {
  open.value = false;
}

onBeforeUnmount(stop);
</script>
