<template>
  <v-list-group value="Cases" class="guide-cases-overall">
    <template v-slot:activator="{ props }">
      <v-list-item
        v-bind="props"
        color="nav-success"
        prepend-icon="mdi-image"
        title="Cases Select"
      ></v-list-item>
    </template>
    <v-text-field
      class="mx-4 my-1"
      label="Completed Cases"
      :model-value="completedCases"
      variant="solo"
      disabled
    ></v-text-field>
    <v-text-field
      class="mx-4"
      label="Case Name"
      :model-value="caseName"
      variant="solo"
      disabled
    ></v-text-field>
  </v-list-group>
</template>

<script setup lang="ts">
import { ref, onMounted, computed, onUnmounted } from "vue";
import { ITumourStudyAppDetail } from "@/models/apiTypes";
import emitter from "@/plugins/custom-emitter";
import {useTumourStudyDetailsStore } from "@/store/tumour_position_study_app";
import { storeToRefs } from "pinia";

const { studyDetails } = storeToRefs(useTumourStudyDetailsStore());
const disableSelectCase = ref(false);
const caseName = ref("");
const fromWhichApp = ref("");


onMounted(() => {
  manageEmitters();
});

const completedCases = computed(() => {
  if (!!studyDetails.value === false) return "0 / 0";
  let completeTask = []
  let totalTask = 0;
  switch (fromWhichApp.value) {
    case "TumourStudy:User-Tumour-Distance-Calculation":
      completeTask = studyDetails.value?.details.filter(detail=> detail.report.complete === true);
      totalTask = studyDetails.value?.details.length;
      break;
    case "TumourStudy:Admin-TumourCenter":
      completeTask = studyDetails.value?.details.filter(detail=> detail.tumour_window.validate === true);
      totalTask = studyDetails.value?.details.length;
      break;
    case "TumourStudy:Admin-TumourAssisted":
      completeTask = studyDetails.value?.details.filter(detail=> detail.report.assisted === true);
      totalTask = studyDetails.value?.details.filter(detail=>detail.report.complete === true).length;
      break;
    default:
      completeTask = [];
      break;
  }
  
  return `${completeTask.length} / ${totalTask}`;
});

function manageEmitters() {
  emitter.on("TumourStudy:ImageLoaded", emitterOnImageLoaded);
  emitter.on("Common:OnAppMounted", emitterOnAppMounted);
}

const emitterOnImageLoaded = (workingCase: ITumourStudyAppDetail) => {
  caseName.value = workingCase.name;
  disableSelectCase.value = false;
};

const emitterOnAppMounted = (from:string) => {
  fromWhichApp.value = from;
}

onUnmounted(() => {
  emitter.off("TumourStudy:ImageLoaded", emitterOnImageLoaded);
  emitter.off("Common:OnAppMounted", emitterOnAppMounted);
});

</script>

<style scoped>
</style>
