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
      class="mx-4"
      label="Case Name"
      :model-value="caseName"
      variant="solo"
      disabled
    ></v-text-field>
  </v-list-group>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useFileCountStore } from "@/store/app";
import { storeToRefs } from "pinia";
import { ITumourStudyAppDetail } from "@/models/apiTypes";
import emitter from "@/plugins/custom-emitter";


const disableSelectCase = ref(false);
const caseName = ref("");


onMounted(() => {
  manageEmitters();
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
