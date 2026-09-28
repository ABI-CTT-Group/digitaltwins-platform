<template>
  <v-app class="container">
    <AuthNavBar :dashboard-title="dashboardTitle"/>
    <default-view />
  </v-app>
</template>

<script lang="ts" setup>
import DefaultView from "./View.vue";
import AuthNavBar from "@/components/AuthNavBar.vue";
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

    /* FULLY STATIC backdrop — one cached paint layer (aurora gradients + a
       faint tiled grid). No animation and no mask, on purpose:
        - a continuously-animating layer behind the glass navbar forces the
          navbar's backdrop-filter to re-blur EVERY frame (the real cause of
          the scroll stutter — not the backdrop-filter itself);
        - mask-image breaks layer caching, so content scrolling over it
          re-rasterises each frame.
       Static means the browser paints this once and scrolling the content
       above it is essentially free. Single source of truth for every page. */
    background-color: #060f16;
    background-image:
      linear-gradient(rgba(120,200,220,0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(120,200,220,0.04) 1px, transparent 1px),
      radial-gradient(1100px 680px at 8% 4%, rgba(40,180,180,0.24), transparent 60%),
      radial-gradient(1200px 760px at 94% 9%, rgba(58,170,215,0.26), transparent 62%),
      radial-gradient(950px 640px at 70% 110%, rgba(205,95,175,0.18), transparent 60%),
      linear-gradient(180deg, #0e2a3a 0%, #0a1d28 42%, #060f16 72%, #020609 100%);
    background-size: 48px 48px, 48px 48px, auto, auto, auto, auto;

    background-clip: padding-box;
    -webkit-background-clip: padding-box;
}
</style>
