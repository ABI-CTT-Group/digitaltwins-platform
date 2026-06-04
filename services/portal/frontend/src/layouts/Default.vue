<template>
  <v-app class="container">
    <AuthNavBar :dashboard-title="dashboardTitle"/>
    <!-- <NavHome>{{ dashboardTitle }}</NavHome> -->
    <BackIcon v-if="route.matched.some(r => r.meta?.showBack)" />
    <default-view />
  </v-app>
</template>

<script lang="ts" setup>
import DefaultView from "./View.vue";
import AuthNavBar from "@/components/AuthNavBar.vue";
import BackIcon from "@/components/common/BackIcon.vue";
import { useRoute } from "vue-router";
import { computed } from "vue";

const route = useRoute();

const dashboardTitle = computed(() => {
  if (route.name === 'CatalogueDashboardView'){
    return "Catalogue Dashboard";
  } else if (route.name === 'TutorialDashboard'){
    return "How It Works";
  } else if (route.name === 'Dashboard') {
    return route.params.dashboardType === 'clinician' ? "Clinician Dashboard" : "Study Dashboard";
  } else {
    return "";
  }
})
</script>

<style scoped>
.container {
    font-weight: 400;
    font-style: normal;
    position: relative;
    height: 100vh;
    max-height: 100vh;
    overflow: hidden;

    background-color: #071019;
    background-image:
      radial-gradient(1200px circle at 18% 50%,
        rgba(0,0,0,0.85) 0%,
        rgba(0,0,0,0.55) 38%,
        rgba(0,0,0,0.20) 60%,
        rgba(0,0,0,0.00) 72%),
      linear-gradient(
        90deg,
        #050708 0%,
        #071019 3%,
        #0b2433 8%,
        #0e3f5a 33%,
        #0f5f83 50%,
        #1493b4 90%,
        #1fb7d9 100%
      );

    background-clip: padding-box;
    -webkit-background-clip: padding-box;
}
</style>
