<template>
  <div v-if="assay" class="panel">
    <header class="panel__head">
      <h2 class="panel__title">{{ assay.title }}</h2>
      <p class="panel__meta">
        <span class="kind">{{ assay.type }} assay</span>
        <span class="status" :class="`status--${status}`">{{ STATUS_TEXT[status] }}</span>
      </p>
    </header>

    <section class="block">
      <v-select
        label="Workflow"
        :items="workflowItems"
        item-title="name"
        item-value="id"
        :model-value="assay.workflowId"
        :no-data-text="`No ${assay.type} workflows in the catalogue`"
        density="comfortable"
        variant="outlined"
        hide-details
        @update:model-value="pickWorkflow"
      />
      <div v-if="tools.length" class="tools">
        <div class="tools__head">
          <h3 class="block__title">Tools in this workflow</h3>
          <v-btn size="small" variant="text" prepend-icon="mdi-graph-outline" @click="showWorkflow = true">
            View workflow
          </v-btn>
        </div>
        <ol class="tools__list">
          <li v-for="t in tools" :key="t.stepId" data-test="tool" class="tool">
            <span class="tool__name">{{ t.toolName }}</span>
            <span class="tool__step">step {{ t.stepId }}<template v-if="t.toolType">, {{ t.toolType }}</template></span>
          </li>
        </ol>
      </div>
    </section>

    <section v-if="assay.inputs.length" class="block">
      <h3 class="block__title">Inputs</h3>
      <div v-for="input in assay.inputs" :key="input.port" :data-test="`input-${input.port}`" class="io">
        <v-select
          :label="input.port"
          :items="optionsFor(input.port)"
          item-title="label"
          item-value="key"
          :model-value="input.source ? sourceKey(input.source) : null"
          :hint="categoryOf(input.port)"
          persistent-hint
          density="comfortable"
          variant="outlined"
          no-data-text="Nothing of this category yet"
          @update:model-value="(key: string) => pickSource(input.port, key)"
        >
          <template #item="{ props: itemProps, item }">
            <v-list-item v-bind="itemProps" :class="{ 'is-planned': isGhost(item.raw) }">
              <template #prepend>
                <v-icon :icon="isGhost(item.raw) ? 'mdi-database-clock-outline' : 'mdi-database-outline'" size="18" />
              </template>
              <v-list-item-subtitle>{{ describe(item.raw) }}</v-list-item-subtitle>
            </v-list-item>
          </template>
          <template #selection="{ item }">
            <span class="chosen" :class="{ 'is-planned': isGhost(item.raw) }">
              <v-icon :icon="isGhost(item.raw) ? 'mdi-database-clock-outline' : 'mdi-database-outline'" size="16" />
              <span class="chosen__name">{{ item.raw.label }}</span>
              <span class="chosen__note">{{ describe(item.raw) }}</span>
            </span>
          </template>
        </v-select>
        <p v-for="w in warningsFor(input.port)" :key="w" class="warn" data-test="cohort-warning">
          <v-icon icon="mdi-alert-outline" size="16" />{{ w }}
        </p>
      </div>
    </section>

    <section v-if="assay.outputs.length" class="block">
      <h3 class="block__title">Outputs</h3>
      <p class="block__help">Each output becomes a planned dataset. Later assays in this study can use it before it exists.</p>
      <div v-for="output in assay.outputs" :key="output.port" data-test="output" class="io">
        <v-text-field
          :label="`${output.port}: dataset name`"
          :model-value="output.datasetName"
          :hint="output.category"
          persistent-hint
          density="comfortable"
          variant="outlined"
          @update:model-value="(v: string) => (output.datasetName = v)"
        />
      </div>
    </section>

    <section v-if="assay.workflowId" class="block">
      <v-text-field
        label="Cohort (subjects)"
        :model-value="cohortText"
        :error-messages="cohortError"
        hint="For example 1-5,8. Leave empty to run every subject."
        persistent-hint
        density="comfortable"
        variant="outlined"
        @update:model-value="setCohort"
      />
    </section>

    <WorkflowToolsDialog v-model="showWorkflow" :workflow="workflow" />
  </div>
  <div v-else class="panel panel--empty">
    <v-icon icon="mdi-cursor-default-click-outline" size="28" />
    <p>Select an assay in the tree or the graph to configure it.</p>
  </div>
</template>

<script setup lang="ts">
// Configures one assay of a study. It edits the study object it is given in place: the page's
// composable owns that object, and this is a throwaway prototype, so there is no save step.
import { computed, ref, watch } from "vue";
import type { Catalogue, Study } from "../model/types";
import {
  assayStatus,
  cohortWarnings,
  cohortWarningText,
  formatCohort,
  inputOptions,
  parseCohort,
  setWorkflow,
  sourceKey,
  workflowTools,
  type AssayStatus,
  type InputOption,
  type Sim,
} from "../model/isaProject";
import WorkflowToolsDialog from "./WorkflowToolsDialog.vue";

