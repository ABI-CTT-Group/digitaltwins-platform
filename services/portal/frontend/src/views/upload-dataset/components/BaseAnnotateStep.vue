<template>
  <v-alert
    v-show="showAlert"
    text="You're missing some required information. Please fill in all the required fields."
    title="Required Fields Missing"
    type="error"
  />

  <!-- ──────────────────────────────────────────────────
       WORKFLOW annotation: multi-step + tool selection
       ────────────────────────────────────────────────── -->
  <template v-if="type === 'workflow'">
    <div>
      <h3 class="text-cyan">Workflow Annotation</h3>
      <v-divider class="my-2 mb-5" :thickness="3" />

      <div v-if="cwlObj">
        <v-form ref="form" class="px-5">
          <div v-for="([key, s], index) in Object.entries(annotateSteps)" :key="key" class="mb-5">
            <h3 class="text-cyan">Step {{ index + 1 }}: {{ s.name }}</h3>
            <v-divider class="my-2 mb-3" :thickness="2" />

            <h4 class="my-2">Workflow Tool *</h4>
            <v-autocomplete
              :custom-filter="toolFilter"
              :items="toolItems"
              item-title="name"
              item-value="id"
              :label="'Select Workflow Tool for Step ' + (index + 1)"
              @update:model-value="(val) => handleToolSelect(val, s)"
              :rules="notEmptyRules"
              clearable
            >
              <template v-slot:item="{ props: itemProps, item }">
                <v-list-item v-bind="itemProps" :subtitle="item.raw.label" />
              </template>
            </v-autocomplete>

            <div v-if="s.toolFhirNote">
              <h4 class="my-2 text-amber-darken-2">Tool Inputs</h4>
              <div class="w-100 d-flex flex-row flex-wrap">
                <div v-for="input in s.toolFhirNote.inputs" class="d-flex flex-column justify-start w-33">
                  <span class="mx-2">{{ input.name }} *</span>
                  <v-text-field
                    class="mt-4 mx-2"
                    v-model="input.resource"
                    bg-color="cyan-darken-4"
                    :rules="notEmptyRules"
                    label="FHIR Resource"
                    variant="solo"
                    required
                    readonly
                  />
                </div>
              </div>
            </div>

            <div v-if="s.toolFhirNote">
              <h4 class="my-2 text-amber-darken-2">Tool Outputs</h4>
              <div class="w-100 d-flex flex-row flex-wrap">
                <div v-for="output in s.toolFhirNote.outputs" class="d-flex flex-column justify-start w-33">
                  <span class="mx-2">{{ output.name }} *</span>
                  <v-text-field
                    class="mt-4 mx-2"
                    v-model="output.resource"
                    bg-color="cyan-darken-4"
                    :rules="notEmptyRules"
                    label="FHIR Resource"
                    variant="solo"
                    required
                    readonly
                  />
                  <div v-if="output.resource === 'Observation'">
                    <v-text-field class="mx-2 my-1" label="Code" v-model="output.code" bg-color="cyan-darken-4" :rules="notEmptyRules" variant="solo" required readonly />
                    <v-text-field class="mx-2 my-1" label="Code System" v-model="output.system" bg-color="cyan-darken-4" :rules="notEmptyRules" variant="solo" required readonly />
                    <v-text-field class="mx-2 my-1" label="Unit" v-model="output.unit" bg-color="cyan-darken-4" variant="solo" readonly />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </v-form>
      </div>
      <NoData v-else />
    </div>
  </template>

  <!-- ──────────────────────────────────────────────────
       TOOL annotation: single CWL file inputs/outputs
       ────────────────────────────────────────────────── -->
  <template v-else>
    <div>
      <h3 class="text-cyan">Workflow Tool FHIR Annotation</h3>
      <v-divider class="my-2 mb-5" :thickness="3" />

      <div v-if="cwlObj">
        <v-form ref="form" class="px-5">
          <h3 class="text-cyan">Tool: {{ annotateTool.name }}</h3>
          <v-divider class="my-2 mb-3" :thickness="2" />

          <h4 class="my-2">Tool Inputs</h4>
          <div class="w-100 d-flex flex-row flex-wrap">
            <div v-for="input in annotateTool.inputs" class="d-flex flex-column justify-start w-33">
              <span class="mx-2">{{ input.name }}</span>
              <v-select class="mt-4 mx-2" v-model="input.resource" :items="fhirResources" label="FHIR Resource" required clearable />
            </div>
          </div>

          <h4 class="my-2">Tool Outputs</h4>
          <div class="w-100 d-flex flex-row flex-wrap">
            <div v-for="output in annotateTool.outputs" class="d-flex flex-column justify-start w-33">
              <span class="mx-2">{{ output.name }}</span>
              <v-select class="mt-4 mx-2" v-model="output.resource" :items="fhirResources" :rules="notEmptyRules" label="FHIR Resource" required clearable />
              <div v-if="output.resource === 'Observation'">
                <v-text-field class="mx-2 my-1" label="Code" v-model="output.code" :rules="notEmptyRules" required clearable />
                <v-select class="mx-2 my-1" :items="fhirObservationSystems" item-title="name" item-value="value" label="Code System" v-model="output.system" :rules="notEmptyRules" clearable />
                <v-text-field class="mx-2 my-1" label="Unit" v-model="output.unit" required clearable />
              </div>
            </div>
          </div>
        </v-form>
      </div>

      <div v-else class="w-100 no_data flex-grow-1 d-flex flex-column justify-center align-center">
        <v-icon size="64" color="pink-darken-1">mdi-note-off-outline</v-icon>
        <h2 class="mt-4">No tool CWL file detected</h2>
        <p class="text-grey">It seems there are no tool CWL files available. Please upload one or try refreshing to check again.</p>
      </div>
    </div>
  </template>

  <!-- Shared action buttons -->
  <div class="d-flex flex-row justify-center">
    <v-btn color="red" text="close" variant="tonal" :width="200" rounded="md" class="hover-animate ma-5" @click="handleClose" />
    <v-btn color="success" text="Submit Annotation" variant="tonal" :width="200" rounded="md" class="hover-animate ma-5" @click="handleAnnotationSubmit" />
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, computed, watch } from 'vue';
import type { WorkflowResponse, ToolResponse, WorkflowStepAnnotation, AnnotateTool } from '@/models/types';
import { getRepoContents, getRepoRootCWLContent } from '@/views/upload-dataset/components/utils';
import type { GitContent } from '@/models/types';
import yaml from 'js-yaml';
import NoData from '@/views/upload-dataset/components/NoData.vue';
import { useWorkflowTools, useGetWorkflowToolAnnotation, useGetToolLocalCwl } from '@/bootstrap/tool_api';
import { useGetWorkflowLocalCwl } from '@/bootstrap/workflow_api';

