<template>
  <v-app>
    <default-bar :title="title" version="v3.0.0">
      <NavPanel />
    </default-bar>

    <default-view />
  </v-app>
</template>

<script lang="ts" setup>
import DefaultBar from "../components/AppBar.vue";
import DefaultView from "./View.vue";
import NavPanel from "@/components/nav-calculation/NavPanel.vue";
import emitter from "@/plugins/custom-emitter";
import { ref, onBeforeMount } from "vue";

const title = ref("Tumour Position Study")

function manageEmitters() {
  emitter.on("Common:OnAppMounted", handleTumourAppStart);
}

onBeforeMount(()=>{
  manageEmitters();
})


const handleTumourAppStart = (appName:string)=>{

  if(appName == "TumourStudy:Admin-TumourAssisted"){
    title.value = "Tumour Study: Assisted"
  }else if(appName == "TumourStudy:User-Tumour-Distance-Calculation"){
    title.value = "Tumour Study: Calculate Closest Distance"
  }else if(appName == "TumourStudy:Admin-TumourCenter"){
    title.value = "Tumour Study: Validate Tumour Center"
  }else if(appName == "TumourStudy:Admin-TumourPositionReporting"){
    title.value = "Tumour Position Reporting"
  }
}
</script>

<style></style>