const props = defineProps<{ study: Study; assayId: string | null; catalogue: Catalogue; sim: Sim }>();

const STATUS_TEXT: Record<AssayStatus, string> = {
  unconfigured: "Needs configuring",
  blocked: "Waiting on earlier assays",
  ready: "Ready to run",
  ran: "Run, not submitted",
  submitted: "Submitted (simulated)",
};

const assay = computed(() => props.study.assays.find(a => a.id === props.assayId) ?? null);
const status = computed(() => (assay.value ? assayStatus(props.study, props.sim, assay.value.id) : "unconfigured"));
const workflow = computed(() => props.catalogue.workflows.find(w => w.id === assay.value?.workflowId) ?? null);
const workflowItems = computed(() => props.catalogue.workflows.filter(w => w.type === assay.value?.type));
const tools = computed(() => workflowTools(props.catalogue, assay.value?.workflowId ?? null));
const showWorkflow = ref(false);

const categoryOf = (port: string) => workflow.value?.inputs.find(p => p.name === port)?.category ?? "";

const optionsFor = (port: string): InputOption[] => {
  const category = workflow.value?.inputs.find(p => p.name === port)?.category;
  return assay.value && category ? inputOptions(props.study, props.catalogue, assay.value.id, category) : [];
};

/** A planned dataset that doesn't exist yet: its producer's outputs aren't (simulated) submitted. */
const isGhost = (o: InputOption) =>
  o.planned && !props.sim.submitted.includes(o.source.kind === "planned" ? o.source.assayId : "");

const warningsFor = (port: string) =>
  assay.value ? cohortWarnings(props.study, assay.value.id).filter(w => w.port === port).map(cohortWarningText) : [];

const describe = (o: InputOption) =>
  !o.planned ? "On the platform" : isGhost(o) ? `Will be produced by ${o.producedBy}` : `Produced by ${o.producedBy}`;

function pickWorkflow(id: string) {
  const wf = props.catalogue.workflows.find(w => w.id === id);
  if (assay.value && wf) setWorkflow(props.study, assay.value.id, wf);
}

function pickSource(port: string, key: string) {
  const input = assay.value?.inputs.find(i => i.port === port);
  const option = optionsFor(port).find(o => o.key === key);
  if (input) input.source = option ? option.source : null;
}

const cohortText = ref("");
const cohortError = ref("");
watch(assay, a => { cohortText.value = formatCohort(a?.cohort ?? []); cohortError.value = ""; }, { immediate: true });

function setCohort(text: string) {
  cohortText.value = text;
  const parsed = parseCohort(text);
  if (parsed === null) {
    cohortError.value = "Use subject numbers and ranges, for example 1-5,8.";
    return;
  }
  cohortError.value = "";
  if (assay.value) assay.value.cohort = parsed;
}
</script>

<style scoped>
.panel { display: flex; flex-direction: column; gap: 22px; }
.panel--empty {
  align-items: center;
  justify-content: center;
  gap: 10px;
  min-height: 240px;
  text-align: center;
  color: var(--text-faint);
}
.panel--empty p { max-width: 26ch; margin: 0; }

.panel__title {
  margin: 0;
  font-family: var(--font-title);
  font-weight: 500;
  font-size: 1.55rem;
  line-height: 1.1;
  color: #fff;
}
.panel__meta { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 0; font-size: 0.82rem; }
.kind { color: var(--text-dim); }
.status { padding: 1px 9px; border-radius: 999px; border: 1px solid currentColor; }
.status--unconfigured { color: var(--text-faint); }
.status--blocked { color: var(--tone-needs); }
.status--ready { color: var(--accent-tools); }
.status--ran { color: #9fb4bf; }
.status--submitted { color: var(--accent-measurements); }
.warn { display: flex; align-items: center; gap: 6px; margin: 6px 0 0; font-size: 0.8rem; color: var(--tone-needs); }

.block { display: flex; flex-direction: column; gap: 12px; }
.block__title { margin: 0; font-size: 0.92rem; font-weight: 600; color: var(--text); }
.block__help { margin: -4px 0 0; font-size: 0.82rem; line-height: 1.5; color: var(--text-dim); }

.tools__head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.tools__list { margin: 8px 0 0; padding: 0 0 0 1.2em; display: flex; flex-direction: column; gap: 6px; }
.tool { color: var(--text); font-size: 0.88rem; }
.tool__name { font-weight: 500; }
.tool__step { margin-left: 8px; color: var(--text-faint); font-size: 0.8rem; }

/* Name, then the note on its own line, so a long note never squeezes the name. */
.chosen {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  column-gap: 6px;
  align-items: center;
  min-width: 0;
  padding: 2px 0;
}
.chosen__name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.chosen__note { grid-column: 2; color: var(--text-faint); font-size: 0.76rem; line-height: 1.3; }
.chosen.is-planned { color: var(--text-dim); font-style: italic; }
.v-list-item.is-planned { opacity: 0.62; font-style: italic; }
</style>