// ---- props / emits --------------------------------------------------------
const props = defineProps<{
  type: 'workflow' | 'tool';
  data: WorkflowResponse | ToolResponse | undefined;
}>();
const emit = defineEmits(['close', 'annotation-submit']);

// ---- shared state ---------------------------------------------------------
const showAlert = ref(false);
const form = ref();
const cwlObj = ref<any>(null);

const fhirResources = ['Observation', 'ImagingStudy', 'DocumentReference'];
const fhirObservationSystems = [
  { name: 'LOINC Codes',    value: 'https://loinc.org/' },
  { name: 'SNOMED CT',      value: 'http://snomed.info/sct' },
  { name: 'DCM',            value: 'https://fhir-ru.github.io/codesystem-dicom-dcim.html#4.3.14.431' },
  { name: '12 Labours Codes', value: 'https://www.auckland.ac.nz/en/abi/our-research/research-groups-themes/12-Labours.html' },
];
const notEmptyRules = [(v: string) => !!v || "This field can't be empty!"];

// ---- workflow-specific state ----------------------------------------------
const annotateSteps = ref<Array<WorkflowStepAnnotation>>([]);
const workflowTools = ref<ToolResponse[]>([]);
const toolItems = computed(() =>
  workflowTools.value.map((t) => ({ id: t.id, name: t.name, label: t.label })),
);

// ---- tool-specific state --------------------------------------------------
const annotateTool = ref<AnnotateTool>({ name: '', inputs: [], outputs: [] });

