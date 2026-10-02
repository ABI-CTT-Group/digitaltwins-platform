<template>
  <CardUI
    :title="workflow.name"
    kind="Workflow"
    accent="#7fb2f0"
    :is-deleting="isDeleting"
    :menu-items="menuItems"
  >
    <template #description>{{ workflow.description || 'No description provided.' }}</template>

    <template #meta>
      <span v-if="workflow.version" class="aurora-chip">v{{ workflow.version }}</span>
      <span v-if="workflow.author" class="aurora-chip">{{ workflow.author }}</span>
      <span v-if="workflow.status" class="aurora-chip" :style="{ '--chip': auroraStatus(workflow.status) }">
        {{ workflow.status }}
      </span>
      <span v-if="workflow.workflowType" class="aurora-chip">{{ workflow.workflowType }}</span>
      <span v-if="handoffActive" class="aurora-chip" :style="{ '--chip': '#5fd6e8' }">approving…</span>
      <span v-else-if="workflow.handoffStatus === 'failed'" class="aurora-chip" :style="{ '--chip': '#ff6b6b' }">
        approval failed
      </span>
      <span v-if="workflow.platformOnly" class="aurora-chip" :style="{ '--chip': '#9fb4bf' }">platform upload</span>
      <span v-if="workflow.createdAt" class="aurora-chip ms-auto">{{ formatDate(workflow.createdAt) }}</span>
    </template>
  </CardUI>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, toRef, watch } from 'vue'
import { WorkflowResponse } from '@/models/types';
import CardUI, { type UCardMenuItem } from './CardUI.vue';
import { formatDate } from './utils';
import { useWorkflowApprovalStatus, useDeleteWorkflow } from '@/bootstrap/workflow_api';
// @ts-ignore - vue-toastification is installed but missing type declarations
import { useToast } from 'vue-toastification';

const props = defineProps<{
  workflow: WorkflowResponse
}>()

const toast = useToast();
const workflow = toRef(props, "workflow")
const isDeleting = ref(false)

const emit = defineEmits(["submit-approve", "approve-platform", "approval-done", "delete", "delete-platform"])

// Aurora status palette — soft tonal chips keyed by lifecycle state.
const auroraStatus = (s?: string) => {
  switch (s) {
    case "pending": return "#ffb74d"
    case "building": return "#5fd6e8"
    case "failed": return "#ff6b6b"
    case "completed": return "#6fd49a"
    default: return "#9fb4bf"
  }
}

const menuItems = computed<UCardMenuItem[]>(() => workflow.value.platformOnly
  // Uploaded via the REST API: the hub confirms the delete (and whether its tools go too).
  ? [{ label: 'Delete workflow', icon: 'mdi-trash-can-outline', danger: true, onClick: () => emit("delete-platform", workflow.value) }]
  : [
    { label: 'Submit to approval', icon: 'mdi-send-check-outline', onClick: workflow.value.isSds ? () => emit("approve-platform", workflow.value) : onSubmit },
    { label: 'Delete workflow', icon: 'mdi-trash-can-outline', danger: true, onClick: onDelete },
  ])

const ACTIVE = ['uploading', 'awaiting_reauth', 'committing']
const handoffActive = computed(() => ACTIVE.includes(workflow.value.handoffStatus ?? ''))

// While an approval is under way, poll it: each poll relays a fresh token to
// the portal backend, which resumes a handoff paused by an expired one.
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

const onSubmit = () => emit("submit-approve", workflow.value.id)
const onDelete = async () => {
    isDeleting.value = true;
    try {
        const res: any = await useDeleteWorkflow(workflow.value.id)
        if (!res["status"]) {
            isDeleting.value = false;
            toast.error("Error: " + res["message"])
        }
        emit("delete", res)
    } catch (err: any) {
        isDeleting.value = false;
        toast.error("Error: " + (err?.message ?? err))
    }
}
</script>
