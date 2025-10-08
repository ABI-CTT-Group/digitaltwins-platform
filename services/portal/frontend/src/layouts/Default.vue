<template>
  <v-app class="container">
    <NavHome>{{ dashboardTitle }}</NavHome>

    <default-view />
  </v-app>
</template>

<script lang="ts" setup>
import DefaultView from "./View.vue";
import NavHome from "@/components/dt-components/NavHome.vue";
import { useRoute } from "vue-router";
import { watch, ref, computed } from "vue";

const route = useRoute();

const dashboardTitle = computed(() => {
  if (route.name === 'CatalogueDashboardView'){
    return "Catalogue Dashboard";
  }else if(route.name === 'TutorialDashboard'){
    return "How It Works";
  }else if (route.params.dashboardType === 'clinician') {
    return "Clinician Dashboard";
  } else if (route.params.dashboardType === 'study') {
    return "Study Dashboard";
  }else {
    return "";
  }
})

</script>

<style scoped>
.container {
    font-weight: 400;
    font-style: normal;
    position: relative;
    /* background-image: url("@/assets/bg.png"); 
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    backdrop-filter: blur(10px); 
    -webkit-backdrop-filter: blur(10px);  */
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
        #071019 18%,
        #0b2433 33%,
        #0e3f5a 50%,
        #0f5f83 68%,
        #1493b4 90%,
        #1fb7d9 100%
      );

    background-clip: padding-box;
    -webkit-background-clip: padding-box;
}
</style>
