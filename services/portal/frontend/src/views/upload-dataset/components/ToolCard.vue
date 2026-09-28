<template>
  <CardUI
    :title="tool.name"
    :kind="kind"
    :accent="accent"
    :is-deleting="isDeleting"
    :is-disabled="!!disabled"
    :menu-items="menuItems"
  >
    <template #description>{{ tool.description || 'No description provided.' }}</template>

    <template #meta>
      <span v-if="tool.version" class="aurora-chip">v{{ tool.version }}</span>
      <span v-if="tool.author" class="aurora-chip">{{ tool.author }}</span>
      <span v-if="tool.status" class="aurora-chip" :style="{ '--chip': auroraStatus(tool.status) }">
        {{ tool.status }}
      </span>
      <span v-if="tool.deployStatus" class="aurora-chip" :style="{ '--chip': auroraStatus(tool.deployStatus) }">
        deploy · {{ tool.deployStatus }}
      </span>
      <span v-if="tool.createdAt" class="aurora-chip">{{ formatDate(tool.createdAt) }}</span>
    </template>

    <template #action>
      <button v-if="isBuilding" type="button" class="aurora-btn aurora-btn--ghost aurora-btn--sm" disabled>
        <v-progress-circular indeterminate size="13" width="2" :color="accent" /> Building
      </button>
      <button v-else-if="isDeploying" type="button" class="aurora-btn aurora-btn--ghost aurora-btn--sm" disabled>
        <v-progress-circular indeterminate size="13" width="2" :color="accent" /> Deploying
      </button>
      <button
        v-else
        type="button"
        class="aurora-btn aurora-btn--sm"
        :disabled="disabled || tool.status != 'completed'"
        @click.stop="onLaunch"
      >
        <v-icon icon="mdi-rocket-launch-outline" size="15" /> Launch
      </button>
    </template>
  </CardUI>
</template>

<script setup lang="ts">
import { computed, ref, toRef } from 'vue'
import { ToolResponse } from '@/models/types';
import { useGetDockerComposeStatus, useDeleteTool } from '@/bootstrap/tool_api'
import CardUI, { type UCardMenuItem } from './CardUI.vue';
import { formatDate } from './utils';
// @ts-ignore - vue-toastification is installed but missing type declarations
import { useToast } from 'vue-toastification';

const toast = useToast();

const props = defineProps<{
  tool: ToolResponse
  disabled?: boolean
}>()

const tool = toRef(props, "tool")
const isDeleting = ref(false)

// Per-type identity colour — GUI tools aqua, CWL scripts violet — so the rail,
// eyebrow and Launch button all carry the tool's kind at a glance.
const accent = computed(() => (tool.value.label === 'Script' ? '#c792ea' : '#5fd6e8'))
const kind = computed(() => (tool.value.label === 'Script' ? 'CWL Script' : 'Web GUI Tool'))

const isBuilding = computed(() => tool.value.status == "building")
const isDeploying = computed(() => {
    if(!tool.value.hasBackend ) return false;
    if(!tool.value.deployStatus) return false;
    return tool.value.deployStatus == "deploying";
})

// Aurora status palette — soft tonal chips keyed by lifecycle state.
const auroraStatus = (s?: string) => {
  switch (s) {
    case "pending": return "#ffb74d"
    case "building":
    case "deploying": return "#5fd6e8"
    case "failed": return "#ff6b6b"
    case "completed": return "#6fd49a"
    default: return "#9fb4bf"
  }
}

const emit = defineEmits(["launch", "rebuild", "submit-approve", "deploy", "compose-up", "compose-down", "delete", "view-logs"])

const hasViewLogs = computed(() =>
  !!(tool.value.latestDeployId || tool.value.latestBuildId)
)

