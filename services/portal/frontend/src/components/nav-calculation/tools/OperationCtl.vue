<template>
  <v-list-group value="Operation" class="guide-operation-overall" data-tool="operationtool">
    <template v-slot:activator="{ props }">
      <v-list-item
        v-bind="props"
        color="nav-success"
        prepend-icon="mdi-axe"
        title="Operation Settings"
      ></v-list-item>
    </template>
    <!-- Functional Control -->
    <Calculator />
    <v-container fluid>
      <v-progress-linear
        color="nav-success-2"
        buffer-value="0"
        stream
      ></v-progress-linear>
      <v-radio-group
        class="radio-group guide-operation-functional-control"
        v-model="commFuncRadios"
        label="Functional Controller"
        :inline="true"
        :disabled="commFuncRadiosDisabled"
      >
        <v-radio
          v-for="(item, idx) in commFuncRadioValues"
          :key="idx"
          :label="item.label"
          :value="item.value"
          :color="item.color"
        ></v-radio>
      </v-radio-group>
      <v-progress-linear
        color="nav-success-2"
        buffer-value="0"
        stream
      ></v-progress-linear>
      <!-- </v-container> -->
    </v-container>
  </v-list-group>
</template>

<script setup lang="ts">
import Calculator from "./advance/Calculator.vue";
import { ref, onMounted } from "vue";
import { storeToRefs } from "pinia";
import emitter from "@/plugins/custom-emitter";

// Functional Controls
const commFuncRadios = ref("segmentation");
const commFuncRadiosDisabled = ref(true);

const commFuncRadioValues = ref([
  { label: "Calculate Distance", value: "calculator", color: "calculator" },
]);



onMounted(() => {
  manageEmitters();
});

function manageEmitters() {

  emitter.on("TumourStudy:NextCase", async (casename: string)=>{
    commFuncRadiosDisabled.value = true;
  });

  emitter.on("TumourStudy:ImageLoaded", () => {
    commFuncRadiosDisabled.value = false;
    commFuncRadios.value = "calculator";
  });
 
}



</script>

<style>
.v-selection-control-group--inline {
  flex-direction: row;
  flex-wrap: wrap;
  justify-content: space-between;
  padding: 0 10px;
}
</style>