// ---- helpers --------------------------------------------------------------
function parseCwlText(raw: string): any {
  try { return yaml.load(raw); }
  catch { return JSON.parse(raw); }
}

async function loadWorkflowCwl(workflow: WorkflowResponse): Promise<{ cwlFile: string; content: any }> {
  if (workflow.sourceType === 'local') {
    const { cwlFile, content } = await useGetWorkflowLocalCwl(workflow.id);
    return { cwlFile, content: parseCwlText(content) };
  }
  // GitHub fallback (default).
  const res = await getRepoContents(workflow.repositoryUrl);
  const files = res!.data as GitContent[];
  let cwlFile = '';
  files.forEach((item: GitContent) => {
    if (item.type === 'file' && item.name.endsWith('.cwl')) { cwlFile = item.name; }
  });
  const contentRes = await getRepoContents(workflow.repositoryUrl, cwlFile);
  const raw = atob((contentRes.data.content as string).replace(/\n/g, ''));
  return { cwlFile, content: parseCwlText(raw) };
}

async function loadToolCwl(tool: ToolResponse): Promise<{ cwlFile: string; content: any }> {
  if (tool.sourceType === 'local') {
    const { cwlFile, content } = await useGetToolLocalCwl(tool.id);
    return { cwlFile, content: parseCwlText(content) };
  }
  return getRepoRootCWLContent(tool.repositoryUrl);
}

// ---- lifecycle ------------------------------------------------------------
onMounted(async () => {
  if (props.type === 'workflow') {
    const workflow = props.data as WorkflowResponse | undefined;
    if (!workflow) { console.warn('No workflow info in annotation stepper.'); return; }

    workflowTools.value = await useWorkflowTools();
    const { content } = await loadWorkflowCwl(workflow);
    cwlObj.value = content;
  } else {
    const tool = props.data as ToolResponse | undefined;
    if (!tool) { console.warn('No workflow tool info in annotation stepper.'); return; }
    const { cwlFile, content } = await loadToolCwl(tool);
    annotateTool.value.name = cwlFile.replace(/\.cwl$/, '');
    cwlObj.value = content;
  }
});

// ---- watchers -------------------------------------------------------------
watch(cwlObj, (newVal) => {
  if (!newVal) return;
  if (props.type === 'workflow') {
    annotateSteps.value = Object.entries(newVal.steps ?? {}).map(([name]) => ({
      name, id: '', uuid: '',
    }));
  } else {
    const inputs = newVal['inputs'] ?? {};
    const outputs = newVal['outputs'] ?? {};
    annotateTool.value.inputs = Object.keys(inputs).map((k) => ({ name: k, resource: '' }));
    annotateTool.value.outputs = Object.keys(outputs).map((k) => ({ name: k, resource: '', code: '', system: '', unit: '' }));
  }
}, { immediate: true });

// ---- handlers -------------------------------------------------------------
const handleToolSelect = async (val: string, step: any) => {
  const selected = workflowTools.value.find((t) => t.id === val);
  if (selected) {
    step.uuid = selected.uuid ?? '';
    step.id = selected.id;
    const annotation = await useGetWorkflowToolAnnotation(selected.id);
    step.toolFhirNote = annotation.fhirNote ? JSON.parse(annotation.fhirNote) : null;
  } else {
    step.uuid = ''; step.id = ''; step.fhirNote = '';
  }
};

function toolFilter(itemTitle: string, queryText: string, item: any) {
  const q = queryText.toLowerCase();
  return itemTitle.toLowerCase().includes(q) || item.raw.label.toLowerCase().includes(q);
}

async function validate() {
  const { valid } = await form.value.validate();
  return valid;
}

const handleAnnotationSubmit = async () => {
  const ok = await validate();
  if (ok) {
    showAlert.value = false;
    if (props.type === 'workflow') {
      emit('annotation-submit', (props.data as WorkflowResponse)!.id, {
        sparcNote: '',
        fhirNote: JSON.stringify(annotateSteps.value),
      });
    } else {
      emit('annotation-submit', (props.data as ToolResponse)!.id, annotateTool.value);
    }
  } else {
    showAlert.value = true;
  }
};

const handleClose = () => emit('close');
</script>

<style scoped>
.no_data { height: 20dvh; }
</style>
