<template>
  <RegistryView
    ref="registryRef"
    register-label="Register a new workflow"
    search-label="Search workflows"
    accent="#7fb2f0"
    :fetch-list="useWorkflow"
    :is-pending="(items) => items.some(w => w.status === 'building')"
    @register="handleRegister"
  >
    <template #default="{ items }">
      <WorkflowCard
        v-for="w in items"
        :key="w.id"
        :workflow="w"
        @delete="handleDeleteWorkflow"
        @submit-approve="(id) => handleWorkflowApproval(id)"
      />
    </template>
  </RegistryView>
</template>

<script setup lang="ts">
// @ts-ignore - vue-toastification is installed but missing type declarations
import { useToast } from 'vue-toastification';
import { ref } from 'vue';
import RegistryView from '../components/RegistryView.vue';
import WorkflowCard from '../components/WorkflowCard.vue';
import { useWorkflow, useDeleteWorkflow, useWorkflowApproval } from '@/bootstrap/workflow_api';

const toast = useToast();
const registryRef = ref<{ handleRefresh: () => Promise<void> }>();
const emit = defineEmits(['register']);

const handleRegister = () => emit('register');

const handleDeleteWorkflow = async (id: string) => {
  await useDeleteWorkflow(id);
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