<template>
  <section class="report">
    <div class="report__inner">
      <BackLink back label="Back to dashboard" />

      <!-- Loading -->
      <div v-if="loading" class="report__center">
        <v-progress-circular indeterminate size="48" width="3" color="#5fd6e8" />
        <p class="report__hint">Loading assay…</p>
      </div>

      <!-- Not ready -->
      <div v-else-if="!ready" class="report__center report__empty">
        <v-icon icon="mdi-flask-empty-off-outline" size="56" />
        <h2 class="report__empty-title">Assay isn't ready to launch</h2>
        <p class="report__empty-sub">
          Double-check that the workflow, datasets and cohorts are configured. If the issue
          persists, contact your system administrator.
        </p>
      </div>

      <!-- Ready -->
      <template v-else>
        <header class="report__head">
          <p class="report__eyebrow">Assay report center</p>
          <h1 class="report__title">{{ assayName }}</h1>
          <p class="report__sub">Launch, monitor and retrieve results for this assay's cohorts.</p>
        </header>

        <div class="report__actions">
          <AssayActionBar
            :ready="ready"
            :launching="launching"
            :can-monitor="canMonitor"
            @launch="actions.launch(assayId)"
            @monitor="actions.monitor(assayId)"
            @verify="actions.verify(assayId)"
            @download="actions.download(assayId)"
            @submit="actions.submit(assayId)"
          />
        </div>

        <div class="panel">
          <h2 class="panel__title">Cohorts</h2>
          <div class="cohorts">
            <div v-for="cohort in cohorts" :key="cohort.uuid" class="cohort-row">
              <div class="cohort-row__name">
                <strong>{{ capitalize(cohort.name) }}</strong>
                <span class="cohort-row__id">{{ cohort.uuid }}</span>
              </div>
              <button type="button" class="cohort-row__btn">Get report</button>
            </div>
          </div>
        </div>
      </template>
    </div>

    <DownloadSheet
      v-model:download-dialog="actions.downloadDialog.value"
      :download-zip-progress-value="actions.downloadZipProgressValue.value"
    />
    <SubmitSheet
      v-model:submit-dialog="actions.submitDialog.value"
      :submit-state="actions.submitState.value"
    />
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute } from "vue-router";
import BackLink from "@/components/common/BackLink.vue";
import AssayActionBar from "@/views/dashboard/components/AssayActionBar.vue";
import DownloadSheet from "@/components/domain/DownloadSheet.vue";
import SubmitSheet from "@/components/domain/SubmitSheet.vue";
import { useAssayActions } from "@/composables/useAssayActions";
import { useDashboardCacheStore } from "@/store/dashboard_cache_store";
import {
  useDashboardSeekAssay,
  useDashboardGetAssayConfigDetails,
} from "@/bootstrap/dashboard_api";
import type { SeekAssayDetails } from "@/models/types";
import { capitalize } from "@/utils/common";

const route = useRoute();
const assayId = route.query.assayId as string;

const actions = useAssayActions();
const store = useDashboardCacheStore();

const loading = ref(true);
const seekAssay = ref<SeekAssayDetails>();

// Mock cohorts — replace with the real cohort API when it lands.
const cohorts = ref<Array<{ name: string; uuid: string }>>([
  { name: "Cohort 1", uuid: "uuid-1" },
  { name: "Cohort 2", uuid: "uuid-2" },
  { name: "Cohort 3", uuid: "uuid-3" },
]);

const detail = computed(() => store.assayDetails[assayId]);
const exec = computed(() => store.assayExecute[assayId]);
const ready = computed(() => detail.value?.isAssayReadyToLaunch ?? false);
const launching = computed(() => exec.value?.isLaunching ?? false);
const canMonitor = computed(() => exec.value?.text === "Monitor");

// Prefer the name cached from the assays list; fall back to the fetched seek
// assay only on a deep-link where the list was never loaded.
const assayName = computed(() => {
  const n = store.assayNames[assayId] ?? seekAssay.value?.name;
  return n ? capitalize(n) : "Assay";
});

