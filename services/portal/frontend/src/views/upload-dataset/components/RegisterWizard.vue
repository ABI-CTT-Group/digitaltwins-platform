<template>
  <WizardFrame :steps="['Source', 'FHIR annotation (optional)', 'Build']" :current="stepNumber">
    <!-- Step 1, once saved: what was registered, read-only. -->
    <template #summary>
      <dl v-if="id && item" class="summary">
        <div><dt>Name</dt><dd>{{ item.name }}</dd></div>
        <div><dt>Type</dt><dd>{{ typeLabel }}</dd></div>
        <div v-if="item.version"><dt>Version</dt><dd>v{{ item.version }}</dd></div>
        <div><dt>Source</dt><dd>{{ sourceLabel }}</dd></div>
      </dl>
    </template>

    <BaseInformationStep v-if="!id" ref="info" :type="type" :submit="create" @cancel="toHub" />
    <template v-else-if="ready && item">
      <BaseAnnotateStep
        v-if="step === 'annotation'"
        :type="type"
        :data="item"
        :pending-auth="auth"
        :saved-note="savedNote"
        :submit="saveAnnotation"
        @skip="toBuild"
        @close="toHub"
      />
      <BaseBuildStep v-else :type="type" :data="item" :submit="build" @close="toHub" />
    </template>
    <p v-else-if="loadError" class="step-error" role="alert">
      <v-icon icon="mdi-alert-circle-outline" size="18" /> {{ loadError }}
    </p>
    <v-progress-linear v-else-if="!askToken" indeterminate color="#5fd6e8" />
  </WizardFrame>

  <RebuildAuthDialog
    v-model="askToken"
    :source-type="item?.sourceType ?? null"
    title="Repository access"
    note="Tokens are never stored. To read this repository again and build it, enter its token, or leave it blank if the repository is public."
    verb="Continue"
    @submit="onToken"
    @cancel="toHub"
  />
</template>

<script setup lang="ts">
/**
 * The tool and workflow registration wizard: Source → FHIR annotation (optional) → Build.
 * `/catalogue/<hub>/new` runs step 1, which creates the item once, then moves to the item's own URL,
 * `/catalogue/<hub>/<id>/register?step=annotation|build`, where step 1 is a read-only summary.
 * Continue registration and Add/Edit FHIR annotation open that URL from the item's card.
 */
