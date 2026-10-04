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
      <span v-if="handoffActive" class="aurora-chip" :style="{ '--chip': '#5fd6e8' }">approving…</span>
      <span v-else-if="tool.handoffStatus === 'failed'" class="aurora-chip" :style="{ '--chip': '#ff6b6b' }">
        approval failed
      </span>
      <span v-if="tool.kind === 'workflow'" class="aurora-chip" :style="{ '--chip': '#7fb2f0' }">
        from workflow {{ tool.workflowName }}
      </span>
      <span v-else-if="tool.platformOnly" class="aurora-chip" :style="{ '--chip': '#9fb4bf' }">platform upload</span>
      <span v-else-if="inPlatform" class="aurora-chip" :style="{ '--chip': '#6fd49a' }">in platform</span>
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
        :disabled="disabled || tool.status != 'completed' || tool.platformOnly"
        @click.stop="onLaunch"
      >
        <v-icon icon="mdi-rocket-launch-outline" size="15" /> Launch
      </button>
    </template>
  </CardUI>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, toRef, watch } from 'vue'
import { ToolResponse } from '@/models/types';
import { useGetDockerComposeStatus, useDeleteTool, useToolApprovalStatus } from '@/bootstrap/tool_api'
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

// Per-type identity colour — GUI tools aqua, scripts violet — so the rail,
// eyebrow and Launch button all carry the tool's kind at a glance.
const accent = computed(() => ({ Script: '#c792ea', Notebook: '#ffb74d' } as Record<string, string>)[tool.value.label] ?? '#5fd6e8')
const kind = computed(() => ({ Script: 'Script', Notebook: 'Notebook' } as Record<string, string>)[tool.value.label] ?? 'Web GUI Tool')

const inPlatform = computed(() => !!tool.value.uuid && !tool.value.uuid.startsWith('sparc-tool-'))
const handoffActive = computed(() => ['uploading', 'awaiting_reauth', 'committing'].includes(tool.value.handoffStatus ?? ''))

// While an approval is under way, poll it: each poll relays a fresh token to
// the portal backend, which resumes a handoff paused by an expired one.
let approvalTimer: ReturnType<typeof setInterval> | undefined
const stopApprovalPoll = () => { if (approvalTimer) clearInterval(approvalTimer); approvalTimer = undefined }
watch(handoffActive, (active) => {
  stopApprovalPoll()
  if (!active) return
  approvalTimer = setInterval(async () => {
    try {
      const s = await useToolApprovalStatus(tool.value.id)
      if (s.handoffStatus && !['uploading', 'awaiting_reauth', 'committing'].includes(s.handoffStatus)) {
        stopApprovalPoll()
        emit('approval-done', s)
      }
    } catch (err) {
      console.warn(`Approval status poll failed for tool ${tool.value.id}:`, err)
    }
  }, 3000)
}, { immediate: true })
onBeforeUnmount(stopApprovalPoll)

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

const emit = defineEmits(["launch", "rebuild", "submit-approve", "deploy", "compose-up", "compose-down", "delete", "delete-platform", "view-logs", "approval-done"])

const hasViewLogs = computed(() =>
  !!(tool.value.latestDeployId || tool.value.latestBuildId)
)

const menuItems = computed<UCardMenuItem[]>(() => {
  // A gui workflow's tool: its workflow (Workflow Hub) rebuilds, approves and deletes it; only its backend runs here.
  if (tool.value.kind === 'workflow') {
    const items: UCardMenuItem[] = []
    if (tool.value.hasBackend) items.push({ label: 'Deploy backend', icon: 'mdi-server-network', onClick: onDeploy })
    if (tool.value.deployStatus === 'completed') {
      items.push({ label: 'Compose up', icon: 'mdi-play-circle-outline', onClick: onDockerComposeUp })
      items.push({ label: 'Compose down', icon: 'mdi-stop-circle-outline', onClick: onDockerComposeDown })
    }
    if (hasViewLogs.value) items.push({ label: 'View logs', icon: 'mdi-console-line', onClick: onViewLogs })
    return items
  }
  // Uploaded via the REST API: only a delete, which the hub confirms.
  if (tool.value.platformOnly) {
    return [{ label: 'Delete tool', icon: 'mdi-trash-can-outline', danger: true, onClick: () => emit("delete-platform", tool.value) }]
  }
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
    if(tool.value.label === "Script" || tool.value.label === "Notebook"){
        toast.warning(`${tool.value.label} tool cannot be launched. Please download it and run it locally.`);
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
    emit("deploy", tool.value.id, tool.value.kind)
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