// Only fetch what the cache is actually missing. Arriving from the dashboard,
// both name and config are already cached → zero requests. A fresh deep-link /
// refresh fetches just the missing pieces.
onMounted(async () => {
  try {
    const needName = !store.assayNames[assayId];
    const needConfig = !store.assayDetails[assayId];
    const [seek, config] = await Promise.all([
      needName ? useDashboardSeekAssay(assayId) : Promise.resolve(undefined),
      needConfig ? useDashboardGetAssayConfigDetails(assayId) : Promise.resolve(undefined),
    ]);
    if (seek) seekAssay.value = seek;
    if (config) store.setAssayDetails(assayId, config);
    if (!store.assayExecute[assayId]) store.setAssayExecute(assayId, "Launch", "");
  } finally {
    loading.value = false;
  }
});
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500&display=swap');

.report {
  position: relative;
  min-height: 100%;
  padding: clamp(28px, 6vh, 72px) clamp(20px, 5vw, 80px) 64px;
  font-family: "Nunito", sans-serif;
  color: #e9f2f5;
  /* Aurora background provided by .page-aurora in layouts/View.vue. */
}
.report__inner {
  max-width: 1000px;
  margin: 0 auto;
}

/* ---- States ---- */
.report__center {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: clamp(60px, 16vh, 140px) 20px;
  text-align: center;
}
.report__hint { color: #a4bac4; }
.report__empty { color: #5f7884; }
.report__empty-title {
  margin: 4px 0 0;
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 500;
  font-size: clamp(1.6rem, 3.4vw, 2.4rem);
  color: #e9f2f5;
}
.report__empty-sub {
  margin: 0;
  max-width: 52ch;
  font-size: 0.95rem;
  line-height: 1.55;
  color: #a4bac4;
}

/* ---- Header ---- */
.report__head { margin: 28px 0 22px; }
.report__eyebrow {
  margin: 0 0 10px;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: #5fd6e8;
  opacity: 0.85;
}
.report__title {
  margin: 0;
  font-family: 'Fraunces', Georgia, serif;
  font-weight: 500;
  font-size: clamp(2.2rem, 5vw, 3.4rem);
  line-height: 1.0;
  letter-spacing: -0.015em;
  color: #fff;
}
.report__sub {
  margin: 14px 0 0;
  max-width: 60ch;
  font-size: 1rem;
  line-height: 1.55;
  color: #a4bac4;
}

.report__actions { margin-bottom: 28px; }

/* ---- Cohorts panel ---- */
.panel {
  border-radius: 18px;
  border: 1px solid rgba(120, 200, 220, 0.14);
  background: rgba(255, 255, 255, 0.028);
  padding: 24px 26px;
}
.panel__title {
  margin: 0 0 14px;
  font-size: 1.2rem;
  font-weight: 800;
  color: #fff;
}
.cohorts {
  max-height: 52vh;
  overflow-y: auto;
}
.cohort-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 6px;
  border-bottom: 1px solid rgba(120, 200, 220, 0.1);
}
.cohort-row:last-child { border-bottom: none; }
.cohort-row__name {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  color: #e9f2f5;
}
.cohort-row__id {
  padding: 2px 10px;
  border-radius: 6px;
  font-size: 0.78rem;
  color: #ffb74d;
  background: rgba(0, 0, 0, 0.3);
}
.cohort-row__btn {
  flex-shrink: 0;
  min-width: 140px;
  padding: 8px 18px;
  border-radius: 8px;
  font-family: "Nunito", sans-serif;
  font-size: 0.84rem;
  font-weight: 700;
  cursor: pointer;
  color: #5fd6e8;
  background: rgba(95, 214, 232, 0.14);
  border: 1px solid rgba(95, 214, 232, 0.32);
  transition: background 0.25s ease, border-color 0.25s ease;
}
.cohort-row__btn:hover {
  background: rgba(95, 214, 232, 0.26);
  border-color: rgba(95, 214, 232, 0.55);
}
</style>
