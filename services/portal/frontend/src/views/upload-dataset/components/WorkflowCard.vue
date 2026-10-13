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
      <span class="aurora-chip" :style="{ '--chip': registration.color }" :title="registration.title">{{ registration.label }}</span>
      <span v-if="build" class="aurora-chip" :style="{ '--chip': build.color }">{{ build.label }}</span>
      <span v-if="deploy" class="aurora-chip" :style="{ '--chip': deploy.color }" :title="deploy.title">{{ deploy.label }}</span>
      <span v-if="type" class="aurora-chip">{{ type.label }}</span>
      <span v-if="workflow.version" class="aurora-chip">v{{ workflow.version }}</span>
      <span v-if="workflow.author" class="aurora-chip">{{ workflow.author }}</span>
      <span v-if="workflow.createdAt" class="aurora-chip ms-auto">{{ formatDate(workflow.createdAt) }}</span>
    </template>
  </CardUI>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, toRef, watch } from 'vue'
import { WorkflowResponse } from '@/models/types';
import CardUI, { type UCardMenuItem } from './CardUI.vue';
import { formatDate } from './utils';
import { buildTag, deployTag, handoffRegistrationTag, typeTag } from './cardTags';
import { useWorkflowApprovalStatus, useDeleteWorkflow } from '@/bootstrap/workflow_api';
// @ts-ignore - vue-toastification is installed but missing type declarations
import { useToast } from 'vue-toastification';

const props = defineProps<{
  workflow: WorkflowResponse
  /** The viewer may deploy script workflow DAGs into Airflow (admins). */
  canDeploy?: boolean
}>()

const toast = useToast();
const workflow = toRef(props, "workflow")
const isDeleting = ref(false)

const emit = defineEmits(["submit-approve", "approve-platform", "approval-done", "delete", "delete-platform", "deploy-dag"])

const registration = computed(() => handoffRegistrationTag(workflow.value, 'sparc-workflow-'))
const build = computed(() => buildTag(workflow.value))
const type = computed(() => typeTag(workflow.value.workflowType))

const deploy = computed(() => deployTag(workflow.value.dagStatus, workflow.value.dagError))

// A script workflow in the platform has an Airflow DAG an admin can deploy (again).
const inPlatform = computed(() => !!workflow.value.platformOnly
  || (!!workflow.value.uuid && !workflow.value.uuid.startsWith('sparc-workflow-')))
const deployItem = computed<UCardMenuItem[]>(() =>
  props.canDeploy && workflow.value.workflowType === 'script' && inPlatform.value && workflow.value.dagStatus !== 'deploying'
    ? [{ label: 'Deploy DAG', icon: 'mdi-rocket-launch-outline', onClick: () => emit("deploy-dag", workflow.value) }]
    : [])

const menuItems = computed<UCardMenuItem[]>(() => workflow.value.platformOnly
  // Uploaded via the REST API: the hub confirms the delete (and whether its tools go too).
  ? [...deployItem.value,
    { label: 'Delete workflow', icon: 'mdi-trash-can-outline', danger: true, onClick: () => emit("delete-platform", workflow.value) }]
  : [
    { label: 'Submit to approval', icon: 'mdi-send-check-outline', onClick: workflow.value.isSds ? () => emit("approve-platform", workflow.value) : onSubmit },
    ...deployItem.value,
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
