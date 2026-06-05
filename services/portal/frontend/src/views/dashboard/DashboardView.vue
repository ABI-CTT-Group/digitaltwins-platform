<template>
  <section class="dashboard">
    <div class="dashboard__inner">
      <DashboardHeader
        :root-label="rootLabel"
        :breadcrumbs="level.breadcrumbs"
        :current-category="nav.currentCategory.value"
        :count="level.items.length"
        :loading="data.loading.value"
        @go-root="nav.goToRoot"
        @go-depth="nav.goToDepth"
      />

      <LevelGrid
        :items="level.items"
        :loading="data.loading.value"
        :error="data.error.value"
        :current-category="nav.currentCategory.value"
        :is-clinician-view="isClinicianView"
        @explore="nav.drill"
        @retry="reload"
      />
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
import { reactive, computed, watch } from "vue";
import { useRoute } from "vue-router";
import { DashboardCategory } from "@/models/types";
import { useDashboardData, ResolvedLevel } from "@/composables/useDashboardData";
import { useDashboardNavigation } from "@/composables/useDashboardNavigation";
import { useAssayActions } from "@/composables/useAssayActions";
import DashboardHeader from "./components/DashboardHeader.vue";
import LevelGrid from "./components/LevelGrid.vue";
import DownloadSheet from "@/components/domain/DownloadSheet.vue";
import SubmitSheet from "@/components/domain/SubmitSheet.vue";

const route = useRoute();
const data = useDashboardData();
const nav = useDashboardNavigation();
const actions = useAssayActions();

/** "study" (default) or "clinician" — set on the route meta. */
const dashboardType = computed(() => (route.meta?.type as string) ?? "study");
const isClinicianView = computed(() => dashboardType.value === "clinician");
const rootLabel = computed(() => (isClinicianView.value ? "Clinician dashboard" : "Study dashboard"));

/** The clinician dashboard shows only the "Auckland hospital" programme; the
 *  study dashboard shows everything else. Filter is applied at the root only. */
const typeFilter = (item: DashboardCategory) =>
  isClinicianView.value
    ? item.name === "Auckland hospital"
    : item.name !== "Auckland hospital";

const level = reactive<ResolvedLevel>({
  items: [],
  breadcrumbs: [],
  currentCategory: "Programmes",
});

const load = async () => {
  const resolved = await data.loadTrail(nav.trail.value, typeFilter);
  level.items = resolved.items;
  level.breadcrumbs = resolved.breadcrumbs;
  level.currentCategory = resolved.currentCategory;

  // Self-heal a stale/invalid trail: if the resolved depth is shorter than the
  // URL trail, rewrite the URL to the depth we could actually reach.
  if (resolved.breadcrumbs.length < nav.trail.value.length) {
    nav.goToDepth(resolved.breadcrumbs.length);
    return;
  }

  // The Assays level needs per-assay config + launch state loaded.
  if (resolved.currentCategory === "Assays") {
    actions.loadAssayList(resolved.items);
  }
};

const reload = () => load();

watch(
  () => [dashboardType.value, nav.trail.value.join(",")],
  () => load(),
  { immediate: true },
);
</script>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Hanken+Grotesk:wght@400;500;600;700&display=swap');

.dashboard {
  position: relative;
  min-height: 100%;
  padding: clamp(28px, 6vh, 72px) clamp(20px, 5vw, 80px) 64px;
  font-family: 'Hanken Grotesk', system-ui, sans-serif;
  color: #e9f2f5;
  /* Aurora background is provided once by .page-aurora in layouts/View.vue. */
}
.dashboard__inner {
  position: relative;
  max-width: 1200px;
  margin: 0 auto;
}
</style>