const menuItems = computed<UCardMenuItem[]>(() => {
  const isGui = tool.value.label === 'GUI'
  const items: UCardMenuItem[] = [
    { label: 'Rebuild tool', icon: 'mdi-refresh', onClick: onRebuild },
    { label: 'Submit to approval', icon: 'mdi-send-check-outline', onClick: onSubmit },
  ]
  if (tool.value.hasBackend && isGui) {
    items.push({ label: 'Deploy backend', icon: 'mdi-server-network', onClick: onDeploy })
  }
  if (tool.value.deployStatus === 'completed' && isGui) {
    items.push({ label: 'Compose up', icon: 'mdi-play-circle-outline', onClick: onDockerComposeUp })
    items.push({ label: 'Compose down', icon: 'mdi-stop-circle-outline', onClick: onDockerComposeDown })
  }
  if (hasViewLogs.value) {
    items.push({ label: 'View logs', icon: 'mdi-console-line', onClick: onViewLogs })
  }
  items.push({ label: 'Delete tool', icon: 'mdi-trash-can-outline', danger: true, onClick: onDelete })
  return items
})

const isTerminal = (s?: string) => s === 'completed' || s === 'failed'

const onViewLogs = () => {
  const t = tool.value
  // Prefer the latest deploy if it exists, otherwise fall back to latest build.
  // startedAt = the job's real start (createdAt); endedAt = its finish time, set
  // ONLY for terminal jobs so the console freezes on the actual DURATION rather
  // than ticking "time since it finished".
  if (t.latestDeployId) {
    const st = t.deployStatus ?? 'completed'
    emit('view-logs', {
      kind: 'deploy',
      jobId: t.latestDeployId,
      title: t.name,
      startedAt: t.latestDeployCreatedAt ?? t.updatedAt ?? new Date().toISOString(),
      endedAt: isTerminal(st) ? t.latestDeployUpdatedAt : undefined,
      initialStatus: st,
    })
  } else if (t.latestBuildId) {
    const st = t.status ?? 'completed'
    emit('view-logs', {
      kind: 'build',
      jobId: t.latestBuildId,
      title: t.name,
      startedAt: t.latestBuildCreatedAt ?? t.updatedAt ?? new Date().toISOString(),
      endedAt: isTerminal(st) ? t.latestBuildUpdatedAt : undefined,
      initialStatus: st,
    })
  }
}

const onLaunch = async () => {
    if(tool.value.label === "Script"){
        toast.warning("CWL Script tool cannot be launched. Please download the script and run it locally.");
        return;
    }
    if (tool.value.hasBackend && !tool.value.latestDeployId && tool.value.deployStatus !== 'completed') {
        toast.warning("Tool backend is not deployed yet. Please deploy the backend first.");
        return;
    }else if(!!tool.value.latestDeployId && !await useGetDockerComposeStatus(tool.value.latestDeployId).catch(() => false)){
        toast.warning("Tool backend is not running. Please start the backend by 'Compose Up' first.");
        return;
    }
    emit("launch", tool.value.id)
}
const onRebuild = () => {
    // No optimistic prop mutation here. The parent flow may open a dialog
    // (and the user might Cancel) or the build POST itself may fail, in
    // which case `tool.status` should NOT have flipped to "building".
    // Parent calls registryRef.handleRefresh() once the build is actually
    // started — that pulls the real PENDING/BUILDING status from backend.
    emit("rebuild", tool.value.id)
}
const onSubmit = () => emit("submit-approve", tool.value.id)
const onDeploy = () => {
    tool.value.deployStatus = "deploying"
    emit("deploy", tool.value.id)
}
const onDockerComposeUp = () => emit("compose-up", tool.value.latestDeployId)
const onDockerComposeDown = () => emit("compose-down", tool.value.latestDeployId)
const onDelete = async () => {
    isDeleting.value = true;
    const res:any = await useDeleteTool(tool.value.id)

    if(!res["status"]){
      isDeleting.value = false;
      toast.error("Error: " + res["message"])
    }
    emit("delete", res)
}
</script>
