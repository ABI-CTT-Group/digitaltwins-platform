<template>
  <RegistryView
    ref="registryRef"
    register-label="Register a new workflow"
    search-label="Search workflows"
    accent="#7fb2f0"
    :fetch-list="useWorkflowHub"
    :is-pending="(items) => items.some(w => w.status === 'building')"
    :filter-fn="registrationFilterFn"
    @register="handleRegister"
  >
    <template #filters>
      <v-select
        v-model="registrationFilter"
        :items="registrationFilterOptions"
        item-title="title"
        item-value="value"
        label="Registration status"
        variant="outlined"
        base-color="#7fb2f0"
        color="#7fb2f0"
        density="compact"
        hide-details
        style="max-width: 240px;"
      />
    </template>

    <template #default="{ items }">
      <WorkflowCard
        v-for="w in items"
        :key="w.id"
        :workflow="w"
        @delete="handleDeleteWorkflow"
        @delete-platform="openPlatformDelete"
        @submit-approve="(id) => handleWorkflowApproval(id)"
        @approve-platform="openApproval"
        @approval-done="onApprovalDone"
      />
    </template>
  </RegistryView>

  <ToolApprovalDialog v-model="approvalOpen" kind="workflow" :item="approvalWorkflow" @done="onApprovalDone" />

  <DeletePlatformDatasetDialog v-model="platformDeleteOpen" kind="workflow" :item="platformDeleteItem"
                               @deleted="registryRef?.handleRefresh()" />
</template>

<script setup lang="ts">
// @ts-ignore - vue-toastification is installed but missing type declarations
import { useToast } from 'vue-toastification';
import { computed, ref } from 'vue';
import RegistryView from '../components/RegistryView.vue';
import WorkflowCard from '../components/WorkflowCard.vue';
import DeletePlatformDatasetDialog from '../components/DeletePlatformDatasetDialog.vue';
import ToolApprovalDialog from '../components/ToolApprovalDialog.vue';
import { useWorkflowHub, useWorkflowApproval } from '@/bootstrap/workflow_api';
import type { ToolApprovalStatus, WorkflowResponse } from '@/models/types';

const toast = useToast();
const registryRef = ref<{ handleRefresh: () => Promise<void> }>();
const emit = defineEmits(['register']);

// Same "in platform" convention as Tools: uploaded straight to the platform, or a
// real platform uuid vs. the `sparc-workflow-` placeholder a row gets before it's
// actually registered.
const isWorkflowInPlatform = (w: WorkflowResponse) =>
  !!w.platformOnly || (!!w.uuid && !w.uuid.startsWith('sparc-workflow-'));

const registrationFilterOptions = [
  { title: 'All', value: 'all' },
  { title: 'In platform', value: 'in-platform' },
  { title: 'Not in platform', value: 'not-in-platform' },
];
const registrationFilter = ref<'all' | 'in-platform' | 'not-in-platform'>('all');
const registrationFilterFn = computed(() => {
  if (registrationFilter.value === 'all') return undefined;
  const wantInPlatform = registrationFilter.value === 'in-platform';
  return (w: WorkflowResponse) => isWorkflowInPlatform(w) === wantInPlatform;
});

const handleRegister = () => emit('register');

const handleDeleteWorkflow = async () => {
  await registryRef.value?.handleRefresh();
};

// A workflow uploaded via the REST API is deleted from the platform after a
// confirmation that also asks whether its tool datasets go too.
const platformDeleteOpen = ref(false);
const platformDeleteItem = ref<{ uuid: string; name: string } | null>(null);
const openPlatformDelete = (w: WorkflowResponse) => {
  platformDeleteItem.value = { uuid: w.uuid ?? w.id, name: w.name };
  platformDeleteOpen.value = true;
};

// An SDS workflow is handed to the platform: the dialog picks the SEEK project and follows the handoff.
const approvalOpen = ref(false);
const approvalWorkflow = ref<WorkflowResponse | null>(null);
const openApproval = (w: WorkflowResponse) => {
  approvalWorkflow.value = w;
  approvalOpen.value = true;
};
const onApprovalDone = async (status: ToolApprovalStatus | null) => {
  if (status?.handoffStatus === 'completed') toast.success('Workflow approved into the platform.');
  else if (status?.handoffStatus === 'failed') toast.error(`Approval failed: ${status.handoffError ?? 'unknown error'}`);
  await registryRef.value?.handleRefresh();
};

const handleWorkflowApproval = async (id: string) => {
  try {
    const res = await useWorkflowApproval(id);
    if (res) {
      toast.success('Workflow submitted for approval successfully.');
    } else {
      toast.error('Failed to submit workflow for approval.');
    }
  } catch (error) {
    console.error('Error submitting workflow for approval:', error);
    toast.error('An error occurred while submitting the workflow for approval.');
  }
};
</script>