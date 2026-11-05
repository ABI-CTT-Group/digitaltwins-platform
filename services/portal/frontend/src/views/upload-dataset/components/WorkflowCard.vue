<template>
  <CardUI
    :title="workflow.name"
    kind="Workflow"
    accent="var(--accent-workflows)"
    :menu-items="menuItems"
  >
    <template #description>{{ workflow.description || 'No description provided.' }}</template>

    <template #status><StatusLine :status="status" /></template>

    <template #meta>
      <span v-if="workflow.workflowType" class="aurora-chip">{{ workflow.workflowType }}</span>
      <span v-if="workflow.version" class="aurora-chip">v{{ workflow.version }}</span>
      <span v-for="p in status.problems" :key="p.label" class="aurora-chip aurora-chip--problem" :title="p.reason">{{ p.label }}</span>
    </template>

    <template v-if="status.action" #action>
      <button type="button" class="aurora-btn aurora-btn--sm" @click.stop="runAction(status.action)">
        {{ ACTION_LABELS[status.action] }}
      </button>
    </template>
  </CardUI>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, toRef, watch } from 'vue'
import { WorkflowResponse } from '@/models/types';
import CardUI, { type UCardMenuItem } from './CardUI.vue';
import StatusLine from './StatusLine.vue';
import { ACTION_LABELS, isInPlatform, workflowStatus, type CardAction } from './cardStatus';
import { useWorkflowApprovalStatus } from '@/bootstrap/workflow_api';

const props = defineProps<{
  workflow: WorkflowResponse
  /** The viewer may deploy script workflow DAGs into Airflow (admins). */
  canDeploy?: boolean
}>()

const workflow = toRef(props, "workflow")

const emit = defineEmits(["continue", "edit-annotation", "approve-platform", "approval-done", "retry-fhir", "delete", "delete-platform", "deploy-dag"])

const status = computed(() => workflowStatus(workflow.value, { canDeploy: props.canDeploy }))

// Approve hands an SDS workflow to the platform; non-SDS workflows aren't supported yet (no action).
const runAction = (action: CardAction) => {
  if (action === 'continue') emit("continue", workflow.value)
  else if (action === 'approve' || action === 'approve-again') emit("approve-platform", workflow.value)
  else if (action === 'deploy-dag') emit("deploy-dag", workflow.value)
  else if (action === 'retry-fhir') emit("retry-fhir", workflow.value)
}

// A deployed script workflow's DAG can be deployed again from the menu; the first deploy is the button.
const redeployItem = computed<UCardMenuItem[]>(() =>
  props.canDeploy && workflow.value.workflowType === 'script' && workflow.value.dagStatus === 'deployed'
    ? [{ label: 'Deploy DAG again', icon: 'mdi-rocket-launch-outline', onClick: () => emit("deploy-dag", workflow.value) }]
    : [])

// The FHIR annotation is optional; it can be added or changed until an SDS workflow is in the platform.
const annotationItem = computed<UCardMenuItem[]>(() =>
  !isInPlatform(workflow.value, 'sparc-workflow-') && workflow.value.isSds !== false
    ? [{ label: workflow.value.hasAnnotation ? 'Edit FHIR annotation' : 'Add FHIR annotation', icon: 'mdi-pencil-outline',
      onClick: () => emit("edit-annotation", workflow.value) }]
    : [])

const menuItems = computed<UCardMenuItem[]>(() => [
  ...annotationItem.value,
  ...redeployItem.value,
  // Uploaded via the REST API: the hub confirms the delete (and whether its tools go too).
  workflow.value.platformOnly
    ? { label: 'Delete workflow', icon: 'mdi-trash-can-outline', danger: true, onClick: () => emit("delete-platform", workflow.value) }
    : { label: 'Delete workflow', icon: 'mdi-trash-can-outline', danger: true, onClick: onDelete },
])

const ACTIVE = ['uploading', 'awaiting_reauth', 'committing']
const handoffActive = computed(() => ACTIVE.includes(workflow.value.handoffStatus ?? ''))

// While an approval is under way, poll it: each poll relays a fresh token to
// the builder, which resumes a handoff paused by an expired one.
let approvalTimer: ReturnType<typeof setInterval> | undefined
const stopApprovalPoll = () => { if (approvalTimer) clearInterval(approvalTimer); approvalTimer = undefined }
watch(handoffActive, (active) => {
  stopApprovalPoll()
  if (!active) return
  approvalTimer = setInterval(async () => {
    try {
      const s = await useWorkflowApprovalStatus(workflow.value.id)
      if (s.handoffStatus && !ACTIVE.includes(s.handoffStatus)) {
        stopApprovalPoll()
        emit('approval-done', s)
      }
    } catch (err) {
      console.warn(`Approval status poll failed for workflow ${workflow.value.id}:`, err)
    }
  }, 3000)
}, { immediate: true })
onBeforeUnmount(stopApprovalPoll)

// The hub confirms and deletes.
const onDelete = () => emit("delete", workflow.value)
</script>
