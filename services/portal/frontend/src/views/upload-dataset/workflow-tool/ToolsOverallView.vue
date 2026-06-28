<template>
  <RegistryView
    ref="registryRef"
    register-label="Register a new workflow tool"
    search-label="Search workflow tools"
    accent="#5fd6e8"
    :fetch-list="useWorkflowTools"
    :disabled="dockerComposeBusy"
    :is-pending="(items) => items.some(t => t.status === 'building' || t.deployStatus === 'deploying')"
    @register="handleRegister"
  >
    <template #default="{ items }">
      <!-- Inline cast: RegistryView types displayItems as `{ value: T[] }` (a
           ref-shaped object) but Vue auto-unwraps the ref at the slot binding,
           so at runtime items IS the array. Without the cast TypeScript would
           iterate over the object's `value` property and type `tool` as the
           whole array. -->
      <ToolCard
        v-for="tool in (items as unknown as ToolResponse[])"
        :key="tool.id"
        :tool="tool"
        :disabled="dockerComposeBusy"
        @launch="(id) => handleLaunch(id)"
        @rebuild="(id) => handleRebuild(id)"
        @deploy="(id) => handleDeploy(id)"
        @compose-up="(id) => handleExecuteDockerCompose(id, 'up')"
        @compose-down="(id) => handleExecuteDockerCompose(id, 'down')"
        @delete="handleDeleteTool"
        @submit-approve="(id) => handleToolApproval(id)"
        @view-logs="handleViewLogs"
      />
    </template>
  </RegistryView>

  <RebuildAuthDialog
    v-model="rebuildDialogOpen"
    :source-type="rebuildSourceType"
    :busy="rebuildBusy"
    @submit="onRebuildAuthSubmit"
    @cancel="onRebuildCancel"
  />
</template>

<script setup lang="ts">
// @ts-ignore - vue-toastification is installed but missing type declarations
import { useToast } from 'vue-toastification';
import RegistryView from '../components/RegistryView.vue';
import ToolCard from '../components/ToolCard.vue';
import RebuildAuthDialog from '../components/RebuildAuthDialog.vue';
import {
  useWorkflowTools,
  useToolMetadata,
  useWorkflowToolBuild,
  useToolApproval,
  useDeployTool,
  useDockerCompose,
} from '@/bootstrap/tool_api';
import type { ToolMinIOToolMetadata, ToolResponse, SourceType, TransientAuth } from '@/models/types';
import { useRemoteAppStore } from '@/store/remote_store';
import { useRouter } from 'vue-router';
import { ref } from 'vue';
import { useLogConsole } from '@/composables/useLogConsole';

// Shared, app-level log console (mounted once in workflow-tool/index.vue).
const { openConsole } = useLogConsole();

function openLogConsole(kind: 'build' | 'deploy', jobId: string, title: string, initialStatus: string) {
  openConsole(kind, jobId, title, initialStatus);
}

interface ViewLogsPayload {
  kind: 'build' | 'deploy';
  jobId: string;
  title: string;
  startedAt: string;
  endedAt?: string;
  initialStatus: string;
}

function handleViewLogs(payload: ViewLogsPayload) {
  openConsole(payload.kind, payload.jobId, payload.title, payload.initialStatus, payload.startedAt, payload.endedAt);
}

const router = useRouter();
const remoteAppStore = useRemoteAppStore();
const toast = useToast();
const dockerComposeBusy = ref(false);
const registryRef = ref<{ handleRefresh: () => Promise<void> }>();

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

// --- Rebuild flow with optional token modal ---
// Local source: no auth concept — fire build directly with empty body.
// Any git source: open the auth dialog. The user can leave the token blank
// for public repos (POST body stays `{}`), or fill it for private repos.
// Per phase-0.2 decision the token is never persisted; rebuild prompts
// every time.
const rebuildDialogOpen = ref(false);
const rebuildBusy = ref(false);
const rebuildSourceType = ref<SourceType | null>(null);
const rebuildTargetId = ref<string | null>(null);

