<template>
  <div v-if="study && projectCatalogue" class="design">
    <div class="toolbar">
      <div class="views" role="group" aria-label="View">
        <button type="button" data-test="view-list" :aria-pressed="view === 'list'" :class="{ on: view === 'list' }" @click="setView('list')">
          List
        </button>
        <button type="button" data-test="view-flow" :aria-pressed="view === 'flow'" :class="{ on: view === 'flow' }" @click="setView('flow')">
          Flow
        </button>
      </div>
      <div class="toolbar__run">
        <span class="toolbar__msg" aria-live="polite">{{ message }}</span>
        <v-btn size="small" variant="tonal" prepend-icon="mdi-play-outline" data-test="simulate" :disabled="!canStep" @click="simulateStep">
          Simulate next run
        </v-btn>
        <v-btn size="small" variant="text" :disabled="!sim.ran.length && !sim.submitted.length" @click="resetRun">Reset</v-btn>
      </div>
    </div>
    <p class="design__note">
      <v-icon icon="mdi-flask-empty-outline" size="16" />
      Prototype: these assays use example data. Changes are kept in this browser only, and nothing runs.
    </p>

    <StudyGraph
      v-if="view === 'flow'"
      :study="study"
      :catalogue="projectCatalogue"
      :sim="sim"
      :selected-assay-id="assayId"
      @configure="configure"
      @launch="launch"
      @submit="submit"
      @unavailable="unavailable"
    />
    <div v-else class="list" data-test="assay-list">
      <SandboxAssayCard
        v-for="a in study.assays"
        :key="a.id"
        :assay="a"
        :status="assayStatus(study, sim, a.id)"
        :selected="a.id === assayId"
        :warnings="cohortWarnings(study, a.id).map(cohortWarningText)"
        @configure="configure(a.id)"
        @launch="launch(a.id)"
        @submit="submit(a.id)"
        @unavailable="unavailable"
      />
    </div>

    <ul class="legend">
      <li><span class="sw sw--edge" />Dataset on the platform, or already produced</li>
      <li><span class="sw sw--edge sw--planned" />Planned: exists once its assay's outputs are submitted</li>
      <li><span class="sw sw--dot sw--ready" />Ready to run</li>
      <li><span class="sw sw--dot sw--needs" />Needs configuring, or waiting on earlier assays</li>
      <li><span class="sw sw--dot sw--ran" />Run, not submitted</li>
      <li><span class="sw sw--dot sw--done" />Submitted (simulated)</li>
    </ul>

    <v-dialog v-model="drawerOpen" class="assay-drawer-dialog" content-class="assay-drawer" transition="slide-x-reverse-transition" scrollable>
      <v-card class="assay-drawer__card">
        <div class="assay-drawer__bar">
          <v-btn icon="mdi-close" variant="text" size="small" aria-label="Close" @click="drawerOpen = false" />
        </div>
        <v-card-text class="assay-drawer__body">
          <AssayPanel :study="study" :assay-id="assayId" :catalogue="projectCatalogue" :sim="sim" />
        </v-card-text>
      </v-card>
    </v-dialog>
  </div>
  <div v-else-if="catalogue" class="design design--missing">
    <p>This study isn't in the ISA projects stored in this browser. It may have been removed.</p>
    <router-link :to="{ name: 'IsaProjectPrototype' }">Go to your ISA projects</router-link>
  </div>
</template>

<script setup lang="ts">
// The assays of one sandbox study (prototype), at the study dashboard's assay level: a List or a
// Flow of assay cards, each configured in a side panel. Edits go to the browser-only store.
import { computed, onMounted, ref, watch } from "vue";
import StudyGraph from "./components/StudyGraph.vue";
import AssayPanel from "./components/AssayPanel.vue";
import SandboxAssayCard from "./components/SandboxAssayCard.vue";
import { useIsaProjectStore } from "./isaProjectStore";
import { fixtureSource } from "./adapter/isaProjectSource";
import { withBundled } from "./adapter/isaBundle";
import {
  assayStatus,
  cohortWarnings,
  cohortWarningText,
  emptySim,
  simulateLaunch,
  simulateRunStep,
  simulateSubmit,
  type Sim,
} from "./model/isaProject";
import type { Catalogue } from "./model/types";

const props = defineProps<{ projectId: string; studyId: string }>();

const store = useIsaProjectStore();
const catalogue = ref<Catalogue | null>(null);
const assayId = ref<string | null>(null);
const drawerOpen = ref(false);
/** The simulated run: which assays have run, and whose outputs are submitted. Not saved. */
const sim = ref<Sim>(emptySim());
const message = ref("");

const study = computed(() => store.study(props.projectId, props.studyId));
/** The platform catalogue, the items approvals registered in this browser, and whatever came in this
 *  project's bundle. */
const projectCatalogue = computed(() => catalogue.value && withBundled(withBundled(catalogue.value, store.registered),
  store.entries.find(e => e.project.project.id === props.projectId)?.bundled));

