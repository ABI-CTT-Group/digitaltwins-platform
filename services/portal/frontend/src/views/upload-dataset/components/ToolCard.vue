<template>
  <CardUI
    :title="tool.name"
    kind="Tool"
    :is-disabled="!!disabled"
    :menu-items="menuItems"
  >
    <template #description>{{ tool.description || 'No description provided.' }}</template>

    <template #status><StatusLine :status="status" /></template>

    <template #meta>
      <span v-if="type" class="aurora-chip">{{ type }}</span>
      <span v-if="tool.kind === 'workflow'" class="aurora-chip aurora-chip--clip" :title="`from ${tool.workflowName}`">from {{ tool.workflowName }}</span>
      <span v-if="tool.version" class="aurora-chip">v{{ tool.version }}</span>
      <span v-for="p in status.problems" :key="p.label" class="aurora-chip aurora-chip--problem" :title="p.reason">{{ p.label }}</span>
    </template>

    <template v-if="status.action" #action>
      <button type="button" class="aurora-btn aurora-btn--sm" :disabled="disabled" @click.stop="runAction(status.action)">
        {{ ACTION_LABELS[status.action] }}
      </button>
    </template>
  </CardUI>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, toRef, watch } from 'vue'
import { ToolResponse } from '@/models/types';
import { useToolApprovalStatus } from '@/bootstrap/tool_api'
import CardUI, { type UCardMenuItem } from './CardUI.vue';
import StatusLine from './StatusLine.vue';
import { ACTION_LABELS, isInPlatform, toolStatus, type CardAction } from './cardStatus';

const props = defineProps<{
  tool: ToolResponse
  disabled?: boolean
}>()

const tool = toRef(props, "tool")

const status = computed(() => toolStatus(tool.value))
// GUI / Script / Notebook, as a chip in the workflows' vocabulary (gui · script · notebook).
const type = computed(() => tool.value.label?.toLowerCase())
const handoffActive = computed(() => ['uploading', 'awaiting_reauth', 'committing'].includes(tool.value.handoffStatus ?? ''))

// While an approval is under way, poll it: each poll relays a fresh token to
// the builder, which resumes a handoff paused by an expired one.
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

const emit = defineEmits(["launch", "rebuild", "continue", "edit-annotation", "submit-approve", "retry-fhir", "compose-down", "delete", "delete-platform", "view-logs", "approval-done"])

const runAction = (action: CardAction) => {
  if (action === 'continue') emit("continue", tool.value)
  else if (action === 'view-logs') onViewLogs()
  else if (action === 'approve' || action === 'approve-again') onSubmit()
  else if (action === 'launch') onLaunch()
  else if (action === 'retry-fhir') emit("retry-fhir", tool.value)
}

const hasViewLogs = computed(() =>
  !!(tool.value.latestDeployId || tool.value.latestBuildId)
)

const stopBackend: UCardMenuItem = { label: 'Stop backend', icon: 'mdi-stop-circle-outline',
  onClick: () => emit("compose-down", tool.value.latestDeployId) }

const menuItems = computed<UCardMenuItem[]>(() => {
  // A gui workflow's tool: its workflow (Workflow Hub) rebuilds, approves and deletes it.
  // Launch starts a backend (/tool-view); the menu only stops it.
  if (tool.value.kind === 'workflow') {
    const items: UCardMenuItem[] = []
    if (tool.value.deployStatus === 'completed') items.push(stopBackend)
    if (hasViewLogs.value) items.push({ label: 'View logs', icon: 'mdi-console-line', onClick: onViewLogs })
    return items
  }
  // Uploaded via the REST API: only a delete, which the hub confirms.
  if (tool.value.platformOnly) {
    return [{ label: 'Delete tool', icon: 'mdi-trash-can-outline', danger: true, onClick: () => emit("delete-platform", tool.value) }]
  }
  // The status line's action is the card's button; the menu holds the rest.
  const isGui = tool.value.label === 'GUI'
  const action = status.value.action
  const items: UCardMenuItem[] = []
  if (isGui && tool.value.status === 'completed' && action !== 'launch') {
    items.push({ label: 'Launch', icon: 'mdi-rocket-launch-outline', onClick: onLaunch })
  }
  // The FHIR annotation is optional; it can be added or changed until the tool is in the platform.
  if (!isInPlatform(tool.value, 'sparc-tool-')) {
    items.push({ label: tool.value.hasAnnotation ? 'Edit FHIR annotation' : 'Add FHIR annotation', icon: 'mdi-pencil-outline',
      onClick: () => emit("edit-annotation", tool.value) })
  }
  items.push({ label: 'Rebuild', icon: 'mdi-refresh', onClick: onRebuild })
  if (tool.value.deployStatus === 'completed' && isGui) {
    items.push(stopBackend)
  }
  if (hasViewLogs.value && action !== 'view-logs') {
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

// Only GUI tools launch; /tool-view starts the backend.
const onLaunch = () => emit("launch", tool.value.id)
const onRebuild = () => {
    // No optimistic prop mutation here. The parent flow may open a dialog
    // (and the user might Cancel) or the build POST itself may fail, in
    // which case `tool.status` should NOT have flipped to "building".
    // Parent calls registryRef.handleRefresh() once the build is actually
    // started — that pulls the real PENDING/BUILDING status from backend.
    emit("rebuild", tool.value.id)
}
const onSubmit = () => emit("submit-approve", tool.value)
// The hub confirms and deletes.
const onDelete = () => emit("delete", tool.value)
</script>
