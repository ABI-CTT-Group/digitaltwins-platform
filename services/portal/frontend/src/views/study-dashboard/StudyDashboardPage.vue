<template>
  <StudyListView v-if="view === 'clinician'">
    <template #toolbar><ViewAsSwitch :views="views" :model-value="view" @update:model-value="choose" /></template>
  </StudyListView>
  <StudyDashboardPrototype v-else>
    <template #toolbar><ViewAsSwitch :views="views" :model-value="view" @update:model-value="choose" /></template>
  </StudyDashboardPrototype>
</template>

<script setup lang="ts">
// The study dashboard (prototype) at /study-dashboard: the clinician view or the researcher view,
// by role. See dashboardView.ts for which one opens.
import StudyDashboardPrototype from "@/views/isa-project/StudyDashboardPrototype.vue";
import StudyListView from "@/views/worklists/StudyListView.vue";
import ViewAsSwitch from "./ViewAsSwitch.vue";
import { useStudyDashboardView } from "./dashboardView";

const { views, view, choose } = useStudyDashboardView();
</script>
