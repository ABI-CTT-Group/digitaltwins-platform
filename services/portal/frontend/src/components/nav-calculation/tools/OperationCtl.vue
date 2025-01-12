<template>
  <Operation>
    <template #Calculator>
      <Calculator />
    </template>
    <template #FunctionalControl>
      <FunctionalControl
        v-model="commFuncRadios"
        :radio-values="commFuncRadioValues"
        :disabled="commFuncRadiosDisabled"
      />
      </template>
  </Operation>
</template>

<script setup lang="ts">
import Calculator from "./advance/Calculator.vue";
import FunctionalControl from "@/components/nav-components/functionalCtl/FunctionalControl.vue";
import Operation from "@/components/nav-components/Operation.vue";
import { ref, onMounted } from "vue";
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

