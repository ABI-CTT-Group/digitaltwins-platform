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
import { ref, onMounted, computed } from "vue";
import { ITumourStudyAppDetail } from "@/models/apiTypes";
import emitter from "@/plugins/custom-emitter";
import {useTumourStudyDetailsStore } from "@/store/tumour_position_study_app";
import { storeToRefs } from "pinia";

const { studyDetails } = storeToRefs(useTumourStudyDetailsStore());
const disableSelectCase = ref(false);
const caseName = ref("");


onMounted(() => {
  manageEmitters();
});

const completedCases = computed(() => {
  if (!!studyDetails.value === false) return "0 / 0";
  
  const completeTask = studyDetails.value?.details.filter(detail=> detail.report.complete === true);
  return `${completeTask!.length} / ${studyDetails.value?.details.length}`;
});

function manageEmitters() {
  emitter.on("TumourStudy:ImageLoaded", (workingCase: ITumourStudyAppDetail) => {
    caseName.value = workingCase.name;
    disableSelectCase.value = false;
  });
}

</script>

<style scoped>
</style>
