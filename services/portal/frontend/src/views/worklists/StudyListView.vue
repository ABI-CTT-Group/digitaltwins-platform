<template>
  <section class="studies">
    <div class="studies__inner">
      <header class="head">
        <h1>Clinician dashboard</h1>
        <p class="lede">Choose a study to review its cases.</p>
        <p class="proto">
          <v-icon icon="mdi-flask-empty-outline" size="16" />
          Prototype with example cases. Decisions are kept in this browser only.
        </p>
      </header>

      <ul class="list">
        <li v-for="s in studies" :key="s.id">
          <RouterLink class="row" data-test="study-row" :to="{ name: 'ClinicianStudyWorklist', params: { studyId: s.id } }">
            <div class="row__top">
              <h2>{{ s.title }}</h2>
              <span class="row__left" data-test="study-left">{{ s.n.review ? `${s.n.review} to review` : "All reviewed" }}</span>
            </div>
            <p class="row__purpose">{{ s.purpose }}</p>
            <div class="row__progress">
              <progress :value="s.n.reviewed" :max="s.n.total" :aria-label="`${s.title}: cases reviewed`" />
              <span data-test="study-reviewed">{{ s.n.reviewed }} of {{ s.n.total }} reviewed</span>
              <span v-if="s.last" class="row__last">Last decision {{ formatDate(s.last) }}</span>
            </div>
          </RouterLink>
        </li>
      </ul>
    </div>
  </section>
</template>

<script setup lang="ts">
// The clinician dashboard (frontend-only prototype): the studies a clinician reviews. Each opens its worklist.
// One example study, whose progress comes from the decisions kept in the browser.
import { computed } from "vue";
import { counts, lastDecision } from "./model/worklist";
import { STUDY, useWorklistStore } from "./worklistStore";

const store = useWorklistStore();

const studies = computed(() => [
  { ...STUDY, n: counts(store.cases), last: lastDecision(store.cases) },
]);

const formatDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-NZ", { day: "numeric", month: "short", year: "numeric" });
</script>

<style scoped>
.studies {
  position: relative;
  min-height: 100%;
  padding: clamp(28px, 6vh, 72px) clamp(16px, 5vw, 80px) 64px;
  font-family: var(--font-ui);
  color: var(--text);
}
.studies__inner { max-width: 1200px; margin: 0 auto; }

.head { display: grid; gap: 6px; }
h1 {
  margin: 0; font-family: var(--font-title); font-weight: 400;
  font-size: clamp(2rem, 4vw, 2.6rem); line-height: 1.1; text-wrap: balance; color: var(--text);
}
.lede { margin: 0; max-width: 62ch; color: var(--text-dim); }
.proto { display: flex; align-items: center; gap: 6px; margin: 4px 0 0; font-size: 0.86rem; color: var(--tone-needs); }

.list { list-style: none; margin: 32px 0 0; padding: 0; border-top: 1px solid var(--line); }
.list li { border-bottom: 1px solid var(--line); }

.row {
  display: grid; gap: 6px; padding: 20px 16px; margin-inline: -16px; border-radius: 8px;
  color: inherit; text-decoration: none;
}
.row:hover { background: var(--surface); }
.row:focus-visible { outline: 2px solid var(--accent-tools); outline-offset: -2px; }

.row__top { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 4px 16px; }
h2 { margin: 0; font-family: var(--font-title); font-weight: 400; font-size: 1.5rem; line-height: 1.2; }
.row__left { font-weight: 600; font-variant-numeric: tabular-nums; color: var(--tone-needs); }
.row__purpose { margin: 0; color: var(--text-dim); }

.row__progress {
  display: flex; flex-wrap: wrap; align-items: center; gap: 6px 14px; margin-top: 6px;
  font-size: 0.875rem; font-variant-numeric: tabular-nums;
}
.row__last { color: var(--text-faint); }

progress {
  appearance: none; width: min(240px, 100%); height: 4px; border: 0; border-radius: 2px;
  background: var(--line); overflow: hidden;
}
progress::-webkit-progress-bar { background: var(--line); }
progress::-webkit-progress-value { background: var(--accent-measurements); }
progress::-moz-progress-bar { background: var(--accent-measurements); }
</style>
