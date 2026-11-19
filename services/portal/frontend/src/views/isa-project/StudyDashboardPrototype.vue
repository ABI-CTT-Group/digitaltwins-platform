<template>
  <section class="dashboard">
    <div class="dashboard__inner">
      <DashboardHeader
        root-label="Study dashboard"
        :breadcrumbs="level.breadcrumbs"
        :current-category="nav.currentCategory.value"
        :count="level.items.length"
        :loading="loading"
        @go-root="nav.goToRoot"
        @go-depth="nav.goToDepth"
      />

      <!-- A study is configured as a whole, not assay by assay. -->
      <StudyDesign v-if="study" v-bind="study" />
      <LevelGrid
        v-else
        :items="level.items"
        :loading="loading"
        :error="null"
        :current-category="nav.currentCategory.value"
        :is-clinician-view="false"
        @explore="nav.drill"
      />
    </div>
  </section>
</template>

<script setup lang="ts">
// Frontend-only prototype: the study dashboard for the ISA projects in the browser's store.
// Same parts as the real dashboard (views/dashboard), but nothing here reaches the API.
import { computed, reactive, ref, watch } from "vue";
import type { ResolvedLevel } from "@/composables/useDashboardData";
import { useDashboardNavigation } from "@/composables/useDashboardNavigation";
import DashboardHeader from "@/views/dashboard/components/DashboardHeader.vue";
import LevelGrid from "@/views/dashboard/components/LevelGrid.vue";
import StudyDesign from "./StudyDesign.vue";
import { useIsaProjectStore } from "./isaProjectStore";
import { parseSandboxId, resolveSandboxTrail } from "./sandbox";

const nav = useDashboardNavigation();
const store = useIsaProjectStore();
const loading = ref(true);
const level = reactive<ResolvedLevel>({ items: [], breadcrumbs: [], currentCategory: "Programmes" });

/** The study at the end of the trail, if any. */
const study = computed(() => {
  const last = level.breadcrumbs[level.breadcrumbs.length - 1];
  const ids = last && level.currentCategory === "Assays" ? parseSandboxId(last.seekId) : null;
  return ids?.projectId && ids.studyId ? { projectId: ids.projectId, studyId: ids.studyId } : null;
});

const load = async () => {
  await store.ensureExamples();
  Object.assign(level, resolveSandboxTrail(nav.trail.value, store.entries));
  loading.value = false;
  // A stale trail (e.g. a deleted upload): shorten the URL to the depth that resolved.
  if (level.breadcrumbs.length < nav.trail.value.length) nav.goToDepth(level.breadcrumbs.length);
};

watch(() => nav.trail.value.join(","), load, { immediate: true });
</script>

<style scoped>
.dashboard {
  position: relative;
  min-height: 100%;
  padding: clamp(28px, 6vh, 72px) clamp(20px, 5vw, 80px) 64px;
  font-family: var(--font-ui);
  color: #e9f2f5;
}
.dashboard__inner {
  position: relative;
  max-width: 1200px;
  margin: 0 auto;
}
</style>