// The chosen view is a per-browser convenience; storage may be unavailable.
type View = "list" | "flow";
const VIEW_KEY = "isa-study-design-view";
const readView = (): View => {
  try { return localStorage.getItem(VIEW_KEY) === "list" ? "list" : "flow"; } catch { return "flow"; }
};
const view = ref<View>(readView());
function setView(v: View) {
  view.value = v;
  try { localStorage.setItem(VIEW_KEY, v); } catch { /* not remembered */ }
}

onMounted(async () => {
  [catalogue.value] = await Promise.all([fixtureSource.catalogue(), store.ensureExamples()]);
});

function resetRun() {
  sim.value = emptySim();
  message.value = "";
}

// A different study, or any edit to this one, invalidates the simulated run.
watch(() => [props.projectId, props.studyId], () => { assayId.value = null; drawerOpen.value = false; resetRun(); });
watch(study, resetRun, { deep: true });

function configure(id: string) {
  assayId.value = id;
  drawerOpen.value = true;
}

const titleOf = (id: string) => study.value?.assays.find(a => a.id === id)?.title ?? id;

function simulateStep() {
  if (!study.value) return;
  const r = simulateRunStep(study.value, sim.value);
  sim.value = r.sim;
  message.value = r.ran.length ? `Ran and submitted ${r.ran.map(titleOf).join(", ")}` : "Nothing else can run";
}

function launch(id: string) {
  if (!study.value) return;
  const status = assayStatus(study.value, sim.value, id);
  if (status === "submitted") {
    message.value = `${titleOf(id)} is already submitted (simulated). Reset to start again.`;
  } else if (status === "ran") {
    message.value = `${titleOf(id)} has already run (simulated). Submit its outputs next.`;
  } else if (status === "ready") {
    sim.value = simulateLaunch(study.value, sim.value, id);
    message.value = `Ran ${titleOf(id)}. Submit its outputs so later assays can use them.`;
  }
}

function submit(id: string) {
  if (sim.value.submitted.includes(id)) {
    message.value = `${titleOf(id)} is already submitted (simulated).`;
  } else if (!sim.value.ran.includes(id)) {
    message.value = `${titleOf(id)} has no run to submit. Launch it first.`;
  } else {
    sim.value = simulateSubmit(sim.value, id);
    message.value = `Submitted ${titleOf(id)}`;
  }
}

function unavailable(action: string) {
  message.value = `${action} isn't part of the prototype.`;
}

const canStep = computed(() =>
  !!study.value && study.value.assays.some(a => assayStatus(study.value!, sim.value, a.id) === "ready"));
</script>

<style scoped>
.design { display: flex; flex-direction: column; gap: 14px; font-family: var(--font-ui); color: var(--text); }
.design__note { display: flex; align-items: center; gap: 6px; margin: 0; font-size: 0.84rem; color: var(--tone-needs); }

.toolbar { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; }
.toolbar__run { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
.toolbar__msg { font-size: 0.82rem; color: var(--text-dim); }

/* List | Flow: one segmented control, the active view filled. */
.views { display: inline-flex; padding: 4px; gap: 4px; border-radius: 12px; border: 1px solid var(--line); background: var(--surface); }
.views button {
  padding: 7px 16px;
  border-radius: 9px;
  border: 0;
  background: transparent;
  color: var(--text-dim);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
.views button.on { background: color-mix(in srgb, var(--accent-tools) 18%, transparent); color: var(--accent-tools); }
.views button:focus-visible { outline: 2px solid var(--accent-tools); outline-offset: 2px; }

.list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: clamp(16px, 1.8vw, 22px);
}
@media (max-width: 960px) { .list { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 600px) { .list { grid-template-columns: minmax(0, 1fr); } }

.legend { display: flex; flex-wrap: wrap; gap: 6px 18px; margin: 0; padding: 0; list-style: none; font-size: 0.78rem; color: var(--text-dim); }
.legend li { display: flex; align-items: center; gap: 6px; }
.sw { display: inline-block; }
.sw--edge { width: 22px; border-top: 2px solid #8fa6b2; }
.sw--planned { border-top-style: dashed; border-top-color: var(--text-faint); }
.sw--dot { width: 8px; height: 8px; border-radius: 50%; }
.sw--ready { background: var(--accent-tools); }
.sw--needs { background: var(--tone-needs); }
.sw--ran { background: #9fb4bf; }
.sw--done { background: var(--accent-measurements); }

.design--missing { padding: 32px 0; color: var(--text-dim); }
.design--missing a { color: var(--accent-tools); }
</style>

<style>
/* The configuration panel slides in from the right as a full-height sheet. Not scoped: the
   dialog's content is teleported out of this component. */
.v-dialog.assay-drawer-dialog { justify-content: flex-end; align-items: stretch; }
.v-dialog.assay-drawer-dialog > .v-overlay__content.assay-drawer {
  margin: 0;
  width: 460px;
  max-width: 100%;
  height: 100%;
  max-height: 100%;
}
.assay-drawer__card { height: 100%; border-radius: 0 !important; background: #0a1a24 !important; }
.assay-drawer__bar { display: flex; justify-content: flex-end; padding: 6px 6px 0; }
.assay-drawer__body { padding-top: 0 !important; }
</style>