const handleRebuild = async (id: string) => {
  // Find the tool record so we can read source_type — decides whether to
  // open the auth dialog (git providers) or fire the build directly (local).
  let items: ToolResponse[];
  try {
    items = (await useWorkflowTools()) as ToolResponse[];
  } catch (err: any) {
    console.error('Failed to fetch tools list before rebuild:', err);
    toast.error(`Could not fetch tool list: ${err?.message || 'unknown error'}`);
    return;
  }
  const tool = items.find((t) => t.id === id);
  const st: SourceType = (tool?.sourceType ?? 'github') as SourceType;

  if (st === 'local') {
    // Local source: no token concept, fire directly.
    try {
      const res = await useWorkflowToolBuild(id);
      toast.success('Rebuild started. Watch the registry for status updates.');
      openLogConsole('build', res.buildId, tool?.name ?? id, 'building');
      await registryRef.value?.handleRefresh();
    } catch (err: any) {
      console.error('Local rebuild failed:', err);
      const status = err?.response?.status;
      const detail = err?.response?.data?.detail || err?.response?.data?.message;
      let msg = 'Failed to start rebuild';
      if (status === 405 || status === 404) {
        msg = `Backend ${status} on POST /plugin/{id}/build — backend container may need restart to pick up the new endpoint.`;
      } else if (detail) {
        msg = `Rebuild failed (HTTP ${status}): ${detail}`;
      } else if (err?.message) {
        msg = `Rebuild failed: ${err.message}`;
      }
      toast.error(msg);
    }
    return;
  }

  // Git source (github / gitlab / bitbucket / git_generic): open the auth
  // dialog. User decides whether to provide a token (private) or build
  // anonymously (public github).
  rebuildSourceType.value = st;
  rebuildTargetId.value = id;
  rebuildDialogOpen.value = true;
};

const onRebuildAuthSubmit = async (auth: TransientAuth) => {
  const id = rebuildTargetId.value;
  if (!id) return;
  rebuildBusy.value = true;
  try {
    const res = await useWorkflowToolBuild(id, auth);
    rebuildDialogOpen.value = false;
    // Capture tool name before clearing rebuildTargetId
    let toolName = id;
    try {
      const items = (await useWorkflowTools()) as ToolResponse[];
      toolName = items.find((t) => t.id === id)?.name ?? id;
    } catch { /* fallback to id */ }
    rebuildTargetId.value = null;
    rebuildSourceType.value = null;
    toast.success('Rebuild started. Watch the registry for status updates.');
    openLogConsole('build', res.buildId, toolName, 'building');
    await registryRef.value?.handleRefresh();
  } catch (err: any) {
    // Show backend's actual error if available so the user knows whether
    // it's a missing token, wrong endpoint (backend not restarted after
    // upgrade), network, etc. — not just "see console".
    console.error('Rebuild failed:', err);
    const status = err?.response?.status;
    const detail = err?.response?.data?.detail || err?.response?.data?.message;
    let msg = 'Failed to start rebuild';
    if (status === 405 || status === 404) {
      msg = `Backend ${status} on POST /plugin/{id}/build — backend container may need restart to pick up the new endpoint.`;
    } else if (detail) {
      msg = `Rebuild failed (HTTP ${status}): ${detail}`;
    } else if (err?.message) {
      msg = `Rebuild failed: ${err.message}`;
    }
    toast.error(msg);
  } finally {
    rebuildBusy.value = false;
  }
};

const onRebuildCancel = () => {
  rebuildTargetId.value = null;
  rebuildSourceType.value = null;
};

const handleDeploy = async (id: string) => {
  const res = await useDeployTool(id) as any;
  const deployId: string = res?.deployId ?? res?.deploy_id ?? '';
  // Resolve tool name for the console title
  let toolName = id;
  try {
    const items = (await useWorkflowTools()) as ToolResponse[];
    toolName = items.find((t) => t.id === id)?.name ?? id;
  } catch { /* fallback to id */ }
  if (deployId) {
    openLogConsole('deploy', deployId, toolName, 'deploying');
  }
  await registryRef.value?.handleRefresh();
};

const handleDeleteTool = async () => {
  await registryRef.value?.handleRefresh();
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