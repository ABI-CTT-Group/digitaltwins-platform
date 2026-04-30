<template>
  <RegistryView
    register-label="Register a new workflow tool"
    search-label="Search workflow tools"
    :fetch-list="useWorkflowTools"
    :disabled="dockerComposeBusy"
    :is-pending="(items) => items.some(t => t.status === 'building' || t.deploy_status === 'deploying')"
    @register="handleRegister"
  >
    <template #default="{ items }">
      <ToolCard
        v-for="tool in items"
        :key="tool.id"
        :tool="tool"
        :disabled="dockerComposeBusy"
        @launch="(id) => handleLaunch(id)"
        @rebuild="(id) => handleRebuild(id)"
        @deploy="(id) => handleDeploy(id)"
        @compose-up="(id) => handleExecuteDockerCompose(id, 'up')"
        @compose-down="(id) => handleExecuteDockerCompose(id, 'down')"
        @delete="(id) => handleDeleteTool(id)"
        @submit-approve="(id) => handleToolApproval(id)"
      />
    </template>
  </RegistryView>
</template>

<script setup lang="ts">
// @ts-ignore - vue-toastification is installed but missing type declarations
import { useToast } from 'vue-toastification';
import RegistryView from '../components/RegistryView.vue';
import ToolCard from '../components/ToolCard.vue';
import {
  useWorkflowTools,
  useToolMetadata,
  useWorkflowToolBuild,
  useDeleteTool,
  useToolApproval,
  useDeployTool,
  useDockerCompose,
} from '@/bootstrap/tool_api';
import type { ToolMinIOToolMetadata } from '@/models/types';
import { useRemoteAppStore } from '@/store/remote_store';
import { useRouter } from 'vue-router';
import { ref } from 'vue';

const router = useRouter();
const remoteAppStore = useRemoteAppStore();
const toast = useToast();
const dockerComposeBusy = ref(false);

const emit = defineEmits(['register']);

const handleRegister = () => emit('register');

const handleLaunch = async (id: string) => {
  const metadata = await useToolMetadata();
  if (metadata?.components?.length > 0) {
    const toolMetadata = metadata.components.find((t: ToolMinIOToolMetadata) => t.id === id);
    if (toolMetadata) {
      remoteAppStore.setRemoteApp({
        path: toolMetadata.path,
        expose: toolMetadata.expose,
        name: toolMetadata.name,
        description: toolMetadata.description,
      });
      router.push({ name: 'ToolPluginView' });
      return;
    }
  }
  console.warn(`Launch tool ${id} failed, cannot find the metadata in MinIO.`);
};

const handleRebuild = async (id: string) => {
  await useWorkflowToolBuild(id);
};

const handleDeploy = async (id: string) => {
  await useDeployTool(id);
};

const handleDeleteTool = async (res: any) => {
  // RegistryView auto-refreshes; nothing extra needed
};

const handleExecuteDockerCompose = async (id: string, command: 'up' | 'down') => {
  dockerComposeBusy.value = true;
  try {
    const res = await useDockerCompose(id, command) as any;
    if (res?.success) {
      toast.success(`Docker compose ${command} succeeded.`);
    } else {
      toast.error(res?.message || `Docker compose ${command} failed.`);
    }
  } catch (error) {
    console.error(`Error executing Docker Compose ${command}:`, error);
    toast.error(`An error occurred while executing Docker Compose ${command}.`);
  } finally {
    dockerComposeBusy.value = false;
  }
};

const handleToolApproval = async (id: string) => {
  try {
    const res = await useToolApproval(id);
    if (res) {
      toast.success('Tool submitted for approval successfully.');
    } else {
      toast.error('Failed to submit tool for approval.');
    }
  } catch (error) {
    console.error('Error submitting tool for approval:', error);
    toast.error('An error occurred while submitting the tool for approval.');
  }
};
</script>