import { computed, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import BaseInformationStep from './BaseInformationStep.vue';
import BaseAnnotateStep from './BaseAnnotateStep.vue';
import BaseBuildStep from './BaseBuildStep.vue';
import RebuildAuthDialog from './RebuildAuthDialog.vue';
import WizardFrame from './WizardFrame.vue';
import { describeApiError } from './apiError';
import { forgetAuth, recallAuth, rememberAuth } from './pendingAuth';
import { hubRoute, registerRoute, type Hub } from './registrationSteps';
import { useLeaveGuard } from './useLeaveGuard';
import {
  useCreateTool, useCreateToolAnnotation, useGetTool, useGetWorkflowToolAnnotation, useWorkflowToolBuild,
} from '@/bootstrap/tool_api';
import {
  useCreateWorkflow, useCreateWorkflowAnnotation, useGetWorkflow, useGetWorkflowAnnotation, useWorkflowBuild,
} from '@/bootstrap/workflow_api';
import { useLogConsole } from '@/composables/useLogConsole';
import type { ToolInformationStep, ToolResponse, TransientAuth, WorkflowInformationStep, WorkflowResponse } from '@/models/types';

const props = defineProps<{ type: 'tool' | 'workflow'; id?: string }>();

type Item = ToolResponse | WorkflowResponse;
const API = {
  tool: {
    create: (data: ToolInformationStep | WorkflowInformationStep) => useCreateTool(data as ToolInformationStep),
    get: useGetTool,
    getNote: useGetWorkflowToolAnnotation,
    saveNote: (id: string, fhirNote: string) => useCreateToolAnnotation(id, { fhirNote, sparcNote: '' }),
    build: useWorkflowToolBuild,
  },
  workflow: {
    create: (data: ToolInformationStep | WorkflowInformationStep) => useCreateWorkflow(data as WorkflowInformationStep),
    get: useGetWorkflow,
    getNote: useGetWorkflowAnnotation,
    saveNote: (id: string, fhirNote: string) => useCreateWorkflowAnnotation(id, { fhirNote, sparcNote: '' }),
    build: useWorkflowBuild,
  },
};
const api = API[props.type];
const hub: Hub = props.type === 'tool' ? 'tools' : 'workflows';

const route = useRoute();
const router = useRouter();
const { openConsole } = useLogConsole();

const step = computed(() => (route.query.step === 'build' ? 'build' : 'annotation'));
const stepNumber = computed(() => (!props.id ? 1 : step.value === 'build' ? 3 : 2));

const info = ref<{ dirty: boolean } | null>(null);
const item = ref<Item>();
const savedNote = ref<string | null>(null);
const auth = ref<TransientAuth | undefined>();
const ready = ref(false);
const askToken = ref(false);
const loadError = ref('');
const created = ref(false);

const typeLabel = computed(() => {
  const i = item.value as any;
  return props.type === 'tool' ? `${i?.label ?? ''} tool` : `${i?.workflowType ?? ''} workflow`;
});
const sourceLabel = computed(() => (item.value?.sourceType === 'local' ? 'Uploaded folder' : item.value?.repositoryUrl));

// Step 1 with something typed in, or its upload running: leaving loses it.
useLeaveGuard(() => !props.id && !created.value && !!info.value?.dirty);

async function load(id: string) {
  ready.value = false;
  loadError.value = '';
  try {
    const [row, note] = await Promise.all([
      api.get(id),
      api.getNote(id).then((a) => a?.fhirNote ?? null).catch(() => null),  // none saved yet
    ]);
    item.value = row;
    savedNote.value = note;
  } catch (err) {
    loadError.value = describeApiError(err, 'Loading');
    return;
  }
  const recalled = recallAuth(id);
  auth.value = recalled.auth;
  // Continued later, a git source may need its token again to read the CWL and build.
  if (!recalled.known && item.value.sourceType && item.value.sourceType !== 'local') {
    askToken.value = true;
    return;
  }
  ready.value = true;
}
watch(() => props.id, (id) => { if (id) load(id); }, { immediate: true });

function onToken(token: TransientAuth) {
  auth.value = token;
  rememberAuth(props.id!, token);
  askToken.value = false;
  ready.value = true;
}

async function create(data: ToolInformationStep | WorkflowInformationStep, stepAuth?: TransientAuth) {
  const row = await api.create(data);
  rememberAuth(row.id, stepAuth);
  created.value = true;
  await router.replace(registerRoute(hub, row.id, 'annotation'));
}

async function saveAnnotation(id: string, fhirNote: string) {
  await api.saveNote(id, fhirNote);
  savedNote.value = fhirNote;
  await toBuild();
}

const toBuild = () => router.replace(registerRoute(hub, props.id!, 'build'));
const toHub = () => router.push(hubRoute(hub));

async function build(id: string) {
  const res = await api.build(id, auth.value);
  forgetAuth(id);  // single use: a rebuild asks again
  // The Tool Hub mounts the log console; a workflow's card shows its build.
  if (props.type === 'tool') openConsole('build', res.buildId, item.value?.name ?? id, 'building');
  await toHub();
}
</script>

<style scoped>
.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 28px;
  margin: 4px 0 16px;
  font-family: var(--font-ui);
}
.summary dt { font-size: 0.75rem; color: var(--text-faint); }
.summary dd { margin: 0; font-size: 0.9375rem; color: var(--text); overflow-wrap: anywhere; font-variant-numeric: tabular-nums; }
</style>
