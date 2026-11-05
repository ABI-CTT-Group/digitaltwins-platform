<template>
  <RegistryView
    ref="registryRef"
    register-label="Register a workflow"
    search-label="Search workflows"
    accent="var(--accent-workflows)"
    :fetch-list="useWorkflowHub"
    :is-pending="(items) => items.some(w => w.status === 'building')"
    :filter-fn="hub.filterFn.value"
    :sort-fn="hub.sortFn"
    @refresh="hub.onRefresh"
    @register="handleRegister"
  >
    <template #filters>
      <HubFilterChips v-model="hub.filter.value" :counts="hub.counts.value" />
    </template>

    <template #default="{ items }">
      <WorkflowCard
        v-for="w in items"
        :key="w.id"
        :workflow="w"
        :can-deploy="authStore.hasAdminRole"
        @delete="confirmDeleteWorkflow"
        @delete-platform="openPlatformDelete"
        @approve-platform="openApproval"
        @retry-fhir="handleRetryFhir"
        @approval-done="onApprovalDone"
        @deploy-dag="handleDeployDag"
      />
    </template>

    <template #empty>
      <p class="hub-empty">No workflows yet. Register an SDS workflow package to chain tools into an assay.</p>
    </template>
  </RegistryView>

  <ConfirmDialog v-if="confirm.request.value" v-model="confirm.open.value" v-bind="confirm.request.value" />

  <ToolApprovalDialog v-model="approvalOpen" kind="workflow" :item="approvalWorkflow" @done="onApprovalDone" />

  <DeletePlatformDatasetDialog v-model="platformDeleteOpen" kind="workflow" :item="platformDeleteItem"
                               @deleted="registryRef?.handleRefresh()" />
</template>

<script setup lang="ts">
// @ts-ignore - vue-toastification is installed but missing type declarations
import { useToast } from 'vue-toastification';
import { ref } from 'vue';
import RegistryView from '../components/RegistryView.vue';
import WorkflowCard from '../components/WorkflowCard.vue';
import DeletePlatformDatasetDialog from '../components/DeletePlatformDatasetDialog.vue';
import ConfirmDialog from '../components/ConfirmDialog.vue';
import HubFilterChips from '../components/HubFilterChips.vue';
import { useConfirm } from '../components/useConfirm';
import { isInPlatform, workflowStatus } from '../components/cardStatus';
import { useHubFilter } from '../components/hubFilter';
import ToolApprovalDialog from '../components/ToolApprovalDialog.vue';
import { useWorkflowHub, useDeleteWorkflow } from '@/bootstrap/workflow_api';
import { useRetryToolFhir } from '@/bootstrap/tool_api';
import { deployWorkflowDag } from '@/bootstrap/platform_api';
import { useAuthStore } from '@/store/auth_store';
import type { ToolApprovalStatus, WorkflowResponse } from '@/models/types';

const toast = useToast();
const authStore = useAuthStore();
const registryRef = ref<{ handleRefresh: () => Promise<void> }>();
const emit = defineEmits(['register']);

// All · Needs you · In progress · In the platform, from each card's status line; what needs you first.
const hub = useHubFilter((w: WorkflowResponse) => workflowStatus(w, { canDeploy: authStore.hasAdminRole }));

const handleRegister = () => emit('register');

const confirm = useConfirm();
const confirmDeleteWorkflow = (w: WorkflowResponse) => confirm.ask({
  title: `Delete ${w.name}?`,
  text: isInPlatform(w, 'sparc-workflow-')
    ? 'The workflow is removed from the portal and from the platform, with the tool datasets its steps run. This can\'t be undone.'
    : 'The workflow is removed from the portal, with its builds. This can\'t be undone.',
  confirmLabel: 'Delete workflow',
  action: async () => {
    const res: any = await useDeleteWorkflow(w.id);
    if (res && res.status === false) throw new Error(res.message);
    toast.success('Workflow deleted.');
    await registryRef.value?.handleRefresh();
  },
});

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

// An admin deploys a script workflow's DAG into Airflow; the platform API answers once
// Airflow has loaded it or said why not.
const handleDeployDag = async (w: WorkflowResponse) => {
  w.dagStatus = 'deploying';
  try {
    const res = await deployWorkflowDag(w.uuid ?? w.id);
    if (res.dagStatus === 'deployed') toast.success(`DAG ${res.dagId} deployed to Airflow.`);
    else toast.error(`DAG deploy failed: ${res.dagError ?? 'unknown error'}`);
  } catch (err: any) {
    toast.error(`DAG deploy failed: ${err?.response?.data?.detail ?? err?.message ?? err}`);
  }
  await registryRef.value?.handleRefresh();
};

const handleRetryFhir = async (w: WorkflowResponse) => {
  try {
    await useRetryToolFhir(w.uuid ?? w.id);
    toast.success('Publishing the workflow to FHIR again.');
  } catch (err: any) {
    toast.error(`Retry FHIR failed: ${err?.response?.data?.detail ?? err?.message ?? 'unknown error'}`);
  }
  await registryRef.value?.handleRefresh();
};
</script>