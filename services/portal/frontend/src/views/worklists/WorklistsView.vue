<template>
  <section class="worklists">
    <div v-if="!study" class="worklists__inner">
      <RouterLink class="back" :to="{ name: 'ClinicianDashboard' }"><v-icon icon="mdi-arrow-left" size="16" /> All studies</RouterLink>
      <p class="lede missing">There is no study called {{ studyId }}.</p>
    </div>
    <div v-else class="worklists__inner">
      <header class="head">
        <nav class="crumb" aria-label="Study">
          <RouterLink class="back" :to="{ name: 'ClinicianDashboard' }"><v-icon icon="mdi-arrow-left" size="16" /> All studies</RouterLink>
          <strong data-test="study-title">{{ study.title }}</strong>
        </nav>
        <h1>Your worklist</h1>
        <p class="lede">Retrospective study. Check the annotation on each case, then confirm it or send it back for correction.</p>
        <p class="proto">
          <v-icon icon="mdi-flask-empty-outline" size="16" />
          Prototype with example cases. Decisions are kept in this browser only.
        </p>
      </header>

      <div class="progress">
        <p class="progress__line" data-test="progress"><b>{{ n.reviewed }}</b> of <b>{{ n.total }}</b> cases reviewed</p>
        <form class="batch" data-test="batch-form" @submit.prevent="start">
          <label for="batch-size">
            Review next
            <input id="batch-size" v-model.number="batchSize" type="number" min="1" :max="Math.max(n.review, 1)" :disabled="!n.review" inputmode="numeric">
            {{ batchSize === 1 ? "case" : "cases" }}
          </label>
          <span class="batch__left">{{ n.review ? `${n.review} left to review` : "All cases reviewed" }}</span>
          <button type="submit" class="aurora-btn aurora-btn--solid" :disabled="!n.review">Start</button>
        </form>
      </div>

      <div class="main">
        <CaseTable v-model:tab="tab" v-model:query="query" :cases="store.cases" :selected-id="selectedId" @select="pick" />
        <CaseReviewPanel
          :item="selected"
          :batch-pos="batch ? batchPosition(batch) : 0"
          :batch-total="batch?.total ?? 0"
          @decide="decide"
          @open="toast.info(`The annotator would open ${selectedId} here. It isn't connected in this prototype.`)"
        />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
// One study's worklist on the clinician dashboard (frontend-only prototype): its cases for clinicians to review,
// one decision per case. Example cases kept in the browser; nothing reaches an API.
import { computed, ref } from "vue";
import { useToast } from "vue-toastification";
import { useAuthStore } from "@/store/auth_store";
import { afterDecision, batchPosition, counts, startBatch, type Batch, type Tab } from "./model/worklist";
import { STUDY, useWorklistStore } from "./worklistStore";
import CaseTable from "./components/CaseTable.vue";
import CaseReviewPanel from "./components/CaseReviewPanel.vue";

const props = defineProps<{ studyId: string }>();

const store = useWorklistStore();
const study = computed(() => (props.studyId === STUDY.id ? STUDY : null));
const auth = useAuthStore();
const toast = useToast();

const tab = ref<Tab>("review");
const query = ref("");
const batchSize = ref(10);
const batch = ref<Batch | null>(null);
const selectedId = ref<string | null>(store.cases.find(c => c.status === "review")?.id ?? null);

const n = computed(() => counts(store.cases));
const selected = computed(() => store.cases.find(c => c.id === selectedId.value) ?? null);

function start() {
  const want = Math.floor(Number(batchSize.value));
  if (!(want >= 1)) { toast.warning("Enter how many cases to review: 1 or more."); return; }
  batch.value = startBatch(store.cases, want);
  if (!batch.value) return;
  batchSize.value = batch.value.total;
  tab.value = "review";
  selectedId.value = batch.value.ids[0];
}

/** Choosing a case by hand leaves the batch. */
function pick(id: string) {
  batch.value = null;
  selectedId.value = id;
}

function decide(status: "confirmed" | "needs", note: string | null) {
  const id = selectedId.value;
  if (!id) return;
  store.decide(id, status, note, auth.displayName || "You");
  const next = afterDecision(store.cases, batch.value, id);
  if (next.finished) {
    const total = batch.value!.total;
    toast.success(`Batch finished: ${total} ${total === 1 ? "case" : "cases"} reviewed`);
  } else {
    toast.success(status === "confirmed" ? `Confirmed ${id}` : `Sent ${id} for correction`);
  }
  batch.value = next.batch;
  selectedId.value = next.selectedId;
}
</script>

<style scoped>
.worklists {
  position: relative;
  min-height: 100%;
  padding: clamp(28px, 6vh, 72px) clamp(16px, 5vw, 80px) 64px;
  font-family: var(--font-ui);
  color: var(--text);
}
.worklists__inner { max-width: 1200px; margin: 0 auto; }

.head { display: grid; gap: 6px; }
.crumb { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 16px; font-size: 0.875rem; }
.crumb strong { color: var(--text); font-weight: 600; }
.back {
  display: inline-flex; align-items: center; gap: 6px; border-radius: 6px;
  color: var(--text-dim); text-decoration: none;
}
.back:hover { color: var(--text); }
.back:focus-visible { outline: 2px solid var(--accent-tools); outline-offset: 2px; }
.missing { margin-top: 16px; }
h1 {
  margin: 10px 0 0; font-family: var(--font-title); font-weight: 400;
  font-size: clamp(2rem, 4vw, 2.6rem); line-height: 1.1; text-wrap: balance; color: var(--text);
}
.lede { margin: 0; max-width: 62ch; color: var(--text-dim); }
.proto { display: flex; align-items: center; gap: 6px; margin: 4px 0 0; font-size: 0.86rem; color: var(--tone-needs); }

.progress {
  display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 16px;
  padding-block: 24px;
}
.progress__line { margin: 0; font-size: 1.05rem; }
.progress__line b { font-variant-numeric: tabular-nums; }
.batch { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
.batch label { display: inline-flex; align-items: center; gap: 8px; font-weight: 600; }
.batch input {
  width: 4.5em; padding: 7px 8px; border-radius: 8px; text-align: center; font-weight: 600;
  font-variant-numeric: tabular-nums; background: var(--surface); border: 1px solid var(--line); color: var(--text);
}
.batch__left { font-size: 0.875rem; color: var(--text-faint); }

.main { display: grid; grid-template-columns: minmax(0, 1fr) 380px; gap: 28px; align-items: start; }

@media (max-width: 960px) {
  .main { grid-template-columns: minmax(0, 1fr); }
  .main > :last-child { order: -1; }
}
</style>
